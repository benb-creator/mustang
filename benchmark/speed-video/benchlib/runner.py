import json
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .capture import CaptureLayout, FFmpegCapture
from .driver import (AppProcess, Calibration, EventLog, MovingAreaWatcher, NoReaction, ScenarioDriver, StepTimeout,
                     TextVariables)
from .references import References
from .scenario import ScenarioLibrary
from .settle import SettleParams
from .snapshot import PasswordRotation


class RunError(Exception):
    pass


class SeriesStop(RunError):
    """Later runs of the series can't start from the same state or can't be recorded, so the series stops."""

    failure = "stop"


class FinishError(SeriesStop):
    """A required finishing sequence failed (e.g. removing the account from new Outlook)."""

    failure = "finish"


class DiskFull(SeriesStop):
    failure = "disk"


class AppLifecycle:
    """What an app needs around its runs besides its scenario: on Windows its fresh state, its windows and, for new
    Outlook, keeping and then removing the account after the measured end (benchlib/winsession.py). This default
    needs nothing."""

    def app_process(self, app_id: str, spec: dict, desktop, region, log, output) -> AppProcess:
        return AppProcess(app_id, spec, desktop, region, log, output)

    def reset(self):
        pass

    def finish(self, driver: ScenarioDriver, probe) -> dict | None:
        return None

    def after_failure(self, driver: ScenarioDriver, probe) -> dict | None:
        return None

    def after_close(self) -> dict | None:
        return None


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
                 progress=print, server_log=None, versions=None, folder=None, account=None, lifecycles=None):
        self.config = config
        self.desktop = desktop
        self.scenarios = scenarios
        self.server_snapshots = server_snapshots
        self.client_profiles = client_profiles
        self.progress = progress
        self.server_log = server_log
        self.versions = versions
        self.folder = folder
        self.account = account
        self.lifecycles = dict(lifecycles or {})
        self.layout = CaptureLayout.from_config(config)
        self.references = References(config.workdir)
        self.rotation = PasswordRotation(config)

    def run_dir(self, comparison: str, task: str, app_id: str, run_id: str) -> Path:
        if self.folder is not None:
            return self.folder.run_dir(app_id, task, run_id)
        return self.config.workdir / "runs" / self.config.run_group(comparison) / task / app_id / run_id

    def variables(self) -> TextVariables:
        server = self.account.server if self.account else None
        imap = server.imap_settings if server else (self.config.get("server.imap") or {})
        smtp = server.smtp_settings if server else (self.config.get("server.smtp") or {})
        values = {
            "account.email": str(self.config.get("account.email", "")),
            "account.username": str(self.config.get("account.username") or self.config.get("account.email", "")),
            "account.name": str(self.config.get("account.display_name", "")),
            "server.host": str(self.config.get("server.host", "")),
            "server.imap_host": str(imap.get("host", "")),
            "server.imap_port": str(imap.get("port", "")),
            "server.smtp_host": str(smtp.get("host", "")),
            "server.smtp_port": str(smtp.get("port", "")),
            "server.jmap_url": str(server.jmap_session_url if server else self.config.get("server.jmap_session_url", "")),
        }
        planted = (self.config.get("corpus") or {}).get("planted") or [{"term": "kumquat"}]
        values["search.term"] = str(self.config.get("corpus_facts.search_term") or planted[0]["term"])
        discovery = (self.folder.manifest().get("server_discovery") if self.folder is not None else None) or {}
        values["server.guard"] = "off" if discovery and not discovery.get("guarded") else "on"
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
               reference_run: bool = False, probe=None, verify_path: Path | None = None) -> ScenarioDriver:
        settle = self.settle(app_scenario)
        driver = ScenarioDriver(
            self.desktop, app, self.calibration(app_id), self.variables(), log,
            type_delay_ms=int(self.config.get("driver.type_delay_ms", 40)), quiet_s=settle.quiet_s,
            step_timeout_s=float(self.config.get("settle.step_timeout_s", 300)),
            task_timeout_s=self.task_timeout_s(scenario), park=self.park_point(),
            no_reaction_s=settle.no_reaction_s, grace_s=None if reference_run else settle.roi_grace_s,
            server_log=self.server_log, probe=probe, expected=self.account.expected if self.account else None,
            verify_path=verify_path, probe_interval_s=float(self.config.get("settle.probe_interval_s", 1.0)))
        if reference_run:
            driver.quiet_by_step = {s.name: SettleParams.from_dict(self.config.get("settle"), app_scenario.settle,
                                                                   s.settle).reference_quiet_s
                                    for s in app_scenario.steps if s.measure}
        return driver

    def restore(self, app_id: str, start_state: dict, run_dir: Path):
        server_state = start_state.get("server")
        client_state = start_state.get("client")
        if self.account is not None and server_state:
            report = self.account.check.run(repair=True)
            (run_dir / "account.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
            if not report["ok"]:
                raise RunError(f"The test account still differs from the corpus after the repair: "
                               f"{report.get('after') or report.get('before')}")
        elif server_state and self.server_snapshots:
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

    def network_watcher(self, run_dir: Path, app: AppProcess, app_id: str):
        if not self.config.get("evidence.network", True) or self.desktop.platform not in ("linux", "windows"):
            return None
        from .netwatch import LinuxConnectionWatcher, NetworkLog
        log = NetworkLog(run_dir / "network.jsonl")
        addresses = {}
        if self.account is not None:
            addresses = self.account.mail_server()
            for host, values in (addresses.get("hosts") or {}).items():
                log.write("resolve", host=host, addresses=values)
            log.write("mail_server", **{k: addresses[k] for k in ("addresses", "ports", "mail_only_ports")})
        names = app.spec.get("process_names") or []
        poll_hz = float(self.config.get("evidence.poll_hz", 10))
        if self.desktop.platform == "windows":
            from .winnet import WindowsConnectionWatcher
            watcher = WindowsConnectionWatcher(log, app_id, lambda: {app.process.pid} if app.process else set(),
                                               [n.lower() for n in names], poll_hz, set(addresses.get("addresses") or []))
        else:
            env = app.spec.get("process_env")
            watcher = LinuxConnectionWatcher(
                log, app_id, lambda: [app.process.pid] if app.process else [],
                (lambda: self.desktop.matching_pids(names, env)) if names else None, poll_hz, ss=self.config.tool("ss"))
        watcher.start()
        return watcher

    def moving_watcher(self, probe, driver: ScenarioDriver):
        """For an app that shows content that changes by itself (Parula's setup video): its area is left out of the
        settle detection, live and offline (`settle.moving_content_hz` polls a second, 0 = off)."""
        hz = float(self.config.get("settle.moving_content_hz", 10))
        if not probe.shows_moving_content or hz <= 0:
            return None
        watcher = MovingAreaWatcher(probe, driver.log, hz).start()
        watcher.show_to(driver.live)
        return watcher

    def check_disk(self, run_dir: Path):
        need_gb = float(self.config.get("runs.min_free_gb", 0) or 0)
        if need_gb <= 0:
            return
        free_gb = shutil.disk_usage(run_dir.parent).free / 1e9
        if free_gb < need_gb:
            raise DiskFull(f"Only {free_gb:.0f} GB free for the results; a run needs {need_gb:.0f} GB for its "
                           f"recording, so the series stops here (the runs so far are kept)")

    def capture_record(self, run_dir: Path, recording: FFmpegCapture):
        record = {"version": 1, "command": recording.command(), "fps": recording.fps,
                  "layout": self.layout.to_dict(), "cpus": recording.cpus, "draw_mouse": recording.draw_mouse,
                  "encoder": recording.encoder, "file": "capture.mkv"}
        (run_dir / "capture.json").write_text(json.dumps(record, indent=2))

    def diagnostics(self, run_dir: Path, probe, label: str):
        shots = run_dir / "screenshots"
        shots.mkdir(exist_ok=True)
        try:
            if hasattr(self.desktop, "screenshot"):
                self.desktop.screenshot(shots / f"{label}.png", self.config.tool("ffmpeg"))
        except Exception:
            pass
        if probe is not None:
            try:
                probe.dump(shots / f"{label}-ui.json")
            except Exception as ex:
                (shots / f"{label}-ui-error.txt").write_text(f"{type(ex).__name__}: {ex}")

    def check_mail_destinations(self, run_dir: Path, meta: dict):
        """After every run: the app's mail connections went only to the mail server's addresses (network.jsonl);
        otherwise the run is a technical failure (WrongServer), the series stops, and the test password must be
        changed, as it may have gone to another server."""
        from .evidence import RunEvidence
        elsewhere = RunEvidence(run_dir, None).mail_elsewhere()
        if not elsewhere:
            return
        ports = sorted({c["remote_port"] for c in elsewhere})
        meta["wrong_server"] = {"connections": len(elsewhere), "ports": ports,
                                "processes": sorted({c.get("process") or "?" for c in elsewhere})}
        meta["status"] = "failed"
        meta["failure"] = "wrong-server"
        meta["error"] = (f"WrongServer: {len(elsewhere)} connection(s) on mail ports ({', '.join(map(str, ports))}) "
                         f"to other addresses than the mail server's; the test password may have gone to another "
                         f"server and must be changed")
        with open(run_dir / "error.txt", "a", encoding="utf-8") as error:
            error.write(meta["error"] + "\n")
        self.progress(f"    {meta['error']}")

    @staticmethod
    def user_actions(log_path: Path, variables: TextVariables) -> dict:
        from .scenario import Action
        events = [e for e in EventLog.read(log_path) if e["type"] == "input" and e.get("phase") == "step"]
        actions = [Action(e["action"], e.get("arg")) for e in events]
        listing = [variables.redact(a.describe()) for a in actions]
        return {"user_actions": sum(a.user_action_count for a in actions), "action_list": listing,
                "prepare_actions": [variables.redact(Action(e["action"], e.get("arg")).describe())
                                    for e in EventLog.read(log_path) if e["type"] == "input"
                                    and e.get("phase") == "prepare" and e["action"] != "launch"]}

    def execute(self, comparison: str, task: str, app_id: str, run_id: str, warmup: bool, order: int,
                reference_run: bool = False, record: bool = True, attempt: int = 1) -> Path:
        from .probe import Probes
        scenario = self.scenarios.get(task)
        app_scenario = scenario.for_app(app_id)
        run_dir = self.run_dir(comparison, task, app_id, run_id)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        app_spec = self.config.expand(self.config.app(app_id), app_id)
        lifecycle = self.lifecycles.get(app_id) or AppLifecycle()
        meta = {"run": run_id, "app": app_id, "task": task, "comparison": comparison, "warmup": warmup,
                "order": order, "attempt": attempt, "layout": self.layout.to_dict(),
                "started": datetime.now(timezone.utc).isoformat(), "status": "running",
                "task_timeout_s": self.task_timeout_s(scenario)}
        if self.versions:
            meta["app_version"] = self.versions(app_id)
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        log = EventLog(run_dir / "driver.jsonl")
        app = lifecycle.app_process(app_id, app_spec, self.desktop, self.layout.app_region, log,
                                    run_dir / "app-output.log")
        probe = Probes.create(app_spec.get("probe"), self.config)
        driver = self.driver(app, app_id, log, app_scenario, scenario, reference_run, probe, run_dir / "verify.json")
        probe.redact = driver.variables.redact
        marker = None
        recording = None
        watcher = None
        moving = None
        marks = {}
        started_utc = time.time()
        log.clock("start")
        try:
            self.check_disk(run_dir)
            self.restore(app_id, scenario.start_state, run_dir)
            lifecycle.reset()
            if self.rotation.enabled and scenario.start_state.get("server"):
                driver.variables.values["account.password"] = self.rotation.rotate()
                meta["password_rotated"] = True
            log.write("restored", start_state=scenario.start_state)
            watcher = self.network_watcher(run_dir, app, app_id)
            if app_scenario.prepare:
                preview = self.capture(None, run_dir / "ffmpeg-prepare.log")
                driver.live = preview.start()
                try:
                    driver.do_actions(app_scenario.prepare, "prepare")
                    if probe.method != "none":
                        probe.attach(app, float(app_spec.get("probe", {}).get("timeout_s", 120)))
                        meta["preparations"] = probe.prepare(self.account.server if self.account else None)
                        moving = self.moving_watcher(probe, driver)
                finally:
                    preview.stop()
            recording = self.capture(run_dir / "capture.mkv" if record else None, run_dir / "ffmpeg.log")
            self.capture_record(run_dir, recording)
            self.live_checks(driver, recording, app_id, task, app_scenario, reference_run)
            driver.live = recording.start()
            if moving is not None:
                moving.show_to(driver.live)
            x, y = self.layout.marker_screen_position
            marker = self.desktop.marker_window(x, y, self.layout.marker)
            driver.marker = marker
            driver.marker_burst("start")
            marks["recording"] = time.time()
            try:
                if app_scenario.flow:
                    from .flows import Flows
                    meta["flow_path"] = Flows.run(app_scenario.flow, driver, probe,
                                                  app_scenario.flow.get("final") or {})
                else:
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
            if driver.verify_result is not None:
                meta["inbox_complete"] = driver.verify_result.get("inbox_complete")
            try:
                if app_scenario.finish:
                    driver.do_actions(app_scenario.finish, "finish")
                    meta["finished_sequence"] = True
                finished = lifecycle.finish(driver, probe)
                if finished is not None:
                    meta["finish"] = finished
            except Exception as ex:
                if app_scenario.finish_required:
                    raise FinishError(f"{app_id}: finishing sequence failed: {ex}") from ex
                raise
        except SeriesStop as ex:
            meta["status"] = "failed"
            meta["failure"] = ex.failure
            meta["error"] = driver.variables.redact(f"{type(ex).__name__}: {ex}")
            (run_dir / "error.txt").write_text(driver.variables.redact(traceback.format_exc()))
            self.progress(f"    {meta['error']}")
            self.diagnostics(run_dir, probe, "stop")
        except Exception as ex:
            meta["status"] = "failed"
            meta["failure"] = "no-reaction" if isinstance(ex, NoReaction) else "technical"
            meta["error"] = driver.variables.redact(f"{type(ex).__name__}: {ex}")
            (run_dir / "error.txt").write_text(driver.variables.redact(traceback.format_exc()))
            self.progress(f"    run failed: {meta['error']}")
            self.diagnostics(run_dir, probe, "failure")
            try:
                recovered = lifecycle.after_failure(driver, probe)
                if recovered is not None:
                    meta["after_failure"] = recovered
            except Exception as recovery:
                meta["after_failure_error"] = driver.variables.redact(f"{type(recovery).__name__}: {recovery}")
        finally:
            if moving is not None:
                moving.stop()
            if recording:
                recording.stop()
            if marker:
                marker.close()
            probe.close()
            meta["closed_cleanly"] = app.close()
            meta.update(app.notes())
            try:
                closed = lifecycle.after_close()
                if closed is not None:
                    meta["after_close"] = closed
            except Exception as ex:
                meta["after_close_error"] = driver.variables.redact(f"{type(ex).__name__}: {ex}")
            log.write("closed")
            if watcher is not None:
                watcher.stop()
                watcher.log.close()
            log.clock("end")
            log.close()
            meta["finished"] = datetime.now(timezone.utc).isoformat()
            meta.update(self.user_actions(run_dir / "driver.jsonl", driver.variables))
            if watcher is not None:
                self.check_mail_destinations(run_dir, meta)
            if self.server_log is not None and self.server_log.enabled:
                try:
                    events = EventLog.read(run_dir / "driver.jsonl")
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
    dropped frames) is recorded again at the end of the plan, at most `runs.retries` times, and listed in the report;
    a run whose mail connections went to another server than the mail server stops the series (the next run would
    send the password there again). Timeouts and wrong results are measurements and are never recorded again."""

    def __init__(self, config, executor: RunExecutor, progress=print, analyzer=None, pressure_log: Path | None = None):
        self.config = config
        self.executor = executor
        self.progress = progress
        self.analyzer = analyzer
        self.pressure_log = pressure_log

    def outcome(self, run_dir: Path) -> str:
        meta = json.loads((run_dir / "meta.json").read_text())
        if meta.get("failure") == "wrong-server":
            return "wrong-server"
        if meta.get("failure") in ("finish", "disk", "stop"):
            return "series-stop"
        if meta.get("status") == "failed":
            return "technical"
        if self.analyzer is None:
            status = meta["status"]
        else:
            analysis = self.analyzer.analyze_safely(run_dir)
            status = "technical" if analysis.get("status") == "failed" and analysis.get("failure") == "technical" \
                else analysis.get("status", "failed")
        if status != "technical" and self.cpu_stalled(run_dir):
            return "technical"
        return status

    def cpu_stalled(self, run_dir: Path) -> bool:
        """The session's CPU stall share during the run above `runs.max_cpu_pressure_pct` (Linux)."""
        if self.pressure_log is None:
            return False
        from .pressure import CpuPressure, CpuPressureLog
        limit = CpuPressure.configured_limit(self.config)
        result = CpuPressure(CpuPressureLog.read(self.pressure_log), limit).write(run_dir)
        if result and result["over_limit"]:
            self.progress(f"    CPU stall {result['pct']:.1f} % during the {result['basis']} (limit {limit:g} %): "
                          f"recorded again at the end of the series")
            return True
        return False

    def done_before(self, run_dir: Path) -> bool:
        meta_path = run_dir / "meta.json"
        if not meta_path.exists():
            return False
        meta = json.loads(meta_path.read_text())
        if meta.get("status") not in ("complete", "timeout"):
            return False
        pressure = run_dir / "cpu-pressure.json"
        if pressure.exists() and json.loads(pressure.read_text()).get("over_limit"):
            return False
        analysis = run_dir / "analysis.json"
        if analysis.exists():
            data = json.loads(analysis.read_text())
            return not (data.get("status") == "failed" and data.get("failure") == "technical")
        return True

    def run_comparison(self, comparison_id: str, tasks: list[str] | None = None, resume: bool = True,
                       measured: int | None = None, warmup: int | None = None, only_apps: list[str] | None = None):
        spec = self.config.comparison(comparison_id)
        measured = int(measured if measured is not None else self.config.get("runs.measured", 5))
        warmup = int(warmup if warmup is not None else self.config.get("runs.warmup", 1))
        retries = int(self.config.get("runs.retries", 2))
        apps = [a for a in self.config.group_apps(comparison_id) if not only_apps or a in only_apps]
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
                if outcome == "wrong-server":
                    raise SeriesStop(f"{comparison_id} {task} {app_id} {run_id}: the series stops: "
                                     + json.loads((run_dir / "meta.json").read_text())["error"])
                if outcome == "series-stop":
                    raise SeriesStop(f"{comparison_id} {task} {app_id} {run_id}: the series stops (see "
                                     f"{run_dir / 'error.txt'})")
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
        (out / "server-evidence.json").rename(out / "after-series.json")
        (out / "server-log.txt").rename(out / "after-series-server-log.txt")
