import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from .driver import EventLog
from .marker import ClockFit, ClockFitError, MarkerCode, MarkerTrack
from .scenario import ScenarioLibrary
from .settle import ChangeSeries, FrameDiff, Rect, SettleDetector, SettleParams
from .video import VideoFile


class AnalysisError(Exception):
    pass


class RunAnalyzer:
    def __init__(self, config, scenarios: ScenarioLibrary):
        self.config = config
        self.scenarios = scenarios

    def reference_path(self, app_id: str, task_id: str, step_name: str) -> Path:
        return self.config.workdir / "references" / app_id / task_id / f"{step_name}.png"

    def step_params(self, app_scenario, step, settle_override: dict | None = None) -> SettleParams:
        return SettleParams.from_dict(self.config.get("settle"), app_scenario.settle, step.settle, settle_override)

    def analyze(self, run_dir: Path, settle_override: dict | None = None, use_references: bool = True) -> dict:
        run_dir = Path(run_dir)
        meta = json.loads((run_dir / "meta.json").read_text())
        if meta.get("status") != "complete":
            raise AnalysisError(f"{run_dir} is not a complete run ({meta.get('status')}: {meta.get('error')})")
        events = EventLog.read(run_dir / "log.jsonl")
        layout = meta["layout"]
        app_rect = Rect.from_dict(layout["app_in_capture"])
        marker_rect = Rect.from_dict(layout["marker_in_capture"])
        code = MarkerCode(int(layout["marker_cell"]))
        scenario = self.scenarios.get(meta["task"]).for_app(meta["app"])
        steps = [s for s in scenario.steps if s.measure]
        params = {s.name: self.step_params(scenario, s, settle_override) for s in steps}
        masks = [Rect.from_dict(m) for m in scenario.masks + list(self.config.get("display.masks") or [])]
        base = SettleParams.from_dict(self.config.get("settle"), scenario.settle)
        diff = FrameDiff(app_rect.width, app_rect.height, base.pixel_threshold, masks)

        references = {}
        for step in steps if use_references else []:
            path = None
            if step.expect == "auto":
                candidate = self.reference_path(meta["app"], meta["task"], step.name)
                path = candidate if candidate.exists() else None
            elif step.expect:
                path = self.config.workdir / "references" / step.expect
            if path is not None:
                references[step.name] = np.asarray(Image.open(path).convert("RGB"))

        video = VideoFile(run_dir / "capture.mkv", self.config.tool("ffmpeg"), self.config.tool("ffprobe"))
        times = video.frame_times()
        counts = np.zeros(len(times), dtype=np.int64)
        distances = {name: np.ones(len(times), dtype=np.float32) for name in references}
        track = MarkerTrack()
        previous = None
        count = 0
        for i, frame in enumerate(video.frames()):
            if i >= len(times):
                break
            m = marker_rect
            track.add(float(times[i]), code.decode(frame[m.y:m.y + m.height, m.x:m.x + m.width]))
            app = frame[app_rect.y:app_rect.y + app_rect.height, app_rect.x:app_rect.x + app_rect.width]
            if previous is not None:
                counts[i] = diff.changed_pixels(previous, app)
            for name, reference in references.items():
                if reference.shape == app.shape:
                    distances[name][i] = diff.reference_distance(app, reference, params[name].reference_pixel_threshold)
            previous = app
            count = i + 1
        times, counts = times[:count], counts[:count]
        distances = {k: v[:count] for k, v in distances.items()}
        series = ChangeSeries(times, counts, distances)
        series.save(run_dir / "changes.npz")

        fps = float(self.config.get("capture.fps", 60))
        driver_markers = {e["code"]: e["t"] for e in events if e["type"] == "marker"}
        try:
            fit = ClockFit.fit(driver_markers, track.first_seen, 1.0 / fps)
        except ClockFitError as ex:
            raise AnalysisError(f"{run_dir}: {ex}") from ex

        results = []
        for n, event in enumerate(events):
            if event["type"] != "step_start" or not event.get("measure", True):
                continue
            name = event["step"]
            start = fit.to_video(event["t"])
            later = [e for e in events[n + 1:] if e["type"] in ("input", "marker")]
            window_end = fit.to_video(later[0].get("t_before", later[0]["t"])) if later else float(times[-1])
            tolerance = params[name].reference_tolerance
            accept = None
            if name in distances:
                accept = lambda index, d=distances[name], tol=tolerance: bool(d[index] <= tol)
            result = SettleDetector(params[name]).find_end(series, start, window_end, accept)
            entry = {"name": name, **result.to_dict(), "window_end": window_end,
                     "reference": name in references}
            if name in distances and result.end_index is not None:
                entry["reference_distance"] = float(distances[name][result.end_index])
            results.append(entry)

        intervals = np.diff(times)
        dropped = int(np.count_nonzero(intervals > 1.5 / fps))
        ok = all(r["status"] == "settled" for r in results) and len(results) == len(steps)
        analysis = {
            "version": 1, "run": meta["run"], "app": meta["app"], "task": meta["task"],
            "comparison": meta["comparison"], "warmup": meta["warmup"], "order": meta.get("order"),
            "status": "ok" if ok else "failed",
            "total_s": sum(r["duration_s"] for r in results) if ok else None,
            "steps": results, "clock_fit": fit.to_dict(),
            "frames": {"count": int(count), "duration_s": float(times[-1] - times[0]) if count else 0.0,
                       "dropped_intervals": dropped, "mean_fps": float(1 / np.mean(intervals)) if count > 1 else 0},
            "analyzed": datetime.now(timezone.utc).isoformat(),
        }
        (run_dir / "analysis.json").write_text(json.dumps(analysis, indent=2))
        return analysis


class Aggregator:
    def __init__(self, config, scenarios: ScenarioLibrary):
        self.config = config
        self.scenarios = scenarios

    def run_dirs(self, comparison: str, task: str, app: str) -> list[Path]:
        root = self.config.workdir / "runs" / comparison / task / app
        if not root.exists():
            return []
        return sorted(p for p in root.glob("*") if (p / "meta.json").exists() and p.name != "reference")

    @staticmethod
    def median_run(runs: list[dict]) -> dict:
        totals = [r["total_s"] for r in runs]
        median = statistics.median(totals)
        return min(runs, key=lambda r: (abs(r["total_s"] - median), r["order"] or 0))

    def side(self, comparison: str, task: str, app_id: str) -> dict:
        app = self.config.app(app_id)
        scenario = self.scenarios.get(task).for_app(app_id)
        runs, failures, warmups, forced_close = [], [], [], []
        for run_dir in self.run_dirs(comparison, task, app_id):
            path = run_dir / "analysis.json"
            meta = json.loads((run_dir / "meta.json").read_text())
            if meta.get("warmup"):
                warmups.append(meta["run"])
                continue
            if meta.get("closed_cleanly") is False:
                forced_close.append(meta["run"])
            if not path.exists():
                failures.append({"run": meta["run"], "reason": meta.get("error") or "not analyzed"})
                continue
            analysis = json.loads(path.read_text())
            if analysis["status"] != "ok":
                failures.append({"run": analysis["run"], "reason": "; ".join(
                    f"{s['name']}: {s['status']}" for s in analysis["steps"] if s["status"] != "settled")})
                continue
            runs.append(analysis)
        side = {"app": app_id, "name": app.get("name", app_id), "version": app.get("version"),
                "protocol": app.get("protocol"), "os": app.get("os"),
                "actions": scenario.user_action_count, "action_list": scenario.action_list,
                "runs": [{"run": r["run"], "order": r["order"], "total_s": r["total_s"],
                          "steps": {s["name"]: s["duration_s"] for s in r["steps"]}} for r in runs],
                "warmups_discarded": warmups, "failed_runs": failures, "runs_app_killed_at_close": forced_close}
        if runs:
            totals = [r["total_s"] for r in runs]
            chosen = self.median_run(runs)
            side.update({"median_s": statistics.median(totals), "min_s": min(totals), "max_s": max(totals),
                         "median_run": chosen["run"], "measured_runs": len(runs)})
            side["steps"] = {}
            for step in [s for s in scenario.steps if s.measure]:
                values = [r_s["duration_s"] for r in runs for r_s in r["steps"] if r_s["name"] == step.name]
                side["steps"][step.name] = {"median_s": statistics.median(values), "min_s": min(values),
                                            "max_s": max(values)}
        else:
            side.update({"median_s": None, "min_s": None, "max_s": None, "median_run": None, "measured_runs": 0})
        return side

    def comparison(self, comparison_id: str) -> dict:
        spec = self.config.comparison(comparison_id)
        tasks = {}
        for task in spec["tasks"]:
            scenario = self.scenarios.get(task)
            left = self.side(comparison_id, task, spec["left"])
            right = self.side(comparison_id, task, spec["right"])
            ratio = None
            if left["median_s"] and right["median_s"] is not None:
                ratio = right["median_s"] / left["median_s"]
            tasks[task] = {"title": scenario.title, "description": scenario.description,
                           "left": left, "right": right, "ratio": ratio}
        return {"os": spec.get("os"), "left": spec["left"], "right": spec["right"], "tasks": tasks}


class ReportWriter:
    def __init__(self, results: dict, deviations: list[str]):
        self.results = results
        self.deviations = deviations

    @staticmethod
    def seconds(value) -> str:
        return "–" if value is None else f"{value:.2f} s"

    def write(self, path: Path):
        r = self.results
        lines = ["# Speed benchmark report", "",
                 f"Generated {r['generated']}. Median of {r['runs']['measured']} measured runs per app and task, "
                 f"after {r['runs']['warmup']} discarded warm-up run(s) each.", "",
                 "## Method", "",
                 "- Same computer, OS, display resolution, window size, network, server and account snapshot for both apps.",
                 "- Apps recorded one after another, never at the same time; run order interleaved (A B A B …).",
                 "- Server and client state restored from the same snapshot before every run.",
                 "- Screen recording (lossless, 60 fps) runs during every measured run of every app; ffmpeg pinned "
                 "to its own CPU core where the OS allows it.",
                 "- A step starts at the logged input event (mapped onto the video by sync markers and a linear fit) "
                 "and ends at the last significant screen change before a quiet period; see the settle parameters below.",
                 "- The video shows the median run, synchronized at the start of each task.", "",
                 "## Deviations from default settings", ""]
        lines += [f"- {d}" for d in self.deviations] or ["- none"]
        lines += ["", "## Settle detection parameters", "", "```json", json.dumps(r.get("settle", {}), indent=2), "```",
                  "", "## Environment", ""]
        for comparison_id, env in (r.get("environment") or {}).items():
            lines.append(f"### {comparison_id}")
            lines += [f"- {k}: {v}" for k, v in sorted(env.items()) if not isinstance(v, (dict, list))]
            for k, v in sorted(env.items()):
                if isinstance(v, dict):
                    lines.append(f"- {k}: " + ", ".join(f"{kk} {vv}" for kk, vv in v.items()))
            lines.append("")
        for comparison_id, comparison in r["comparisons"].items():
            any_task = next(iter(comparison["tasks"].values()))
            left, right = any_task["left"], any_task["right"]
            lines += [f"## {comparison_id}: {left['name']} {left['version'] or ''} ({left['protocol']}) vs "
                      f"{right['name']} {right['version'] or ''} ({right['protocol']}), {comparison['os']}", "",
                      "| Task | Left median | min–max | actions | Right median | min–max | actions | right ÷ left |",
                      "|---|---|---|---|---|---|---|---|"]
            for task_id, t in comparison["tasks"].items():
                l, rr = t["left"], t["right"]
                ratio = "–" if t["ratio"] is None else f"{t['ratio']:.2f}"
                lines.append(f"| {task_id} {t['title'].get('en', '')} | {self.seconds(l['median_s'])} | "
                             f"{self.seconds(l['min_s'])}–{self.seconds(l['max_s'])} | {l['actions']} | "
                             f"{self.seconds(rr['median_s'])} | {self.seconds(rr['min_s'])}–{self.seconds(rr['max_s'])} | "
                             f"{rr['actions']} | {ratio} |")
            lines.append("")
            for task_id, t in comparison["tasks"].items():
                lines.append(f"### {comparison_id} {task_id}: {t['title'].get('en', '')}")
                for side_name in ("left", "right"):
                    s = t[side_name]
                    lines.append(f"- **{s['name']}** ({s['protocol']}): actions: " + "; ".join(s["action_list"]))
                    lines.append("  - runs: " + ", ".join(f"{x['run']} {x['total_s']:.3f} s" for x in s["runs"])
                                 + (f"; median run shown: {s['median_run']}" if s["median_run"] else ""))
                    for step, v in (s.get("steps") or {}).items():
                        lines.append(f"  - step {step}: median {self.seconds(v['median_s'])}, "
                                     f"min {self.seconds(v['min_s'])}, max {self.seconds(v['max_s'])}")
                    if s["failed_runs"]:
                        lines.append("  - failed runs (excluded): " + "; ".join(
                            f"{f['run']} ({f['reason']})" for f in s["failed_runs"]))
                    if s.get("runs_app_killed_at_close"):
                        lines.append("  - app didn't quit by itself after these runs and was killed (check for "
                                     "unexpected dialogs): " + ", ".join(s["runs_app_killed_at_close"]))
                    if s["warmups_discarded"]:
                        lines.append("  - warm-up runs discarded: " + ", ".join(s["warmups_discarded"]))
                lines.append("")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
