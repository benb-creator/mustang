import json
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .capture import CaptureLayout, FFmpegCapture
from .driver import AppProcess, Calibration, EventLog, NoReaction, ScenarioDriver, StepTimeout, TextVariables
from .references import References
from .scenario import ScenarioLibrary
from .settle import SettleParams
from .snapshot import PasswordRotation


class RunError(Exception):
    pass


class FinishError(RunError):
    """A required finishing sequence failed (e.g. removing the account from new Outlook): later runs of the series
    would not start from the same state, so the series stops."""


class Desktops:
    @staticmethod
    def create(config):
        platform = config.get("display.platform", "linux")
        if platform == "linux":
            from .x11 import X11Desktop
            return X11Desktop(config.get("display.display", ":0"), config.tool("xdotool"))
        if platform == "windows":
            from .windows import WindowsDesktop
            return WindowsDesktop(int(config.get("display.monitor", 0)))
        raise RunError(f"Unknown display.platform '{platform}'")


class RunPlan:
    @staticmethod
    def interleaved(apps: list[str], measured: int, warmup: int) -> list[tuple[str, str, bool]]:
        plan = []
        for w in range(warmup):
            plan += [(app, f"warmup-{w + 1}", True) for app in apps]
        for r in range(measured):
            plan += [(app, f"run-{r + 1}", False) for app in apps]
        return plan


class RunExecutor:
    def __init__(self, config, desktop, scenarios: ScenarioLibrary, server_snapshots=None, client_profiles=None,
                 progress=print, server_log=None, versions=None):
        self.config = config
        self.desktop = desktop
        self.scenarios = scenarios
        self.server_snapshots = server_snapshots
        self.client_profiles = client_profiles
        self.progress = progress
        self.server_log = server_log
        self.versions = versions
        self.layout = CaptureLayout.from_config(config)
        self.references = References(config.workdir)
        self.rotation = PasswordRotation(config)

    def run_dir(self, comparison: str, task: str, app_id: str, run_id: str) -> Path:
        return self.config.workdir / "runs" / self.config.run_group(comparison) / task / app_id / run_id

    def variables(self) -> TextVariables:
        values = {
            "account.email": str(self.config.get("account.email", "")),
            "account.username": str(self.config.get("account.username") or self.config.get("account.email", "")),
            "account.name": str(self.config.get("account.display_name", "")),
            "server.host": str(self.config.get("server.host", "")),
            "server.imap_host": str(self.config.get("server.imap.host", "")),
            "server.imap_port": str(self.config.get("server.imap.port", "")),
            "server.smtp_host": str(self.config.get("server.smtp.host", "")),
            "server.smtp_port": str(self.config.get("server.smtp.port", "")),
        }
        planted = (self.config.get("corpus") or {}).get("planted") or [{"term": "kumquat"}]
        values["search.term"] = str(self.config.get("corpus_facts.search_term") or planted[0]["term"])
        for key, value in (self.config.get("variables") or {}).items():
            values[key] = str(value)
        if self.config.get("account.password_env"):
            try:
                values["account.password"] = self.config.secret("account.password_env")
            except Exception:
                pass
        return TextVariables(values, {"account.password"})

    def calibration(self, app_id: str) -> Calibration:
        layout_name = self.config.get("display.layout", "default")
        return Calibration(self.config.workdir / "calibration" / layout_name / f"{app_id}.yaml", self.layout.app_region)

    def settle(self, app_scenario=None) -> SettleParams:
        return SettleParams.from_dict(self.config.get("settle"), app_scenario.settle if app_scenario else None)

    def capture(self, record_path: Path | None, log_path: Path) -> FFmpegCapture:
        settle = self.settle()
        return FFmpegCapture(
            self.desktop, self.config.tool("ffmpeg"), self.layout, int(self.config.get("capture.fps", 60)),
            record_path, int(self.config.get("capture.live_scale", 4)), self.config.get("capture.cpus"),
            bool(self.config.get("capture.draw_mouse", False)), log_path,
            int(self.config.get("settle.live_pixel_threshold", 6)), settle.min_changed_pixels)

    def park_point(self) -> tuple[int, int] | None:
        park = self.config.get("display.pointer_park")
        if park == "none":
            return None
        if isinstance(park, dict):
            return int(park["x"]), int(park["y"])
        region = self.layout.capture_region
        return region.x + region.width + 100, region.y + 100

    def task_timeout_s(self, scenario) -> float:
        return float(scenario.timeout_s or self.config.get("settle.task_timeout_s", 7200))

    def driver(self, app: AppProcess, app_id: str, log: EventLog, app_scenario, scenario,
               reference_run: bool = False) -> ScenarioDriver:
        settle = self.settle(app_scenario)
        driver = ScenarioDriver(
            self.desktop, app, self.calibration(app_id), self.variables(), log,
            type_delay_ms=int(self.config.get("driver.type_delay_ms", 40)), quiet_s=settle.quiet_s,
            step_timeout_s=float(self.config.get("settle.step_timeout_s", 300)),
            task_timeout_s=self.task_timeout_s(scenario), park=self.park_point(),
            no_reaction_s=settle.no_reaction_s, grace_s=None if reference_run else settle.roi_grace_s,
            server_log=self.server_log)
        if reference_run:
            driver.quiet_by_step = {s.name: SettleParams.from_dict(self.config.get("settle"), app_scenario.settle,
                                                                   s.settle).reference_quiet_s
                                    for s in app_scenario.steps if s.measure}
        return driver

    def restore(self, app_id: str, start_state: dict):
        server_state = start_state.get("server")
        client_state = start_state.get("client")
        if server_state and self.server_snapshots:
            self.server_snapshots.restore(server_state)
        if client_state and self.client_profiles:
            self.client_profiles.restore(app_id, client_state)

    def live_checks(self, driver: ScenarioDriver, recording: FFmpegCapture, app_id: str, task: str, app_scenario,
                    reference_run: bool):
        """The live gate waits for the step's references; changes inside its regions always count. A calibration
        run has no references yet, but watches the regions all the same."""
        rects = driver.calibration.region_rects()
        for step in app_scenario.steps:
            if not step.measure:
                continue
            path = None if reference_run else self.references.full_frame(app_id, task, step)
            reference = recording.live_reference(path) if path else None
            if reference is not None:
                driver.live_references[step.name] = reference
            regions = self.references.regions(app_id, task, step, "end", rects, load=not reference_run)
            driver.live_regions[step.name] = [recording.live_region(r) for r in regions]

    def execute(self, comparison: str, task: str, app_id: str, run_id: str, warmup: bool, order: int,
                reference_run: bool = False, record: bool = True, attempt: int = 1) -> Path:
        scenario = self.scenarios.get(task)
        app_scenario = scenario.for_app(app_id)
        run_dir = self.run_dir(comparison, task, app_id, run_id)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        app_spec = self.config.expand(self.config.app(app_id), app_id)
        meta = {"run": run_id, "app": app_id, "task": task, "comparison": comparison, "warmup": warmup,
                "order": order, "attempt": attempt, "layout": self.layout.to_dict(),
                "started": datetime.now(timezone.utc).isoformat(), "status": "running",
                "task_timeout_s": self.task_timeout_s(scenario)}
        if self.versions:
            meta["app_version"] = self.versions(app_id)
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        log = EventLog(run_dir / "log.jsonl")
        app = AppProcess(app_id, app_spec, self.desktop, self.layout.app_region, log, run_dir / "app-output.log")
        driver = self.driver(app, app_id, log, app_scenario, scenario, reference_run)
        marker = None
        recording = None
        marks = {}
        started_utc = time.time()
        log.clock("start")
        try:
            self.restore(app_id, scenario.start_state)
            if self.rotation.enabled and scenario.start_state.get("server"):
                driver.variables.values["account.password"] = self.rotation.rotate()
                meta["password_rotated"] = True
            log.write("restored", start_state=scenario.start_state)
            if app_scenario.prepare:
                preview = self.capture(None, run_dir / "ffmpeg-prepare.log")
                driver.live = preview.start()
                try:
                    driver.do_actions(app_scenario.prepare, "prepare")
                finally:
                    preview.stop()
            recording = self.capture(run_dir / "capture.mkv" if record else None, run_dir / "ffmpeg.log")
            self.live_checks(driver, recording, app_id, task, app_scenario, reference_run)
            driver.live = recording.start()
            x, y = self.layout.marker_screen_position
            marker = self.desktop.marker_window(x, y, self.layout.marker)
            driver.marker = marker
            driver.marker_burst("start")
            marks["recording"] = time.time()
            try:
                driver.run_steps(app_scenario)
                meta["status"] = "complete"
            except StepTimeout as ex:
                meta["status"] = "timeout"
                meta["timeout"] = {"step": ex.step, "limit_s": ex.limit_s}
                self.progress(f"    time limit reached in step {ex.step}")
            driver.marker_burst("end")
            marks["steps-done"] = time.time()
            tail = float(app_scenario.tail_s if app_scenario.tail_s is not None else self.config.get("capture.tail_s", 0))
            if tail > 0 and meta["status"] == "complete":
                time.sleep(tail)
                driver.marker_burst("tail-end")
            time.sleep(0.3)
            recording.stop()
            recording = None
            if app_scenario.finish:
                try:
                    driver.do_actions(app_scenario.finish, "finish")
                except Exception as ex:
                    if app_scenario.finish_required:
                        raise FinishError(f"{app_id}: finishing sequence failed: {ex}") from ex
                    raise
                meta["finished_sequence"] = True
        except FinishError as ex:
            meta["status"] = "failed"
            meta["failure"] = "finish"
            meta["error"] = driver.variables.redact(f"{type(ex).__name__}: {ex}")
            (run_dir / "error.txt").write_text(driver.variables.redact(traceback.format_exc()))
            self.progress(f"    {meta['error']}")
        except Exception as ex:
            meta["status"] = "failed"
            meta["failure"] = "no-reaction" if isinstance(ex, NoReaction) else "technical"
            meta["error"] = driver.variables.redact(f"{type(ex).__name__}: {ex}")
            (run_dir / "error.txt").write_text(driver.variables.redact(traceback.format_exc()))
            self.progress(f"    run failed: {meta['error']}")
        finally:
            if recording:
                recording.stop()
            if marker:
                marker.close()
            meta["closed_cleanly"] = app.close()
            log.write("closed")
            log.clock("end")
            log.close()
            meta["finished"] = datetime.now(timezone.utc).isoformat()
            if self.server_log is not None and self.server_log.enabled:
                try:
                    events = EventLog.read(run_dir / "log.jsonl")
                    offset = EventLog.utc_offset(events)
                    removal = next((e["t"] for e in events if e["type"] == "input" and e.get("phase") == "finish"), None)
                    if removal is not None and offset is not None:
                        marks["removal"] = removal + offset
                    self.server_log.collect(run_dir, started_utc, time.time(), marks)
                except Exception as ex:
                    meta["evidence_error"] = driver.variables.redact(f"{type(ex).__name__}: {ex}")
            (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        return run_dir


class Orchestrator:
    """Runs the interleaved plan. A run that failed for a technical reason (window, capture, crash, clock fit,
    dropped frames) is recorded again at the end of the plan, at most `runs.retries` times, and listed in the report.
    Timeouts and wrong results are measurements and are never recorded again."""

    def __init__(self, config, executor: RunExecutor, progress=print, analyzer=None):
        self.config = config
        self.executor = executor
        self.progress = progress
        self.analyzer = analyzer

    def outcome(self, run_dir: Path) -> str:
        meta = json.loads((run_dir / "meta.json").read_text())
        if meta.get("failure") == "finish":
            return "finish-failed"
        if meta.get("status") == "failed":
            return "technical"
        if self.analyzer is None:
            return meta["status"]
        analysis = self.analyzer.analyze_safely(run_dir)
        return "technical" if analysis.get("status") == "failed" and analysis.get("failure") == "technical" \
            else analysis.get("status", "failed")

    def done_before(self, run_dir: Path) -> bool:
        meta_path = run_dir / "meta.json"
        if not meta_path.exists():
            return False
        meta = json.loads(meta_path.read_text())
        if meta.get("status") not in ("complete", "timeout"):
            return False
        analysis = run_dir / "analysis.json"
        if analysis.exists():
            data = json.loads(analysis.read_text())
            return not (data.get("status") == "failed" and data.get("failure") == "technical")
        return True

    def run_comparison(self, comparison_id: str, tasks: list[str] | None = None, resume: bool = True,
                       measured: int | None = None, warmup: int | None = None):
        spec = self.config.comparison(comparison_id)
        measured = int(measured if measured is not None else self.config.get("runs.measured", 5))
        warmup = int(warmup if warmup is not None else self.config.get("runs.warmup", 1))
        retries = int(self.config.get("runs.retries", 2))
        apps = self.config.group_apps(comparison_id)
        for task in tasks or spec["tasks"]:
            queue = [(app_id, run_id, is_warmup, 1) for app_id, run_id, is_warmup in
                     RunPlan.interleaved(apps, measured, warmup)]
            order = 0
            while queue:
                app_id, run_id, is_warmup, attempt = queue.pop(0)
                run_dir = self.executor.run_dir(comparison_id, task, app_id, run_id)
                order += 1
                if resume and attempt == 1 and self.done_before(run_dir):
                    continue
                if attempt > 1:
                    failed_copy = run_dir.with_name(f"{run_id}.failed-{attempt - 1}")
                    if failed_copy.exists():
                        shutil.rmtree(failed_copy)
                    shutil.copytree(run_dir, failed_copy)
                self.progress(f"{comparison_id} {task} {app_id} {run_id}"
                              + (f" (attempt {attempt}, re-recorded at the end of the series)" if attempt > 1 else ""))
                self.executor.execute(comparison_id, task, app_id, run_id, is_warmup, order, attempt=attempt)
                outcome = self.outcome(run_dir)
                if outcome == "finish-failed":
                    raise FinishError(f"{comparison_id} {task} {app_id} {run_id}: the finishing sequence failed; "
                                      f"the series stops (see {run_dir / 'error.txt'})")
                if outcome == "technical" and attempt <= retries:
                    queue.append((app_id, run_id, is_warmup, attempt + 1))
            self.watch_after_series(comparison_id, task)

    def watch_after_series(self, comparison_id: str, task: str):
        server_log = self.executor.server_log
        minutes = float(self.config.get("server.log.final_watch_min", 0) or 0)
        if server_log is None or not server_log.enabled or minutes <= 0:
            return
        self.progress(f"watching the server log for {minutes:.0f} more minutes")
        started = time.time()
        time.sleep(minutes * 60)
        out = self.config.workdir / "evidence" / self.config.run_group(comparison_id) / task
        out.mkdir(parents=True, exist_ok=True)
        server_log.collect(out, started, time.time(), {})
        (out / "evidence.json").rename(out / "after-series.json")
        (out / "server-log.txt").rename(out / "after-series-server-log.txt")
