import json
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .analyze import Aggregator, ReportWriter, RunAnalyzer
from .compose import Composer, ShortSettings, ValuesBuilder
from .config import ConfigError
from .corpus import CorpusGenerator, CorpusSpec
from .driver import AppProcess, Calibration, EventLog, ScenarioDriver
from .encode import EncodeError, Encoder
from .environment import EnvironmentProbe
from .method import MethodTexts
from .narration import Narration
from .references import References
from .runner import Desktops, Orchestrator, RunExecutor
from .scenario import ScenarioLibrary
from .seed import Seeder
from .serverlog import EvidenceSummary, ServerLog
from .settle import Rect
from .snapshot import ClientProfiles, CommandRunner, ProtocolSnapshot, ServerReadiness, SnapshotError, StorageSnapshot
from .speech import SpeechEngine, VoiceSynthesizer
from .verify import OutputVerifier
from .video import VideoFile


class NarrationFiles:
    """Finds a variant's narration, its segment list and the short-video settings in the voice-over's directory
    layout: `<dir>/narration.<lang>.json`, `<dir>/variants/{variants.json, compose.json, narration.<lang>.<v>.json}`,
    `<dir>/method/`."""

    def __init__(self, narration: str | None, language: str, variant: str | None):
        self.language = language
        self.variant = variant
        self.path = None
        self.root = None
        if not narration:
            return
        path = Path(narration)
        self.root = path if path.is_dir() else (path.parent.parent if path.parent.name == "variants" else path.parent)
        candidate = self.root / "variants" / f"narration.{language}.{variant}.json" if variant else None
        if path.is_dir():
            self.path = candidate if candidate and candidate.exists() else self.root / f"narration.{language}.json"
        else:
            self.path = path
        if not self.path.exists():
            raise ConfigError(f"No narration file {self.path}")

    def segment_ids(self) -> list[str] | None:
        if not self.variant or not self.root:
            return None
        for base in (self.root / "variants", self.root):
            if (base / "variants.json").exists():
                variants = json.loads((base / "variants.json").read_text())
                if self.variant not in variants:
                    raise ConfigError(f"Unknown variant '{self.variant}'. Known: {', '.join(variants)}")
                return variants[self.variant]
        raise ConfigError(f"No variants.json in {self.root}")

    def settings(self, config_compose: dict) -> ShortSettings:
        return ShortSettings.find(self.root, config_compose)

    def method_dir(self) -> Path | None:
        return self.root / "method" if self.root else None


class Pipeline:
    def __init__(self, config, progress=print):
        self.config = config
        self.progress = progress
        self.scenarios = ScenarioLibrary(config.scenario_dir)
        self._desktop = None
        self._server_log = None

    @property
    def desktop(self):
        if self._desktop is None:
            self._desktop = Desktops.create(self.config)
        return self._desktop

    def server_snapshots(self):
        spec = self.config.get("server.snapshot") or {}
        method = spec.get("method", "storage")
        if method == "none":
            return None
        if method == "protocol":
            return ProtocolSnapshot(Seeder(self.config, self.progress))
        ready = ServerReadiness(self.config.require("server.jmap_session_url"), self.config.get("server.imap.host"),
                                int(self.config.get("server.imap.port", 993)))
        return StorageSnapshot(spec, CommandRunner(spec.get("ssh"), spec.get("ssh_options")), ready)

    @property
    def server_log(self) -> ServerLog | None:
        if self._server_log is None and self.config.get("server.log.path"):
            ssh = self.config.get("server.log.ssh", self.config.get("server.snapshot.ssh"))
            self._server_log = ServerLog(self.config, CommandRunner(ssh, self.config.get("server.snapshot.ssh_options")),
                                         self.progress)
        return self._server_log

    def app_version(self, app_id: str) -> str | None:
        return EnvironmentProbe(self.config).app_version(app_id).get("version")

    def executor(self) -> RunExecutor:
        return RunExecutor(self.config, self.desktop, self.scenarios, self.server_snapshots(),
                           ClientProfiles(self.config), self.progress, self.server_log, self.app_version)

    def corpus_facts(self) -> dict:
        generator = CorpusGenerator(CorpusSpec.from_dict(self.config.get("corpus")))
        expected = generator.expected()
        facts = self.config.get("corpus_facts") or {}
        folders = expected["folders"]
        archive = next((n for n, f in folders.items() if f["role"] == "archive"), None)
        inbox = next((n for n, f in folders.items() if f["role"] == "inbox"), None)
        move = facts.get("move_folder", "Projects/Move-me")
        term = facts.get("search_term") or next(iter(expected["planted"]), None)
        return {"profile": expected["profile"], "messages": expected["total"],
                "inbox_messages": folders[inbox]["count"] if inbox else None,
                "attachment_messages": expected["attachment_messages"],
                "attachment_bytes": expected["attachment_size"],
                "archive_messages": folders[archive]["count"] if archive and folders[archive]["count"] else None,
                "move_messages": folders.get(move, {}).get("count"),
                "search_hits": expected["planted"][term]["count"] if term in expected["planted"] else None}

    def environment_path(self, comparison_id: str) -> Path:
        return self.config.workdir / "results" / f"environment-{self.config.run_group(comparison_id)}.json"

    def environment(self, comparison_id: str) -> dict:
        spec = self.config.comparison(comparison_id)
        env = EnvironmentProbe(self.config, self.desktop).collect(self.config.group_apps(comparison_id))
        env.update(spec.get("environment") or {})
        path = self.environment_path(comparison_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(env, indent=2))
        return env

    def run(self, comparison_id: str, tasks: list[str] | None, resume: bool, measured: int | None,
            warmup: int | None):
        if not self.environment_path(comparison_id).exists():
            self.environment(comparison_id)
        if self.server_log is not None:
            self.progress(f"benchmark computer as the server sees it: {', '.join(sorted(self.server_log.probe()))}")
        analyzer = RunAnalyzer(self.config, self.scenarios) if self.config.get("runs.analyze_after_each", True) else None
        Orchestrator(self.config, self.executor(), self.progress, analyzer).run_comparison(
            comparison_id, tasks, resume, measured, warmup)

    def analyze(self, comparison_id: str, force: bool = False) -> dict:
        analyzer = RunAnalyzer(self.config, self.scenarios)
        root = self.config.workdir / "runs" / self.config.run_group(comparison_id)
        for meta_path in sorted(root.glob("*/*/*/meta.json")):
            run_dir = meta_path.parent
            if run_dir.name == "reference" or ".failed-" in run_dir.name:
                continue
            meta = json.loads(meta_path.read_text())
            if meta.get("status") not in ("complete", "timeout") or (not force and (run_dir / "analysis.json").exists()):
                continue
            result = analyzer.analyze_safely(run_dir)
            self.progress(f"  {run_dir.relative_to(self.config.workdir)}: {result['status']} "
                          + (f"{result['total_s']:.3f} s" if result.get("total_s") is not None else "")
                          + (f" ({result['reason']})" if result.get("reason") else ""))
        results = None
        for comparison in self.config.group_comparisons(comparison_id):
            results = self.write_results(comparison)
        return results

    def results_path(self) -> Path:
        return self.config.workdir / "results" / "results.json"

    def facts(self, results_dir: Path) -> dict:
        """Person-set facts (never from the measurement): `results/facts.json`, created as a template."""
        path = results_dir / "facts.json"
        if not path.exists():
            template = {"_help": "Set by a person after checking the recordings; 1 = confirmed. Never filled in by "
                                 "the pipeline. See README, 'Facts set by a person'.",
                        **{c: {"right_protocol_default": None} for c in self.config.get("comparisons", {})}}
            if "C4" in template:
                template["C4"].update({"cloud_sync_confirmed": None, "dialog_text": None, "microsoft_footage": None})
            path.write_text(json.dumps(template, indent=2, ensure_ascii=False))
        return json.loads(path.read_text())

    def evidence(self, comparison_id: str, comparison: dict) -> dict | None:
        task_id = self.config.get("server.log.evidence_task", "T1")
        task = comparison["tasks"].get(task_id) or next(iter(comparison["tasks"].values()), None)
        if task is None or not any(r.get("evidence") for side in ("left", "right") for r in task[side]["runs"]):
            return None
        task_id = next(t for t, v in comparison["tasks"].items() if v is task)
        cloud = {side for side in ("left", "right") if self.config.app(comparison[side]).get("cloud_sync")}
        summary = EvidenceSummary(comparison_id, task_id, {s: task[s] for s in ("left", "right")}, cloud).compute()
        watch = [self.watch_minutes(comparison[side]) for side in cloud]
        if watch and watch[0]:
            summary["values"]["removal_watch_min"] = watch[0]
        return summary

    def watch_minutes(self, app_id: str) -> float | None:
        for scenario_file in sorted(self.config.scenario_dir.glob("T*.yaml")):
            scenario = self.scenarios.get(scenario_file.stem)
            if app_id in scenario.apps:
                for action in scenario.for_app(app_id).finish:
                    if action.kind == "wait_cloud_quiet" and action.options.get("watch", "logins") == "logins":
                        return float(action.options.get("minutes", action.arg or 10))
        return None

    def write_results(self, comparison_id: str) -> dict:
        path = self.results_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        results = json.loads(path.read_text()) if path.exists() else {"version": 2, "comparisons": {},
                                                                       "environment": {}}
        comparison = Aggregator(self.config, self.scenarios).comparison(comparison_id)
        comparison["evidence"] = self.evidence(comparison_id, comparison)
        comparison["corpus"] = self.corpus_facts()
        results["comparisons"][comparison_id] = comparison
        env_path = self.environment_path(comparison_id)
        if env_path.exists():
            env = json.loads(env_path.read_text())
            for side in ("left", "right"):
                app = env.get("apps", {}).get(comparison[side], {})
                for task in comparison["tasks"].values():
                    if app.get("version") and not task[side].get("versions_seen"):
                        task[side]["version"] = app["version"]
            results["environment"][comparison_id] = env
        results["runs"] = comparison["runs"]
        results["settle"] = comparison["settle"]
        results["corpus"] = comparison["corpus"]
        results["facts"] = self.facts(path.parent)
        results["generated"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        ReportWriter(results, self.deviations("en"), list(self.config.get("procedures") or [])).write(
            path.parent / "report.md")
        return results

    def deviations(self, language: str) -> list[str]:
        deviations = self.config.get("deviations") or []
        return deviations.get(language) or deviations.get("en") or [] if isinstance(deviations, dict) else deviations

    def merged_results(self, results_paths: list[str] | None) -> dict:
        paths = [Path(p) for p in results_paths] if results_paths else [self.results_path()]
        merged = None
        for path in paths:
            data = json.loads(path.read_text())
            data["facts"] = {**(data.get("facts") or {}), **self.facts(path.parent)}
            if merged is None:
                merged = data
                continue
            for key in ("runs", "corpus"):
                if data.get(key) != merged.get(key):
                    raise ConfigError(f"{path}: '{key}' differs from {paths[0]} ({data.get(key)} vs "
                                      f"{merged.get(key)}); results of different setups can't share one video")
            merged["comparisons"].update(data["comparisons"])
            merged["environment"].update(data.get("environment") or {})
            merged["facts"].update(data["facts"])
        return merged

    def compose(self, comparisons: list[str] | None, language: str, narration_path: str | None,
                variant: str | None, name: str, results_paths: list[str] | None = None) -> dict:
        results = self.merged_results(results_paths)
        files = NarrationFiles(narration_path, language, variant)
        narration = Narration.load(files.path) if files.path else None
        settings = files.settings(self.config.get("compose") or {})
        out_dir = self.config.workdir / "compose" / f"{name}-{language}"
        out_dir.mkdir(parents=True, exist_ok=True)
        composer = Composer(self.config, results, out_dir, language, narration, files.segment_ids(), comparisons,
                            self.progress, settings, results.get("facts"), variant)
        return composer.compose()

    def method(self, comparisons: list[str] | None, language: str, narration_path: str, variant: str, name: str,
               results_paths: list[str] | None = None, allow_missing: bool = False) -> dict:
        results = self.merged_results(results_paths)
        files = NarrationFiles(narration_path, language, variant)
        values = ValuesBuilder(self.config, results, language, results.get("facts") or {}).build()
        compose = self.config.get("compose") or {}
        voice_dir = self.config.path(compose["voice_dir"]) if compose.get("voice_dir") else None
        texts = MethodTexts(self.config, results, values, language, voice_dir)
        out_dir = self.config.workdir / "compose" / f"{name}-{language}" / "method"
        return texts.render(files.method_dir(), variant, out_dir, comparisons or list(results["comparisons"]),
                            allow_missing)

    def voice(self, name: str, language: str, replace: bool = False) -> dict:
        out_dir = self.config.workdir / "compose" / f"{name}-{language}"
        script = json.loads((out_dir / "voice-script.json").read_text())
        compose = self.config.get("compose") or {}
        if not compose.get("voice_dir"):
            raise ConfigError("Set compose.voice_dir for the synthesized voice files")
        engine = SpeechEngine.create(self.config, language)
        return VoiceSynthesizer(engine, self.config.path(compose["voice_dir"]), language, self.progress).run(
            script, replace)

    def encode(self, name: str, language: str, formats: list[str] | None, internal_preview: bool = False) -> dict:
        out_dir = self.config.workdir / "compose" / f"{name}-{language}"
        timeline = json.loads((out_dir / "timeline.json").read_text())
        publication = timeline.get("publication") or {}
        watermark = None
        if not publication.get("allowed", True):
            if not internal_preview:
                instead = ", ".join(publication.get("instead") or []) or "none of its fallbacks " + \
                    f"({', '.join(publication.get('chain') or []) or 'none listed'})"
                raise EncodeError(f"Variant {publication.get('variant')} must not be published: its condition "
                                  f"'{publication.get('publish_when')}' is false. Publish instead: {instead}. "
                                  f"(--internal-preview encodes it with an on-screen 'not for publication' mark.)")
            watermark = Composer.texts.get(language, Composer.texts["en"])["preview"]
        encoder = Encoder(self.config, out_dir / "master.mkv", timeline.get("audio"), out_dir / "out",
                          f"{name}-{language}", self.progress, watermark)
        outputs = encoder.encode_all(formats)
        (out_dir / "out" / "outputs.json").write_text(json.dumps(outputs, indent=2))
        return outputs

    def verify(self, name: str, language: str) -> dict:
        out_dir = self.config.workdir / "compose" / f"{name}-{language}"
        timeline = json.loads((out_dir / "timeline.json").read_text())
        outputs = json.loads((out_dir / "out" / "outputs.json").read_text())
        encode = self.config.get("encode") or {}
        verifier = OutputVerifier(self.config.tool("ffmpeg"), self.config.tool("ffprobe"),
                                  int(self.config.get("capture.fps", 60)), float(encode.get("loudness_lufs", -14)),
                                  float(encode.get("true_peak_db", -1)))
        youtube_height = int(encode.get("youtube_height", 2160))
        reports = {}
        for kind, path in outputs.items():
            height = None
            if kind == "youtube":
                height = max(youtube_height, int(timeline["height"]))
            elif kind in ("webm", "mp4"):
                height = int(timeline["height"])
            reports[kind] = verifier.check(kind, Path(path), timeline["duration_s"], bool(timeline.get("audio")),
                                           height)
        reports["ok"] = all(r["ok"] for r in reports.values() if isinstance(r, dict))
        (out_dir / "out" / "verify.json").write_text(json.dumps(reports, indent=2))
        return reports


class Calibrator:
    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.config = pipeline.config
        self.references = References(self.config.workdir)

    def calibration(self, app_id: str) -> Calibration:
        return self.pipeline.executor().calibration(app_id)

    def wanted(self, app_id: str, tasks: list[str] | None) -> tuple[set[str], set[str]]:
        points, regions = set(), set()
        for scenario_file in sorted(self.config.scenario_dir.glob("T*.yaml")):
            if tasks and scenario_file.stem not in tasks:
                continue
            scenario = self.pipeline.scenarios.get(scenario_file.stem)
            if app_id in scenario.apps:
                points |= scenario.for_app(app_id).point_names
                regions |= scenario.for_app(app_id).region_names
        return points, regions

    def points(self, app_id: str, names: list[str] | None = None, tasks: list[str] | None = None, prompt=input):
        """Asks for each point, then for each region's two corners. The app can be brought to the screen that shows
        the next element in between (`--points` limits the names, e.g. to the elements of one setup page)."""
        calibration = self.calibration(app_id)
        points, regions = self.wanted(app_id, tasks)
        if names:
            points, regions = points & set(names), regions & set(names)
        for name in sorted(points):
            current = calibration.points.get(name)
            prompt(f"Move the mouse pointer onto '{name}'" + (f" (now {current})" if current else "")
                   + " in the app window and press Enter: ")
            x, y = self.pipeline.desktop.pointer_position()
            calibration.set_point(name, x, y)
            print(f"  {name}: {x},{y}")
        for name in sorted(regions):
            current = calibration.regions.get(name)
            prompt(f"Region '{name}'" + (f" (now {current})" if current else "")
                   + ": move the pointer onto its top left corner and press Enter: ")
            a = self.pipeline.desktop.pointer_position()
            prompt(f"Region '{name}': now its bottom right corner, then Enter: ")
            b = self.pipeline.desktop.pointer_position()
            calibration.set_region(name, a, b)
            print(f"  {name}: {calibration.regions[name]}")
        calibration.save()
        return calibration.path

    def window(self, app_id: str, wait_s: float = 20) -> dict:
        executor = self.pipeline.executor()
        spec = self.config.expand(self.config.app(app_id), app_id)
        log = EventLog(self.config.workdir / "calibration" / f"window-{app_id}.jsonl")
        app = AppProcess(app_id, spec, self.pipeline.desktop, executor.layout.app_region, log)
        app.launch(True)
        deadline = time.monotonic() + wait_s
        while app.window is None and app.window_error is None and time.monotonic() < deadline:
            time.sleep(0.2)
        time.sleep(2)
        geometry = self.pipeline.desktop.window_geometry(app.window) if app.window else None
        app.close()
        log.close()
        wanted = executor.layout.app_region
        result = {"wanted": wanted.to_dict(), "actual": geometry.to_dict() if geometry else None,
                  "error": str(app.window_error) if app.window_error else None}
        calibration = self.calibration(app_id)
        calibration.window = result
        calibration.save()
        return result

    def save_crop(self, frame, rect: Rect | None, path: Path) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rect.crop(frame) if rect else frame).save(path)
        return str(path)

    def references_for(self, comparison_id: str, tasks: list[str] | None = None) -> list[str]:
        """One calibration run per app and task with each step's long `reference_quiet_s`; saves the full-frame
        reference of each step, its completion-check regions, its "first messages visible" region and the state
        after its verify actions. Look at every image once: it must show the real end state."""
        spec = self.config.comparison(comparison_id)
        executor = self.pipeline.executor()
        analyzer = RunAnalyzer(self.config, self.pipeline.scenarios)
        saved = []
        for task in tasks or spec["tasks"]:
            for app_id in self.config.group_apps(comparison_id):
                self.pipeline.progress(f"reference run {comparison_id} {task} {app_id}")
                run_dir = executor.execute(comparison_id, task, app_id, "reference", True, -1, reference_run=True)
                analysis = analyzer.analyze(run_dir, reference_run=True)
                saved += self.save_references(run_dir, analysis, app_id, task)
        return saved

    def save_references(self, run_dir: Path, analysis: dict, app_id: str, task: str) -> list[str]:
        meta = json.loads((run_dir / "meta.json").read_text())
        crop = Rect.from_dict(meta["layout"]["app_in_capture"])
        rects = Calibration(self.calibration(app_id).path, Rect.from_dict(meta["layout"]["app_region"])).region_rects()
        app_scenario = self.pipeline.scenarios.get(task).for_app(app_id)
        events = EventLog.read(run_dir / "log.jsonl")
        from .marker import ClockFit
        f = analysis["clock_fit"]
        fit = ClockFit(f["slope"], f["offset"], f["residuals_s"], f["points"], f["rejected_codes"])
        video = VideoFile(run_dir / "capture.mkv", self.config.tool("ffmpeg"), self.config.tool("ffprobe"))
        times = video.frame_times()
        saved = []
        for step in analysis["steps"]:
            scenario_step = next(s for s in app_scenario.steps if s.name == step["name"])
            if step.get("end_index") is None:
                self.pipeline.progress(f"  {step['name']}: no settled state ({step['status']})")
                continue
            frame = video.frame_at_index(step["end_index"], crop)
            path = self.references.full_frame(app_id, task, scenario_step)
            if path is not None:
                saved.append(self.save_crop(frame, None, path))
            for check in scenario_step.regions:
                saved.append(self.save_crop(frame, rects[check.region], self.references.region(
                    app_id, task, step["name"], "end", check.region)))
            if scenario_step.first_visible:
                region = scenario_step.first_visible.region
                saved.append(self.save_crop(frame, rects[region], self.references.region(
                    app_id, task, step["name"], "first", region)))
            if scenario_step.verify:
                verify = [e for e in events if e["type"] == "verify_start" and e["step"] == step["name"]]
                after = [e for e in events if e["type"] == "marker" and verify and e["t"] > verify[0]["t"]]
                if verify and after:
                    at = fit.to_video(after[0]["t"]) - 0.1
                    index = max(0, int((times <= at).sum()) - 1)
                    verify_frame = video.frame_at_index(index, crop)
                    for check in scenario_step.verify.regions:
                        saved.append(self.save_crop(verify_frame, rects[check.region], self.references.region(
                            app_id, task, step["name"], "verify", check.region)))
        return saved

    def crop(self, run_dir: str, at_s: float, app_id: str, task: str, region: str, kind: str,
             step: str | None) -> str:
        """Saves a region of a recorded frame as a reference, e.g. a Microsoft app's opening screen (`opening`)."""
        run_dir = Path(run_dir)
        meta = json.loads((run_dir / "meta.json").read_text())
        rects = self.calibration(app_id).region_rects()
        if region not in rects:
            raise ConfigError(f"Region '{region}' is not calibrated for {app_id}")
        video = VideoFile(run_dir / "capture.mkv", self.config.tool("ffmpeg"), self.config.tool("ffprobe"))
        times = video.frame_times()
        frame = video.frame_at_index(max(0, int((times <= at_s).sum()) - 1),
                                     Rect.from_dict(meta["layout"]["app_in_capture"]))
        path = self.references.opening(app_id, task, region) if kind == "opening" else \
            self.references.region(app_id, task, step, kind, region)
        return self.save_crop(frame, rects[region], path)


class SnapshotBuilder:
    """Takes a snapshot pair: each app's synced profile plus the server state after all apps synced. "Synced" is
    checked, not assumed: the screen is still, the app's profile size stops changing for `snapshot.stable_min`
    minutes and, with the server log, the app fetches nothing from the server for that long; the app must quit by
    itself before its profile is copied."""

    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.config = pipeline.config

    def profile_size(self, app_id: str) -> int:
        total = 0
        for directory in ClientProfiles(self.config).directories(app_id):
            for path in directory.rglob("*"):
                try:
                    if path.is_file():
                        total += path.stat().st_size
                except OSError:
                    pass
        return total

    def wait_synced(self, app_id: str) -> dict:
        stable_s = float(self.config.get("snapshot.stable_min", 2)) * 60
        timeout_s = float(self.config.get("snapshot.sync_timeout_min", 120)) * 60
        started = time.monotonic()
        last_size, last_change = self.profile_size(app_id), time.monotonic()
        server_log = self.pipeline.server_log
        while True:
            time.sleep(10)
            size = self.profile_size(app_id)
            if size != last_size:
                last_size, last_change = size, time.monotonic()
            quiet_server = True
            if server_log is not None:
                now = time.time()
                events = server_log.events(now - stable_s, now)
                quiet_server = not any(e.event in ("imap.fetch", "pop3.fetch") or
                                       (e.event == "http.request-url" and "/download/" in str(e.fields.get("url")))
                                       for e in events if e.source in server_log.benchmark_ips)
            if time.monotonic() - last_change >= stable_s and quiet_server:
                return {"profile_bytes": size, "stable_s": stable_s, "server_checked": server_log is not None,
                        "waited_s": round(time.monotonic() - started)}
            if time.monotonic() - started > timeout_s:
                raise SnapshotError(f"{app_id} didn't finish syncing within {timeout_s / 60:.0f} minutes (profile size "
                                    f"or server fetches still changing)")

    def sync_app(self, app_id: str, manual: bool, sync_wait_s: float) -> dict:
        executor = self.pipeline.executor()
        spec = self.config.expand(self.config.app(app_id), app_id)
        log_path = self.config.workdir / "snapshots" / f"sync-{app_id}.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = EventLog(log_path)
        app = AppProcess(app_id, spec, self.pipeline.desktop, executor.layout.app_region, log,
                         log_path.with_suffix(".output.log"))
        if manual:
            app.launch(True)
            input(f"{app_id}: set up the account and let it sync completely, then press Enter: ")
            check = self.wait_synced(app_id)
            closed = app.close()
            log.close()
            if not closed:
                raise SnapshotError(f"{app_id} didn't quit by itself; its profile may be half written")
            return check
        capture = executor.capture(None, log_path.with_suffix(".ffmpeg.log"))
        driver = ScenarioDriver(self.pipeline.desktop, app, executor.calibration(app_id), executor.variables(), log,
                                type_delay_ms=int(self.config.get("driver.type_delay_ms", 40)),
                                park=executor.park_point())
        driver.live = capture.start()
        try:
            setup = self.pipeline.scenarios.get(self.config.get("snapshot.setup_task", "T1")).for_app(app_id)
            driver.do_actions(setup.prepare, "setup")
            for step in setup.steps:
                driver.do_actions(step.actions, "setup")
                status, _ = driver.live.wait_settled(EventLog.now(), 2.0, 600, step.name, expect_change=False)
                if status != "settled":
                    raise SnapshotError(f"{app_id}: setup step {step.name} didn't settle within 600 s")
            time.sleep(sync_wait_s)
            check = self.wait_synced(app_id)
        finally:
            capture.stop()
            closed = app.close()
            log.close()
        if not closed:
            raise SnapshotError(f"{app_id} didn't quit by itself; its profile may be half written")
        return check

    def resync_app(self, app_id: str, name: str, sync_wait_s: float) -> dict:
        profiles = ClientProfiles(self.config)
        profiles.restore(app_id, name)
        executor = self.pipeline.executor()
        spec = self.config.expand(self.config.app(app_id), app_id)
        log = EventLog(self.config.workdir / "snapshots" / f"resync-{app_id}.jsonl")
        app = AppProcess(app_id, spec, self.pipeline.desktop, executor.layout.app_region, log)
        try:
            app.launch(True)
            time.sleep(sync_wait_s)
            check = self.wait_synced(app_id)
        finally:
            closed = app.close()
            log.close()
        if not closed:
            raise SnapshotError(f"{app_id} didn't quit by itself; its profile may be half written")
        profiles.take(app_id, name)
        return check

    def take(self, name: str, apps: list[str], manual: bool = False, sync_wait_s: float = 60, resync: bool = True):
        profiles = ClientProfiles(self.config)
        checks = {}
        for app_id in apps:
            self.pipeline.progress(f"syncing {app_id} from a fresh profile")
            profiles.reset(app_id)
            checks[app_id] = self.sync_app(app_id, manual, sync_wait_s)
            profiles.take(app_id, name)
        server = self.pipeline.server_snapshots()
        if server:
            self.pipeline.progress(f"server snapshot '{name}'")
            server.take(name)
        if resync and len(apps) > 1:
            for app_id in apps:
                self.pipeline.progress(f"re-syncing {app_id} with the final server state")
                checks[f"{app_id} (resync)"] = self.resync_app(app_id, name, min(sync_wait_s, 30))
            if server:
                server.take(name)
        meta = {"name": name, "apps": apps, "taken": datetime.now(timezone.utc).isoformat(),
                "server_method": (self.config.get("server.snapshot") or {}).get("method", "storage"),
                "sync_check": checks}
        path = self.config.workdir / "snapshots" / name / "meta.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, indent=2))

    def restore(self, name: str, apps: list[str]):
        server = self.pipeline.server_snapshots()
        if server:
            server.restore(name)
        profiles = ClientProfiles(self.config)
        for app_id in apps:
            profiles.restore(app_id, name)
