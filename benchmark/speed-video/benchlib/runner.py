import json
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .capture import CaptureLayout, FFmpegCapture
from .driver import AppProcess, Calibration, EventLog, ScenarioDriver, TextVariables
from .scenario import ScenarioLibrary
from .settle import SettleParams


class RunError(Exception):
    pass


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
                 progress=print):
        self.config = config
        self.desktop = desktop
        self.scenarios = scenarios
        self.server_snapshots = server_snapshots
        self.client_profiles = client_profiles
        self.progress = progress
        self.layout = CaptureLayout.from_config(config)

    def run_dir(self, comparison: str, task: str, app_id: str, run_id: str) -> Path:
        return self.config.workdir / "runs" / comparison / task / app_id / run_id

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
        return TextVariables(values)

    def calibration(self, app_id: str) -> Calibration:
        layout_name = self.config.get("display.layout", "default")
        return Calibration(self.config.workdir / "calibration" / layout_name / f"{app_id}.yaml", self.layout.app_region)

    def capture(self, record_path: Path | None, log_path: Path) -> FFmpegCapture:
        settle = SettleParams.from_dict(self.config.get("settle"))
        return FFmpegCapture(
            self.desktop, self.config.tool("ffmpeg"), self.layout, int(self.config.get("capture.fps", 60)),
            record_path, int(self.config.get("capture.live_scale", 4)), self.config.get("capture.cpus"),
            bool(self.config.get("capture.draw_mouse", True)), log_path,
            int(self.config.get("settle.live_pixel_threshold", 6)), settle.min_changed_pixels)

    def restore(self, app_id: str, start_state: dict):
        server_state = start_state.get("server")
        client_state = start_state.get("client")
        if server_state and self.server_snapshots:
            self.server_snapshots.restore(server_state)
        if client_state and self.client_profiles:
            self.client_profiles.restore(app_id, client_state)

    def execute(self, comparison: str, task: str, app_id: str, run_id: str, warmup: bool, order: int,
                quiet_override: float | None = None, record: bool = True) -> Path:
        scenario = self.scenarios.get(task)
        app_scenario = scenario.for_app(app_id)
        run_dir = self.run_dir(comparison, task, app_id, run_id)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        app_spec = self.config.expand(self.config.app(app_id), app_id)
        meta = {"run": run_id, "app": app_id, "task": task, "comparison": comparison, "warmup": warmup,
                "order": order, "layout": self.layout.to_dict(), "started": datetime.now(timezone.utc).isoformat(),
                "status": "running"}
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        log = EventLog(run_dir / "log.jsonl")
        app = AppProcess(app_id, app_spec, self.desktop, self.layout.app_region, log, run_dir / "app-output.log")
        marker = None
        recording = None
        try:
            self.restore(app_id, scenario.start_state)
            log.write("restored", start_state=scenario.start_state)
            driver = ScenarioDriver(
                self.desktop, app, self.calibration(app_id), self.variables(), log,
                type_delay_ms=int(self.config.get("driver.type_delay_ms", 40)),
                live_quiet_s=float(quiet_override or self.config.get("settle.live_quiet_s", 1.5)),
                step_timeout_s=float(self.config.get("settle.step_timeout_s", 300)))
            if app_scenario.prepare:
                preview = self.capture(None, run_dir / "ffmpeg-prepare.log")
                driver.live = preview.start()
                try:
                    driver.do_actions(app_scenario.prepare, "prepare")
                finally:
                    preview.stop()
            recording = self.capture(run_dir / "capture.mkv" if record else None, run_dir / "ffmpeg.log")
            if quiet_override is None:
                references = self.config.workdir / "references" / app_id / task
                driver.live_references = {s.name: recording.live_reference(references / f"{s.name}.png")
                                          for s in app_scenario.steps if s.measure and s.expect}
            driver.live = recording.start()
            x, y = self.layout.marker_screen_position
            marker = self.desktop.marker_window(x, y, self.layout.marker)
            driver.marker = marker
            driver.marker_burst("start")
            driver.run_steps(app_scenario)
            driver.marker_burst("end")
            time.sleep(0.3)
            recording.stop()
            recording = None
            if app_scenario.finish:
                driver.do_actions(app_scenario.finish, "finish")
            meta["status"] = "complete"
        except Exception as ex:
            meta["status"] = "failed"
            meta["error"] = f"{type(ex).__name__}: {ex}"
            (run_dir / "error.txt").write_text(traceback.format_exc())
            self.progress(f"    run failed: {meta['error']}")
        finally:
            if recording:
                recording.stop()
            if marker:
                marker.close()
            meta["closed_cleanly"] = app.close()
            log.write("closed")
            log.close()
            meta["finished"] = datetime.now(timezone.utc).isoformat()
            (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        return run_dir


class Orchestrator:
    def __init__(self, config, executor: RunExecutor, progress=print):
        self.config = config
        self.executor = executor
        self.progress = progress

    def run_comparison(self, comparison_id: str, tasks: list[str] | None = None, resume: bool = True,
                       measured: int | None = None, warmup: int | None = None):
        spec = self.config.comparison(comparison_id)
        measured = int(measured if measured is not None else self.config.get("runs.measured", 5))
        warmup = int(warmup if warmup is not None else self.config.get("runs.warmup", 1))
        retries = int(self.config.get("runs.retries", 2))
        apps = [spec["left"], spec["right"]]
        for task in tasks or spec["tasks"]:
            plan = RunPlan.interleaved(apps, measured, warmup)
            for order, (app_id, run_id, is_warmup) in enumerate(plan):
                run_dir = self.executor.run_dir(comparison_id, task, app_id, run_id)
                meta_path = run_dir / "meta.json"
                if resume and meta_path.exists() and json.loads(meta_path.read_text()).get("status") == "complete":
                    continue
                for attempt in range(retries + 1):
                    self.progress(f"{comparison_id} {task} {app_id} {run_id}"
                                  + (f" (attempt {attempt + 1})" if attempt else ""))
                    self.executor.execute(comparison_id, task, app_id, run_id, is_warmup, order)
                    status = json.loads(meta_path.read_text()).get("status")
                    if status == "complete":
                        break
                    failed_copy = run_dir.with_name(f"{run_id}.failed-{attempt + 1}")
                    if failed_copy.exists():
                        shutil.rmtree(failed_copy)
                    shutil.copytree(run_dir, failed_copy)
