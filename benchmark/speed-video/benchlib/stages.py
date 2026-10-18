import json
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .analyze import Aggregator, AnalysisError, ReportWriter, RunAnalyzer
from .compose import Composer
from .corpus import CorpusGenerator, CorpusSpec
from .driver import AppProcess, Calibration, EventLog, ScenarioDriver
from .encode import Encoder
from .environment import EnvironmentProbe
from .narration import Narration
from .runner import Desktops, Orchestrator, RunExecutor
from .scenario import ScenarioLibrary
from .seed import Seeder
from .settle import Rect, SettleParams
from .snapshot import ClientProfiles, CommandRunner, ProtocolSnapshot, ServerReadiness, StorageSnapshot
from .verify import OutputVerifier
from .video import VideoFile


class Pipeline:
    def __init__(self, config, progress=print):
        self.config = config
        self.progress = progress
        self.scenarios = ScenarioLibrary(config.scenario_dir)
        self._desktop = None

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

    def executor(self) -> RunExecutor:
        return RunExecutor(self.config, self.desktop, self.scenarios, self.server_snapshots(),
                           ClientProfiles(self.config), self.progress)

    def corpus_facts(self) -> dict:
        generator = CorpusGenerator(CorpusSpec.from_dict(self.config.get("corpus")))
        expected = generator.expected()
        facts = self.config.get("corpus_facts") or {}
        folders = expected["folders"]
        archive = next((n for n, f in folders.items() if f["role"] == "archive"), None)
        move = facts.get("move_folder", "Projects/Move-me")
        term = facts.get("search_term") or next(iter(expected["planted"]), None)
        return {"messages": expected["total"],
                "archive_messages": folders[archive]["count"] if archive else None,
                "move_messages": folders.get(move, {}).get("count"),
                "search_hits": expected["planted"][term]["count"] if term else None}

    def environment(self, comparison_id: str) -> dict:
        spec = self.config.comparison(comparison_id)
        env = EnvironmentProbe(self.config, self.desktop).collect([spec["left"], spec["right"]])
        env.update(spec.get("environment") or {})
        path = self.config.workdir / "results" / f"environment-{comparison_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(env, indent=2))
        return env

    def run(self, comparison_id: str, tasks: list[str] | None, resume: bool, measured: int | None,
            warmup: int | None):
        env_path = self.config.workdir / "results" / f"environment-{comparison_id}.json"
        if not env_path.exists():
            self.environment(comparison_id)
        Orchestrator(self.config, self.executor(), self.progress).run_comparison(
            comparison_id, tasks, resume, measured, warmup)

    def analyze(self, comparison_id: str, force: bool = False) -> dict:
        analyzer = RunAnalyzer(self.config, self.scenarios)
        root = self.config.workdir / "runs" / comparison_id
        for meta_path in sorted(root.glob("*/*/*/meta.json")):
            run_dir = meta_path.parent
            if run_dir.name == "reference":
                continue
            meta = json.loads(meta_path.read_text())
            if meta.get("status") != "complete" or (not force and (run_dir / "analysis.json").exists()):
                continue
            try:
                result = analyzer.analyze(run_dir)
                self.progress(f"  {run_dir.relative_to(self.config.workdir)}: {result['status']} "
                              + (f"{result['total_s']:.3f} s" if result["total_s"] is not None else ""))
            except AnalysisError as ex:
                (run_dir / "analysis-error.txt").write_text(str(ex))
                self.progress(f"  {run_dir.relative_to(self.config.workdir)}: analysis failed: {ex}")
        return self.write_results(comparison_id)

    def results_path(self) -> Path:
        return self.config.workdir / "results" / "results.json"

    def write_results(self, comparison_id: str) -> dict:
        path = self.results_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        results = json.loads(path.read_text()) if path.exists() else {"version": 1, "comparisons": {},
                                                                       "environment": {}}
        comparison = Aggregator(self.config, self.scenarios).comparison(comparison_id)
        results["comparisons"][comparison_id] = comparison
        env_path = self.config.workdir / "results" / f"environment-{comparison_id}.json"
        if env_path.exists():
            env = json.loads(env_path.read_text())
            for side in ("left", "right"):
                app = env.get("apps", {}).get(comparison[side], {})
                for task in comparison["tasks"].values():
                    if app.get("version"):
                        task[side]["version"] = app["version"]
            results["environment"][comparison_id] = env
        results["runs"] = {"measured": int(self.config.get("runs.measured", 5)),
                           "warmup": int(self.config.get("runs.warmup", 1))}
        results["settle"] = vars(SettleParams.from_dict(self.config.get("settle")))
        results["corpus"] = self.corpus_facts()
        results["generated"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        ReportWriter(results, list(self.config.get("deviations") or [])).write(path.parent / "report.md")
        return results

    def compose(self, comparisons: list[str] | None, language: str, narration_path: str | None,
                variant: str | None, name: str, results_paths: list[str] | None = None) -> dict:
        results = self.merged_results(results_paths)
        narration = Narration.load(narration_path) if narration_path else None
        only = None
        if variant and narration_path:
            variants = json.loads((Path(narration_path).parent / "variants" / "variants.json").read_text()) \
                if (Path(narration_path).parent / "variants" / "variants.json").exists() else {}
            only = variants.get(variant)
        out_dir = self.config.workdir / "compose" / f"{name}-{language}"
        out_dir.mkdir(parents=True, exist_ok=True)
        return Composer(self.config, results, out_dir, language, narration, only, comparisons,
                        self.progress).compose()

    def merged_results(self, results_paths: list[str] | None) -> dict:
        paths = [Path(p) for p in results_paths] if results_paths else [self.results_path()]
        merged = None
        for path in paths:
            data = json.loads(path.read_text())
            if merged is None:
                merged = data
            else:
                merged["comparisons"].update(data["comparisons"])
                merged["environment"].update(data.get("environment") or {})
        return merged

    def encode(self, name: str, language: str, formats: list[str] | None) -> dict:
        out_dir = self.config.workdir / "compose" / f"{name}-{language}"
        timeline = json.loads((out_dir / "timeline.json").read_text())
        encoder = Encoder(self.config, out_dir / "master.mkv", timeline.get("audio"), out_dir / "out",
                          f"{name}-{language}", self.progress)
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

    def calibration(self, app_id: str) -> Calibration:
        return self.pipeline.executor().calibration(app_id)

    def points(self, app_id: str, names: list[str] | None = None, prompt=input):
        calibration = self.calibration(app_id)
        wanted = set(names or [])
        if not wanted:
            for scenario_file in sorted(self.config.scenario_dir.glob("T*.yaml")):
                scenario = self.pipeline.scenarios.get(scenario_file.stem)
                if app_id in scenario.apps:
                    wanted |= scenario.for_app(app_id).point_names
        for name in sorted(wanted):
            current = calibration.points.get(name)
            prompt(f"Move the mouse pointer onto '{name}'" + (f" (now {current})" if current else "")
                   + " in the app window and press Enter: ")
            x, y = self.pipeline.desktop.pointer_position()
            calibration.set_point(name, x, y)
            print(f"  {name}: {x},{y}")
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

    def references(self, comparison_id: str, tasks: list[str] | None = None) -> list[str]:
        spec = self.config.comparison(comparison_id)
        quiet = float(self.config.get("settle.reference_quiet_s", 4.0))
        executor = self.pipeline.executor()
        analyzer = RunAnalyzer(self.config, self.pipeline.scenarios)
        saved = []
        for task in tasks or spec["tasks"]:
            for app_id in (spec["left"], spec["right"]):
                self.pipeline.progress(f"reference run {comparison_id} {task} {app_id}")
                run_dir = executor.execute(comparison_id, task, app_id, "reference", True, -1, quiet_override=quiet + 0.5)
                analysis = analyzer.analyze(run_dir, {"quiet_s": quiet}, use_references=False)
                meta = json.loads((run_dir / "meta.json").read_text())
                crop = Rect.from_dict(meta["layout"]["app_in_capture"])
                video = VideoFile(run_dir / "capture.mkv", self.config.tool("ffmpeg"), self.config.tool("ffprobe"))
                for step in analysis["steps"]:
                    if step["end_index"] is None:
                        self.pipeline.progress(f"  {step['name']}: no settled state ({step['status']})")
                        continue
                    frame = video.frame_at_index(step["end_index"], crop)
                    path = analyzer.reference_path(app_id, task, step["name"])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    Image.fromarray(frame).save(path)
                    saved.append(str(path))
        return saved


class SnapshotBuilder:
    """Takes a snapshot pair: each app's synced profile plus the server state after all apps synced."""

    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.config = pipeline.config

    def sync_app(self, app_id: str, manual: bool, sync_wait_s: float):
        executor = self.pipeline.executor()
        spec = self.config.expand(self.config.app(app_id), app_id)
        log_path = self.config.workdir / "snapshots" / f"sync-{app_id}.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = EventLog(log_path)
        app = AppProcess(app_id, spec, self.pipeline.desktop, executor.layout.app_region, log,
                         log_path.with_suffix(".output.log"))
        if manual:
            app.launch(True)
            input(f"{app_id}: set up the account and let it sync completely, then press Enter (the app will be "
                  f"closed): ")
            app.close()
            log.close()
            return
        capture = executor.capture(None, log_path.with_suffix(".ffmpeg.log"))
        driver = ScenarioDriver(self.pipeline.desktop, app, executor.calibration(app_id), executor.variables(), log,
                                type_delay_ms=int(self.config.get("driver.type_delay_ms", 40)))
        driver.live = capture.start()
        try:
            setup = self.pipeline.scenarios.get(self.config.get("snapshot.setup_task", "T1")).for_app(app_id)
            driver.do_actions(setup.prepare, "setup")
            for step in setup.steps:
                driver.do_actions(step.actions, "setup")
                driver.live.wait_settled(EventLog.now(), 2.0, 600, step.name, expect_change=False)
            time.sleep(sync_wait_s)
            driver.live.wait_settled(EventLog.now(), 10.0, max(600.0, 2 * sync_wait_s), "sync",
                                     expect_change=False)
        finally:
            capture.stop()
            app.close()
            log.close()

    def resync_app(self, app_id: str, name: str, sync_wait_s: float):
        profiles = ClientProfiles(self.config)
        profiles.restore(app_id, name)
        executor = self.pipeline.executor()
        spec = self.config.expand(self.config.app(app_id), app_id)
        log = EventLog(self.config.workdir / "snapshots" / f"resync-{app_id}.jsonl")
        app = AppProcess(app_id, spec, self.pipeline.desktop, executor.layout.app_region, log)
        capture = executor.capture(None, self.config.workdir / "snapshots" / f"resync-{app_id}.ffmpeg.log")
        live = capture.start()
        try:
            app.launch(True)
            time.sleep(sync_wait_s)
            live.wait_settled(EventLog.now(), 10.0, max(600.0, 2 * sync_wait_s), "resync", expect_change=False)
        finally:
            capture.stop()
            app.close()
            log.close()
        profiles.take(app_id, name)

    def take(self, name: str, apps: list[str], manual: bool = False, sync_wait_s: float = 60, resync: bool = True):
        profiles = ClientProfiles(self.config)
        for app_id in apps:
            self.pipeline.progress(f"syncing {app_id} from a fresh profile")
            profiles.reset(app_id)
            self.sync_app(app_id, manual, sync_wait_s)
            profiles.take(app_id, name)
        server = self.pipeline.server_snapshots()
        if server:
            self.pipeline.progress(f"server snapshot '{name}'")
            server.take(name)
        if resync and len(apps) > 1:
            for app_id in apps:
                self.pipeline.progress(f"re-syncing {app_id} with the final server state")
                self.resync_app(app_id, name, min(sync_wait_s, 30))
            if server:
                server.take(name)
        meta = {"name": name, "apps": apps, "taken": datetime.now(timezone.utc).isoformat(),
                "server_method": (self.config.get("server.snapshot") or {}).get("method", "storage")}
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
