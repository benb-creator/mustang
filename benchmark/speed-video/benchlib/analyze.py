import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from .driver import Calibration, EventLog
from .marker import ClockFit, ClockFitError, MarkerCode, MarkerTrack
from .references import References
from .scenario import ScenarioLibrary, Step
from .settle import CompletionGate, FrameAnalyzer, MovingMasks, Rect, Region, SettleDetector, SettleParams
from .video import VideoError, VideoFile


class AnalysisError(Exception):
    pass


class StepVerdict:
    """What a step's analysis means for the run: ok, a measurement outcome, or a failure of the measurement."""

    ok = "ok"
    timeout = "timeout"
    wrong_result = "wrong-result"
    invalid = "invalid"
    technical = "technical"

    severity = {ok: 0, timeout: 1, invalid: 2, technical: 3, wrong_result: 4}


class ListRows:
    """When the message list first shows rows: per frame, a small grey thumbnail of the list area and its share of
    "ink" (pixels far from the area's background). Rows are visible once the area has changed from its state at the
    step's start and holds ink."""

    size = 32

    def __init__(self, rect: Rect):
        self.rect = rect
        self.thumbnails: list[np.ndarray] = []
        self.ink: list[float] = []

    def add(self, frame: np.ndarray):
        area = self.rect.crop(frame)
        grey = area[:, :, 1] if area.ndim == 3 else area
        background = int(np.median(grey[::4, ::4]))
        self.ink.append(float(np.count_nonzero(np.abs(grey.astype(np.int16) - background) > 40)) / max(1, grey.size))
        h, w = grey.shape
        ys = np.linspace(0, h - 1, self.size).astype(int)
        xs = np.linspace(0, w - 1, self.size).astype(int)
        self.thumbnails.append(grey[np.ix_(ys, xs)].astype(np.uint8))

    def first_rows(self, times: np.ndarray, start: float, end: float, min_ink: float = 0.01,
                   min_change: float = 0.05) -> float | None:
        first = int(np.searchsorted(times, start, side="right"))
        last = int(np.searchsorted(times, end, side="right"))
        if first >= len(self.thumbnails):
            return None
        before = self.thumbnails[max(first - 1, 0)].astype(np.int16)
        for i in range(first, min(last, len(self.thumbnails))):
            changed = np.count_nonzero(np.abs(self.thumbnails[i].astype(np.int16) - before) > 24) / before.size
            if changed >= min_change and self.ink[i] >= min_ink:
                return float(times[i])
        return None


class RunAnalyzer:
    def __init__(self, config, scenarios: ScenarioLibrary):
        self.config = config
        self.scenarios = scenarios
        self.references = References(config.workdir)

    def reference_path(self, app_id: str, task_id: str, step_name: str) -> Path:
        return self.references.step(app_id, task_id, step_name)

    def step_params(self, app_scenario, step, reference_run: bool = False) -> SettleParams:
        params = SettleParams.from_dict(self.config.get("settle"), app_scenario.settle, step.settle)
        if reference_run:
            params.quiet_s = params.reference_quiet_s
        return params

    def calibration(self, app_id: str, layout: dict) -> Calibration:
        layout_name = self.config.get("display.layout", "default")
        return Calibration(self.config.workdir / "calibration" / layout_name / f"{app_id}.yaml",
                           Rect.from_dict(layout["app_region"]))

    def analyze_safely(self, run_dir: Path) -> dict:
        try:
            return self.analyze(run_dir)
        except (AnalysisError, VideoError) as ex:
            (Path(run_dir) / "analysis-error.txt").write_text(str(ex))
            result = {"status": "failed", "failure": "technical", "reason": str(ex)}
            (Path(run_dir) / "analysis.json").write_text(json.dumps(result, indent=2))
            return result

    def load_checks(self, meta: dict, scenario, steps, use_references: bool, rects: dict) -> tuple[dict, dict]:
        full_frames, regions = {}, {}
        for step in steps if use_references else []:
            path = self.references.full_frame(meta["app"], meta["task"], step)
            if path is not None:
                if not path.exists():
                    raise AnalysisError(f"No reference image {path} for step '{step.name}': run `bench.py calibrate "
                                        f"references`, or set `expect: none` for this step")
                full_frames[step.name] = np.asarray(Image.open(path).convert("RGB"))
        for step in steps:
            for kind in ("end", "first", "verify"):
                try:
                    found = self.references.regions(meta["app"], meta["task"], step, kind, rects, use_references)
                except KeyError as ex:
                    raise AnalysisError(str(ex)) from ex
                for region in found:
                    if use_references and region.reference is None:
                        path = self.references.region(meta["app"], meta["task"], step.name, kind, region.name)
                        raise AnalysisError(f"No region reference {path}: run `bench.py calibrate references`")
                    regions[(step.name, kind, region.name)] = region
        return full_frames, regions

    def analyze(self, run_dir: Path, reference_run: bool = False) -> dict:
        """reference_run: a calibration run, analyzed with each step's long reference quiet period and without
        reference images (it makes them)."""
        use_references = not reference_run
        run_dir = Path(run_dir)
        meta = json.loads((run_dir / "meta.json").read_text())
        if meta.get("status") not in ("complete", "timeout"):
            raise AnalysisError(f"{run_dir} is not a complete run ({meta.get('status')}: {meta.get('error')})")
        events = EventLog.read(run_dir / "driver.jsonl")
        layout = meta["layout"]
        app_rect = Rect.from_dict(layout["app_in_capture"])
        marker_rect = Rect.from_dict(layout["marker_in_capture"])
        code = MarkerCode(int(layout["marker_cell"]))
        scenario = self.scenarios.get(meta["task"]).for_app(meta["app"])
        steps = self.flow_steps(events) if scenario.flow else [s for s in scenario.steps if s.measure]
        verify = json.loads((run_dir / "verify.json").read_text()) if (run_dir / "verify.json").exists() else None
        list_rect = self.screen_rect(verify, "list_rect", layout)
        count_rect = self.screen_rect(verify, "count_rect", layout)
        params = {s.name: self.step_params(scenario, s, reference_run) for s in steps}
        masks = [Rect.from_dict(m) for m in scenario.masks + list(self.config.get("display.masks") or [])]
        base = SettleParams.from_dict(self.config.get("settle"), scenario.settle)
        rects = self.calibration(meta["app"], layout).region_rects()
        full_frames, checks = self.load_checks(meta, scenario, steps, use_references, rects)
        opening_region = self.opening_region(meta, scenario, rects) if use_references else None
        change_regions = {name for step in steps for name in (r.region for r in step.regions)}
        tracked = [Region(name, rects[name]) for name in change_regions]
        if count_rect is not None:
            tracked.append(Region("count", count_rect))
        keyed = [Region("|".join(key), r.rect, r.reference, r.tolerance, r.pixel_threshold)
                 for key, r in checks.items() if r.reference is not None]
        if opening_region is not None:
            keyed.append(opening_region)
        moving = self.moving_masks(events, layout)
        analyzer = FrameAnalyzer(app_rect.width, app_rect.height, base, masks, full_frames, tracked + keyed,
                                 {name: params[name].reference_pixel_threshold for name in full_frames}, moving)
        rows = ListRows(list_rect) if list_rect is not None else None

        video = VideoFile(run_dir / "capture.mkv", self.config.tool("ffmpeg"), self.config.tool("ffprobe"))
        decoded = video.decoded()
        codes = []
        for frame in decoded.frames():
            codes.append(code.decode(marker_rect.crop(frame)))
            app_frame = app_rect.crop(frame)
            analyzer.add(0.0, app_frame)
            if rows is not None:
                rows.add(app_frame)
        times = np.asarray(decoded.times, dtype=np.float64)
        if len(times) == 0:
            raise AnalysisError(f"{run_dir}: no frames")
        track = MarkerTrack()
        for t, c in zip(times, codes):
            track.add(float(t), c)

        fps = float(self.config.get("capture.fps", 60))
        driver_markers = {e["code"]: e["t"] for e in events if e["type"] == "marker"}
        try:
            fit = ClockFit.fit(driver_markers, track.first_seen, 1.0 / fps)
        except ClockFitError as ex:
            raise AnalysisError(f"{run_dir}: {ex}") from ex
        series = analyzer.series(times, fit.to_video)
        series.save(run_dir / "changes.npz")

        results = []
        waited = 0.0
        first_s = None
        markers_by_label = {}
        for e in events:
            if e["type"] == "marker":
                markers_by_label.setdefault(e["label"], []).append(e["t"])
        end_marker = fit.to_video(markers_by_label["end"][0]) if markers_by_label.get("end") else float(times[-1])
        recording_end = float(times[-1])
        intervals = np.diff(times)
        for n, event in enumerate(events):
            if event["type"] != "step_start" or not event.get("measure", True):
                continue
            name = event["step"]
            step = next(s for s in steps if s.name == name)
            p = params[name]
            start = fit.to_video(event["t"])
            later = [e for e in events[n + 1:] if e["type"] in ("input", "marker", "verify_start")]
            window_end = fit.to_video(later[0].get("t_before", later[0]["t"])) if later else recording_end
            timed_out = any(e["type"] == "step_live_timeout" and e["step"] == name for e in events)
            entry = {"name": name, "start_time": start, "window_end": window_end, "reference": name in full_frames,
                     "regions": [r.region for r in step.regions]}
            if timed_out:
                entry.update({"status": "timeout", "verdict": StepVerdict.timeout, "duration_s": None,
                              "limit_s": next(e["limit_s"] for e in events if e["type"] == "step_live_timeout")})
                results.append(entry)
                break
            end_checks = [checks[(name, "end", r.region)] for r in step.regions
                          if checks.get((name, "end", r.region)) is not None and
                          checks[(name, "end", r.region)].reference is not None]

            def accept(index, step_name=name, regions=end_checks, tol=p.reference_tolerance):
                if step_name in series.reference_distances and series.reference_distances[step_name][index] > tol:
                    return False
                return all(series.region_distances[f"{step_name}|end|{r.name}"][index] <= r.tolerance for r in regions)

            region_names = [r.region for r in step.regions]
            if step.complete == "inbox_listed" and count_rect is not None:
                region_names.append("count")
                entry["regions"] = region_names
            detector = SettleDetector(p, region_names)
            confirmed = next((e.get("confirmed_at") for e in events[n + 1:]
                              if e["type"] == "step_live_settled" and e["step"] == name), None)
            if step.complete:
                if confirmed is None:
                    entry.update({"status": "unconfirmed", "verdict": StepVerdict.technical, "duration_s": None,
                                  "reason": "the app's completion check never confirmed the result"})
                    results.append(entry)
                    break
                gate = fit.to_video(confirmed)
                entry["confirmed_time"] = gate
                check = CompletionGate(series, p, region_names, gate).accept
            else:
                check = accept if (end_checks or name in full_frames) else None
            result = detector.find_end(series, start, window_end, check, late_margin_s=2 / fps if later else 0.0)
            entry.update(result.to_dict())
            verdict, reason = StepVerdict.ok, None
            if result.status == "settled":
                in_window = (times >= start) & (times <= min(window_end, result.end_time + p.quiet_s))
                gaps = intervals[in_window[1:] & in_window[:-1]]
                max_gap = float(gaps.max()) if len(gaps) else 0.0
                entry["max_gap_s"] = max_gap
                if max_gap > p.max_gap_frames / fps or (result.end_uncertainty_s or 0) > 2.0 / fps + 1e-6:
                    verdict, reason = StepVerdict.technical, (f"dropped frames in the measured window (gap "
                                                             f"{max_gap * 1000:.0f} ms)")
                elif result.late_changes and step.after_end == "fail":
                    verdict, reason = StepVerdict.invalid, (f"the screen changed again {result.late_changes} times "
                                                           f"after the measured end")
            elif end_checks and result.status in ("reference-mismatch", "unsettled"):
                found = detector.first_match(series, window_end, recording_end, accept)
                if found is not None:
                    verdict, reason = StepVerdict.technical, ("the live gate moved on before the completion check "
                                                             f"matched (it matched {found - window_end:.1f} s later)")
                else:
                    verdict, reason = StepVerdict.wrong_result, "the completion check never matched"
            elif result.status == "reference-mismatch":
                verdict, reason = StepVerdict.invalid, "the end state differs from the calibration reference"
            else:
                verdict, reason = StepVerdict.technical, f"settle detection: {result.status}"
            first_check = checks.get((name, "first", step.first_visible.region)) if step.first_visible else None
            if first_check is not None and first_check.reference is not None:
                key = f"{name}|first|{step.first_visible.region}"
                first = detector.first_match(series, start, window_end,
                                             lambda i, k=key, t=step.first_visible.tolerance:
                                             series.region_distances[k][i] <= t)
                entry["first_visible_time"] = first
                if first is not None and first_s is None:
                    first_s = waited + first - start
            if step.first_visible_list and rows is not None and first_s is None:
                first = rows.first_rows(times, start, window_end)
                entry["first_visible_time"] = first
                if first is not None:
                    first_s = waited + first - start
            if step.verify_probe and verdict == StepVerdict.ok:
                if verify is None or verify.get("step") != name:
                    verdict, reason = StepVerdict.technical, "no completeness check (verify.json) after the step"
                elif not verify.get("inbox_complete"):
                    verdict, reason = StepVerdict.wrong_result, (
                        f"completeness check failed: {verify.get('listed')} of {verify.get('expected')} listed, "
                        f"oldest message visible: {verify.get('oldest_visible')}"
                        + (f" ({verify['error']})" if verify.get("error") else ""))
            if step.verify and verdict == StepVerdict.ok:
                verify_events = [e for e in events if e["type"] == "verify_start" and e["step"] == name]
                verify_checks = [checks[(name, "verify", r.region)] for r in step.verify.regions
                                 if checks.get((name, "verify", r.region)) is not None and
                                 checks[(name, "verify", r.region)].reference is not None]
                if verify_events and verify_checks:
                    t_verify = fit.to_video(verify_events[0]["t"])
                    matched = detector.first_match(
                        series, t_verify, t_verify + step.verify.within_s,
                        lambda i, regions=verify_checks, s=name: all(
                            series.region_distances[f"{s}|verify|{r.name}"][i] <= r.tolerance for r in regions))
                    entry["verify_matched_after_s"] = None if matched is None else matched - t_verify
                    if matched is None:
                        verdict, reason = StepVerdict.wrong_result, (f"verify check failed: the expected state didn't "
                                                                    f"appear within {step.verify.within_s:.0f} s")
                elif use_references:
                    verdict, reason = StepVerdict.technical, "the verify actions weren't logged"
            entry["verdict"], entry["reason"] = verdict, reason
            if result.duration is not None:
                waited += result.duration
            results.append(entry)

        tail = self.tail_activity(series, events, fit, markers_by_label, base, end_marker)
        opening = self.opening_ranges(series, results, recording_end, opening_region)
        verdicts = [r["verdict"] for r in results]
        if len(results) < len(steps) and StepVerdict.timeout not in verdicts:
            verdicts.append(StepVerdict.technical)
        worst = max(verdicts, key=lambda v: StepVerdict.severity[v]) if verdicts else StepVerdict.technical
        status = {StepVerdict.ok: "ok", StepVerdict.timeout: "timeout", StepVerdict.wrong_result: "wrong-result",
                  StepVerdict.invalid: "invalid", StepVerdict.technical: "failed"}[worst]
        reasons = [f"{r['name']}: {r['reason']}" for r in results if r.get("reason")]
        dropped = int(np.count_nonzero(intervals > 1.5 / fps))
        analysis = {
            "version": 3, "run": meta["run"], "app": meta["app"], "task": meta["task"],
            "comparison": meta["comparison"], "warmup": meta["warmup"], "order": meta.get("order"),
            "attempt": meta.get("attempt", 1), "app_version": meta.get("app_version"),
            "status": status, "failure": "technical" if status == "failed" else None,
            "reason": "; ".join(reasons) or None,
            "total_s": sum(r["duration_s"] for r in results) if status == "ok" else None,
            "censored_at_s": float(meta.get("task_timeout_s") or 0) if status == "timeout" else None,
            "first_s": first_s, "steps": results, "clock_fit": fit.to_dict(), "tail": tail,
            "elapsed_s": (results[-1]["end_time"] - results[0]["start_time"]) if status == "ok" else None,
            "measured_window": {"from_t": fit.to_driver(results[0]["start_time"]),
                                "to_t": fit.to_driver(results[-1].get("end_time") or recording_end)}
            if results else None,
            "flow_path": meta.get("flow_path"), "user_actions": meta.get("user_actions"),
            "verify": {k: verify.get(k) for k in ("method", "inbox_complete", "listed", "expected", "oldest_visible",
                                                  "newest_visible")} if verify else None,
            "opening_ranges": opening,
            "moving_masks": analyzer.schedule_summary,
            "measured_end_utc": self.utc_of(events, fit, results, status),
            "frames": {"count": int(len(times)), "duration_s": float(times[-1] - times[0]),
                       "dropped_intervals": dropped, "max_gap_s": float(intervals.max()) if len(intervals) else 0.0,
                       "mean_fps": float(1 / np.mean(intervals)) if len(intervals) else 0},
            "analyzed": datetime.now(timezone.utc).isoformat(),
        }
        (run_dir / "analysis.json").write_text(json.dumps(analysis, indent=2))
        return analysis

    @staticmethod
    def flow_steps(events: list[dict]) -> list[Step]:
        """The measured steps a flow created at run time, with the checks it logged."""
        turned_final = {e["step"] for e in events if e["type"] == "step_final"}
        steps = [Step.from_checks(e["step"], e.get("checks") or {}) for e in events
                 if e["type"] == "step_start" and e.get("measure", True)]
        return [step.as_final() if step.name in turned_final else step for step in steps]

    @staticmethod
    def moving_masks(events: list[dict], layout: dict) -> MovingMasks | None:
        """The masks over content that changed by itself during the run (driver `mask` lines, screen pixels), in
        app-capture pixels."""
        lines = [e for e in events if e["type"] == "mask"]
        if not lines:
            return None
        app = Rect.from_dict(layout["app_region"])
        changes = [{"t": e["t"], "since_t": e.get("since_t"),
                    "rects": [Rect(int(r["x"]) - app.x, int(r["y"]) - app.y, int(r["w"]), int(r["h"]))
                              for r in e.get("rects") or []]} for e in lines]
        return MovingMasks(changes, app.width, app.height)

    @staticmethod
    def screen_rect(verify: dict | None, key: str, layout: dict) -> Rect | None:
        """A rectangle the probe reported in screen pixels (the message list, the message count), inside the app
        capture. Changes inside the count's rectangle always count, however small (a count going from 2,800 to
        3,000 changes only a few dozen pixels)."""
        rect = (verify or {}).get(key)
        if not rect:
            return None
        app = Rect.from_dict(layout["app_region"])
        x, y = int(rect["x"]) - app.x, int(rect["y"]) - app.y
        width = min(int(rect["w"]), app.width - x)
        height = min(int(rect["h"]), app.height - y)
        return Rect(max(0, x), max(0, y), width, height) if width > 2 and height > 2 else None

    def opening_region(self, meta: dict, scenario, rects: dict) -> Region | None:
        check = scenario.opening_screen
        if check is None:
            return None
        if check.region not in rects:
            raise AnalysisError(f"Region '{check.region}' (opening screen) is not calibrated")
        path = self.references.opening(meta["app"], meta["task"], check.region)
        if not path.exists():
            raise AnalysisError(f"No opening-screen reference {path}: make it with `bench.py calibrate crop`")
        return Region("opening", rects[check.region], np.asarray(Image.open(path).convert("RGB")), check.tolerance,
                      check.pixel_threshold)

    @staticmethod
    def opening_ranges(series, results: list[dict], recording_end: float, region: Region | None) -> list:
        if region is None or "opening" not in series.region_distances or not results:
            return []
        start = results[0]["start_time"]
        matched = (series.region_distances["opening"] <= region.tolerance) & (series.times >= start) & \
            (series.times <= recording_end)
        ranges, begin = [], None
        for i, flag in enumerate(matched):
            if flag and begin is None:
                begin = float(series.times[i])
            elif not flag and begin is not None:
                ranges.append([begin, float(series.times[i])])
                begin = None
        if begin is not None:
            ranges.append([begin, recording_end])
        return ranges

    @staticmethod
    def utc_of(events: list[dict], fit: ClockFit, results: list[dict], status: str) -> float | None:
        offset = EventLog.utc_offset(events)
        if offset is None or status != "ok" or not results or results[-1].get("end_time") is None:
            return None
        return fit.to_driver(results[-1]["end_time"]) + offset

    @staticmethod
    def tail_activity(series, events, fit, markers_by_label: dict, params: SettleParams, end_marker: float) -> dict:
        if not markers_by_label.get("tail-end"):
            return {"recorded_s": 0.0}
        tail_end = fit.to_video(markers_by_label["tail-end"][0])
        window = (series.times > end_marker + 0.7) & (series.times < tail_end)
        significant = series.significant(params) & window
        indexes = np.flatnonzero(significant)
        return {"recorded_s": round(tail_end - end_marker, 3), "significant_frames": int(len(indexes)),
                "last_change_after_s": None if not len(indexes) else round(float(series.times[indexes[-1]]) - end_marker, 3)}


class Aggregator:
    def __init__(self, config, scenarios: ScenarioLibrary, folder=None):
        self.config = config
        self.scenarios = scenarios
        self.folder = folder

    def run_counts(self) -> dict:
        """The session's planned run counts (the result folder's manifest), else the config's."""
        planned = (self.folder.manifest().get("runs") if self.folder is not None else None) or {}
        return {"measured": int(planned.get("measured", self.config.get("runs.measured", 5))),
                "warmup": int(planned.get("warmup", self.config.get("runs.warmup", 1)))}

    def run_dirs(self, comparison: str, task: str, app: str) -> list[Path]:
        if self.folder is not None:
            return [p for p in self.folder.run_dirs(app, task) if p.name != "reference"]
        root = self.config.workdir / "runs" / self.config.run_group(comparison) / task / app
        if not root.exists():
            return []
        return sorted(p for p in root.glob("*") if (p / "meta.json").exists() and p.name != "reference"
                      and ".failed-" not in p.name)

    def failed_attempts(self, comparison: str, task: str, app: str) -> list[dict]:
        """The failed attempts of runs recorded again, for the evidence of every run (not for the times)."""
        if self.folder is not None:
            dirs = self.folder.failed_attempt_dirs(app, task)
        else:
            root = self.config.workdir / "runs" / self.config.run_group(comparison) / task / app
            dirs = sorted(p for p in root.glob("*.failed-*") if (p / "meta.json").exists()) if root.exists() else []
        return [{**self.run_entry(d), "run": d.name} for d in dirs]

    @staticmethod
    def median_run(runs: list[dict], median: float | None = None) -> dict:
        """The run whose total is the median (of all measured runs, timeouts included, when given)."""
        median = statistics.median([r["total_s"] for r in runs]) if median is None else median
        return min(runs, key=lambda r: (abs(r["total_s"] - median), r["order"] or 0))

    @staticmethod
    def censored_median(values: list[float | None]) -> tuple[float | None, bool]:
        """Median where None means "not done within the limit" (larger than every measured value)."""
        ordered = sorted(values, key=lambda v: (v is None, v or 0))
        n = len(ordered)
        if n == 0:
            return None, False
        middle = ordered[(n - 1) // 2: n // 2 + 1]
        if any(v is None for v in middle):
            return None, True
        return statistics.median(middle), False

    def run_entry(self, run_dir: Path) -> dict:
        meta = json.loads((run_dir / "meta.json").read_text())
        analysis_path = run_dir / "analysis.json"
        analysis = json.loads(analysis_path.read_text()) if analysis_path.exists() else None
        status = analysis["status"] if analysis else ("failed" if meta.get("status") == "failed" else "not analyzed")
        failed_attempts = sorted(p.name for p in run_dir.parent.glob(f"{run_dir.name}.failed-*"))
        evidence_path = run_dir / "evidence.json"
        server_evidence_path = run_dir / "server-evidence.json"
        account_path = run_dir / "account.json"
        account = json.loads(account_path.read_text()) if account_path.exists() else None
        pressure_path = run_dir / "cpu-pressure.json"
        pressure = json.loads(pressure_path.read_text()) if pressure_path.exists() else None
        reason = (analysis or {}).get("reason") or meta.get("error")
        if pressure and pressure.get("over_limit") and status in ("ok", "timeout", "wrong-result"):
            status, reason = "failed", (f"technical: CPU stall {pressure['pct']:.1f} % during the "
                                        f"{pressure['basis']} (limit {pressure['limit_pct']:g} %)")
        return {"run": meta["run"], "order": meta.get("order"), "attempt": meta.get("attempt", 1),
                "warmup": bool(meta.get("warmup")), "status": status, "reason": reason,
                "cpu_pressure": pressure,
                "total_s": (analysis or {}).get("total_s"), "first_s": (analysis or {}).get("first_s"),
                "censored_at_s": (analysis or {}).get("censored_at_s"),
                "steps": {s["name"]: s.get("duration_s") for s in (analysis or {}).get("steps", [])},
                "tail": (analysis or {}).get("tail"), "app_version": meta.get("app_version"),
                "closed_cleanly": meta.get("closed_cleanly"), "re_recorded_after": failed_attempts,
                "measured_end_utc": (analysis or {}).get("measured_end_utc"),
                "evidence": json.loads(evidence_path.read_text()) if evidence_path.exists() else None,
                "server_evidence": json.loads(server_evidence_path.read_text()) if server_evidence_path.exists()
                else None, "evidence_error": meta.get("evidence_error"),
                "elapsed_s": (analysis or {}).get("elapsed_s"), "flow_path": meta.get("flow_path"),
                "user_actions": meta.get("user_actions"), "action_list": meta.get("action_list"),
                "prepare_actions": meta.get("prepare_actions"), "inbox_complete": meta.get("inbox_complete"),
                "preparations": meta.get("preparations"),
                "account_repairs": (account or {}).get("repairs") if account else None,
                "moving_mask_changes": ((analysis or {}).get("moving_masks") or {}).get("changes"),
                "dir": self.folder.relative(run_dir) if self.folder is not None else str(run_dir)}

    def side(self, comparison: str, task: str, app_id: str) -> dict:
        app = self.config.app(app_id)
        scenario = self.scenarios.get(task)
        app_scenario = scenario.for_app(app_id)
        measured_count = self.run_counts()["measured"]
        entries = [self.run_entry(d) for d in self.run_dirs(comparison, task, app_id)]
        warmups = [e for e in entries if e["warmup"]]
        measured = sorted((e for e in entries if not e["warmup"]), key=lambda e: e["order"] or 0)
        ok = [e for e in measured if e["status"] == "ok"]
        timeouts = [e for e in measured if e["status"] == "timeout"]
        wrong = [e for e in measured if e["status"] == "wrong-result"]
        versions = sorted({str(e["app_version"]) for e in measured if e["app_version"]})
        side = {"app": app_id, "name": app.get("name", app_id), "version": app.get("version"),
                "protocol": app.get("protocol"), "os": app.get("os"),
                "actions": app_scenario.user_action_count, "action_list": app_scenario.action_list,
                "flow": app_scenario.flow.get("name") if app_scenario.flow else None,
                "microsoft_ui": bool(app.get("microsoft_ui")), "cloud_sync": bool(app.get("cloud_sync")),
                "runs": measured, "warmups": warmups, "warmups_discarded": [e["run"] for e in warmups],
                "failed_attempts": self.failed_attempts(comparison, task, app_id),
                "runs_app_killed_at_close": [e["run"] for e in entries if e["closed_cleanly"] is False],
                "failed_runs": [{"run": e["run"], "reason": f"{e['status']}: {e['reason']}"}
                                for e in measured if e["status"] not in ("ok", "timeout")],
                "re_recorded": [{"run": e["run"], "failed_attempts": e["re_recorded_after"]}
                                for e in entries if e["re_recorded_after"]],
                "timeout_s": float(scenario.timeout_s or self.config.get("settle.task_timeout_s", 7200)),
                "versions_seen": versions, "measured_runs": len(ok), "timed_out_runs": len(timeouts),
                "settle": self.effective_settle(app_scenario)}
        if versions:
            side["version"] = versions[-1] if len(versions) == 1 else side["version"]
        values = [e["total_s"] for e in ok] + [None] * len(timeouts)
        median, censored = self.censored_median(values)
        reason = None
        if wrong:
            status, reason = 3, "; ".join(f"{e['run']}: {e['reason']}" for e in wrong)
        elif len(versions) > 1:
            status, reason = 1, f"the app version changed during the series: {', '.join(versions)}"
        elif len(values) < measured_count:
            status = 1
            reason = (f"{len(values)} of {measured_count} measured runs valid or timed out; failed: " +
                      "; ".join(f"{f['run']} ({f['reason']})" for f in side["failed_runs"]) if side["failed_runs"]
                      else f"only {len(values)} of {measured_count} measured runs recorded")
        elif censored:
            status, reason = 2, f"not done within {side['timeout_s']:.0f} s in {len(timeouts)} of {len(values)} runs"
        else:
            status = 0
        side["status"] = status
        side["status_reason"] = reason
        valid = status == 0
        side["median_s"] = median if valid else None
        side["min_s"] = min(v for v in values if v is not None) if valid and ok else None
        side["max_s"] = (side["timeout_s"] if timeouts else max(e["total_s"] for e in ok)) if valid and ok else None
        side["max_censored"] = bool(timeouts) and valid
        chosen = self.median_run(ok, median) if valid and ok else None
        side["median_run"] = chosen["run"] if chosen else None
        side["median_run_s"] = chosen["total_s"] if chosen else None
        firsts = [e["first_s"] for e in ok if e["first_s"] is not None]
        side["first_s"] = {"median_s": statistics.median(firsts), "min_s": min(firsts), "max_s": max(firsts),
                           "runs": len(firsts)} if firsts else None
        if app_scenario.flow:
            self.flow_actions(side, chosen, ok or measured)
        elapsed = [e["elapsed_s"] for e in ok if e.get("elapsed_s") is not None]
        side["elapsed_s"] = {"median_s": statistics.median(elapsed), "min_s": min(elapsed), "max_s": max(elapsed)} \
            if elapsed and valid else None
        side["steps"] = {}
        step_names = [s.name for s in app_scenario.steps if s.measure] or \
            list(dict.fromkeys(name for e in ok for name in e["steps"]))
        for step in step_names:
            step_values = [e["steps"].get(step) for e in ok if e["steps"].get(step) is not None]
            if step_values:
                side["steps"][step] = {"median_s": statistics.median(step_values), "min_s": min(step_values),
                                       "max_s": max(step_values)}
        if status == 2:
            side["median_run"] = None
        side["timeout_run"] = timeouts[len(timeouts) // 2]["run"] if status == 2 and timeouts else None
        return side

    @staticmethod
    def flow_actions(side: dict, chosen: dict | None, runs: list[dict]):
        """A flow's user actions come from the recorded runs (each app's own setup path, e.g. autoconfig or manual);
        the published count is the median run's, and differing runs are listed."""
        reference = chosen or next((r for r in runs if r.get("user_actions") is not None), None)
        if reference is None:
            return
        side["actions"] = reference.get("user_actions")
        side["action_list"] = reference.get("action_list") or []
        side["prepare_actions"] = reference.get("prepare_actions") or []
        side["flow_path"] = reference.get("flow_path") or []
        differing = {r["run"]: r.get("user_actions") for r in runs if r.get("user_actions") != side["actions"]}
        if differing:
            side["actions_differ"] = differing

    def effective_settle(self, app_scenario) -> dict:
        out = {"masks": list(app_scenario.masks) + list(self.config.get("display.masks") or []), "steps": {}}
        for step in app_scenario.steps:
            if step.measure:
                params = SettleParams.from_dict(self.config.get("settle"), app_scenario.settle, step.settle)
                out["steps"][step.name] = {
                    "params": vars(params), "reference": step.expect,
                    "regions": [vars(r) for r in step.regions],
                    "first_visible": vars(step.first_visible) if step.first_visible else None,
                    "verify": {"actions": [a.describe() for a in step.verify.actions],
                               "regions": [vars(r) for r in step.verify.regions],
                               "within_s": step.verify.within_s} if step.verify else None,
                    "after_end": step.after_end}
        return out

    def comparison(self, comparison_id: str, tasks: list[str] | None = None) -> dict:
        spec = self.config.comparison(comparison_id)
        out_tasks = {}
        for task in tasks or spec["tasks"]:
            scenario = self.scenarios.get(task)
            left = self.side(comparison_id, task, spec["left"])
            right = self.side(comparison_id, task, spec["right"])
            ratio = None
            if left["median_s"] and right["median_s"] is not None:
                ratio = right["median_s"] / left["median_s"]
            out_tasks[task] = {"title": scenario.title, "description": scenario.description,
                               "left": left, "right": right, "ratio": ratio}
        return {"os": spec.get("os"), "left": spec["left"], "right": spec["right"], "tasks": out_tasks,
                "runs": self.run_counts(),
                "settle": vars(SettleParams.from_dict(self.config.get("settle")))}


class ReportWriter:
    def __init__(self, results: dict, deviations: list[str], procedures: list[str] | None = None,
                 instrumentation: list[str] | None = None):
        self.results = results
        self.deviations = deviations
        self.procedures = procedures or []
        self.instrumentation = instrumentation or []

    @staticmethod
    def seconds(value) -> str:
        return "–" if value is None else f"{value:.2f} s"

    status_text = {0: "valid median", 1: "no valid median", 2: "time limit reached", 3: "result differs"}

    def run_line(self, run: dict) -> str:
        if run["status"] == "ok":
            value = f"{run['total_s']:.3f} s"
        elif run["status"] == "timeout":
            value = f"not done within {run['censored_at_s']:.0f} s"
        else:
            value = f"{run['status']} ({run['reason']})"
        extra = f", attempt {run['attempt']}" if run.get("attempt", 1) > 1 else ""
        pressure = run.get("cpu_pressure")
        if pressure:
            value += f"; CPU stall {pressure['pct']:.1f} %"
            if pressure.get("loadavg_start") and pressure.get("loadavg_end"):
                value += f", load {pressure['loadavg_start'][0]:.1f} → {pressure['loadavg_end'][0]:.1f}"
        return f"{run['run']} (#{run['order']}{extra}): {value}"

    def write(self, path: Path):
        r = self.results
        account_mode = r.get("server_mode", "account") == "account"
        lines = ["# Speed benchmark report", "",
                 f"Generated {r['generated']}. Median of {r['runs']['measured']} measured runs per app and task, "
                 f"after {r['runs']['warmup']} discarded warm-up run(s) each.", "",
                 "## Method", "",
                 "- Same computer, OS, display resolution, window size, network"
                 + (", server and test account" if account_mode else " and server snapshot") + " for both apps.",
                 "- Apps recorded one after another, never at the same time; run order interleaved (A B A B …). A run "
                 "that failed for a technical reason is recorded again at the end of the series (listed below); "
                 "timeouts and differing results are never recorded again.",
                 ("- Before every run the test account was checked against the corpus (every message by its "
                  "Message-ID, folder and flags) and repaired over IMAP where an earlier run had changed it; every "
                  "run starts with a fresh app profile." if account_mode else
                  "- Server and client state restored from the same snapshot before every run."),
                 "- Screen recording (lossless, 60 fps) runs during every measured run of every app; ffmpeg pinned "
                 "to its own CPU core where the OS allows it. The mouse pointer is moved out of the recorded area "
                 "after every click and not recorded.",
                 "- A step starts at the logged input event (mapped onto the video by sync markers and a linear fit) "
                 "and ends at the last significant screen change before a quiet period, at a frame that passes the "
                 "step's completion checks; see the settle parameters below.",
                 "- A run that reaches the time limit counts as \"not done within the limit\" in the median.",
                 "- The video shows the median run, synchronized at the start of each task.", "",
                 "## Deviations from default settings", ""]
        lines += [f"- {d}" for d in self.deviations] or ["- none"]
        if self.instrumentation:
            lines += ["", "## Instrumentation", ""] + [f"- {i}" for i in self.instrumentation]
        if self.procedures:
            lines += ["", "## Procedure notes", ""] + [f"- {p}" for p in self.procedures]
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
                cells = []
                for side in (t["left"], t["right"]):
                    if side["status"]:
                        cells += [self.status_text[side["status"]], "–"]
                    else:
                        top = f"≥ {side['max_s']:.0f} s" if side.get("max_censored") else self.seconds(side["max_s"])
                        cells += [self.seconds(side["median_s"]), f"{self.seconds(side['min_s'])}–{top}"]
                    cells.append(str(side["actions"]))
                ratio = "–" if t["ratio"] is None else f"{t['ratio']:.2f}"
                lines.append(f"| {task_id} {t['title'].get('en', '')} | " + " | ".join(cells) + f" | {ratio} |")
            lines.append("")
            for task_id, t in comparison["tasks"].items():
                lines.append(f"### {comparison_id} {task_id}: {t['title'].get('en', '')}")
                for side_name in ("left", "right"):
                    s = t[side_name]
                    lines.append(f"- **{s['name']}** ({s['protocol']}): actions: " + "; ".join(s["action_list"]))
                    if s.get("flow_path"):
                        lines.append("  - setup path: " + "; ".join(s["flow_path"]))
                    if s.get("prepare_actions"):
                        lines.append("  - not counted (benchmark preparation): " + "; ".join(s["prepare_actions"]))
                    preparations = sorted({p for x in s["runs"] for p in x.get("preparations") or []})
                    if preparations:
                        lines.append("  - before the setup: " + "; ".join(preparations))
                    if s.get("actions_differ"):
                        lines.append(f"  - runs with another action count: {s['actions_differ']}")
                    if s.get("elapsed_s"):
                        e = s["elapsed_s"]
                        lines.append(f"  - wall-clock time from the first submit to the measured end (incl. the "
                                     f"driver's reaction time between steps): median {self.seconds(e['median_s'])} "
                                     f"(min {self.seconds(e['min_s'])}, max {self.seconds(e['max_s'])})")
                    repairs = [f"{x['run']}: " + ", ".join(f"{p['what']} ({p.get('count', p.get('folder', ''))})"
                                                         for p in x["account_repairs"])
                               for x in s["runs"] if x.get("account_repairs")]
                    if repairs:
                        lines.append("  - account repaired before: " + "; ".join(repairs))
                    lines.append(f"  - status: {s['status']} ({self.status_text[s['status']]})"
                                 + (f": {s['status_reason']}" if s.get("status_reason") else ""))
                    lines.append("  - measured runs in run order: " + "; ".join(self.run_line(x) for x in s["runs"])
                                 + (f"; median run shown: {s['median_run']}" if s["median_run"] else ""))
                    if s.get("first_s"):
                        f = s["first_s"]
                        lines.append(f"  - first messages visible: median {self.seconds(f['median_s'])} "
                                     f"(min {self.seconds(f['min_s'])}, max {self.seconds(f['max_s'])})")
                    for step, v in (s.get("steps") or {}).items():
                        lines.append(f"  - step {step}: median {self.seconds(v['median_s'])}, "
                                     f"min {self.seconds(v['min_s'])}, max {self.seconds(v['max_s'])}")
                    for step, info in (s.get("settle") or {}).get("steps", {}).items():
                        checks = [f"regions {', '.join(c['region'] for c in info['regions'])}" if info["regions"] else "",
                                  f"reference {info['reference']}" if info["reference"] else "",
                                  "verify: " + ", ".join(info["verify"]["actions"]) if info.get("verify") else ""]
                        lines.append(f"  - settle {step}: quiet {info['params']['quiet_s']} s, min "
                                     f"{info['params']['min_changed_pixels']} px; "
                                     + "; ".join(c for c in checks if c))
                    if (s.get("settle") or {}).get("masks"):
                        lines.append(f"  - masked regions: {s['settle']['masks']}")
                    masked = [x for x in s["runs"] if x.get("moving_mask_changes")]
                    if masked:
                        changes = sorted({x["moving_mask_changes"] for x in masked})
                        times = str(changes[0]) if len(changes) == 1 else f"{changes[0]}–{changes[-1]}"
                        lines.append(f"  - content that changes by itself (the setup's background video) left out of "
                                     f"the change detection in {len(masked)} of {len(s['runs'])} runs; its visible "
                                     f"area changed {times} times per run (see deviations)")
                    if s.get("re_recorded"):
                        lines.append("  - re-recorded at the end of the series after a technical failure: " + ", ".join(
                            f"{x['run']} ({', '.join(x['failed_attempts'])})" for x in s["re_recorded"]))
                    if s.get("runs_app_killed_at_close"):
                        lines.append("  - app didn't quit by itself after these runs and was killed (check for "
                                     "unexpected dialogs): " + ", ".join(s["runs_app_killed_at_close"]))
                    if s["warmups_discarded"]:
                        lines.append("  - warm-up runs discarded: " + ", ".join(s["warmups_discarded"]))
                    after = [x["tail"] for x in s["runs"] if x.get("tail") and x["tail"].get("recorded_s")]
                    if after:
                        lines.append("  - after the measured end (recorded tail): " + "; ".join(
                            f"{a['significant_frames']} changing frames, last {a['last_change_after_s']} s after"
                            for a in after))
                lines.append("")
            evidence = comparison.get("evidence")
            if evidence:
                kind = "network evidence (client side)" if evidence.get("kind") == "client" else "server log evidence"
                lines += [f"### {comparison_id}: {kind}", ""]
                lines += [f"- {line}" for line in evidence.get("lines", [])]
                lines.append("")
            server_evidence = comparison.get("server_evidence")
            if server_evidence:
                lines += [f"### {comparison_id}: server log evidence", ""]
                lines += [f"- {line}" for line in server_evidence.get("lines", [])]
                lines.append("")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
