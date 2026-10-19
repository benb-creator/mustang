import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .capture import CaptureLayout, FFmpegCapture
from .corpus import CorpusGenerator, CorpusSpec
from .driver import AppProcess, DriverError, EventLog, FocusError, NoReaction, ScenarioDriver, StepTimeout, TextVariables
from .runner import FinishError, Orchestrator
from .scenario import ScenarioLibrary
from .settle import Rect
from .winapps import (LocalCommands, OutlookClassicProfile, ParulaProfile, ParulaUpdates, ProcessGuard,
                      SessionState, WindowsSettings)
from .winflows import FlowError, NewOutlookRemoval, SetupFlows, WindowsFlowContext
from .winnet import WindowsConnectionWatcher
from .winprobe import UiaAppMap, UiaProbe


class WindowsBenchError(Exception):
    pass


class InboxExpectations:
    """What a complete Inbox listing is, from the corpus (no message is generated: counts, keywords and the
    envelopes of the oldest and the newest message come from the generator's layout)."""

    @staticmethod
    def compute(config) -> dict:
        generator = CorpusGenerator(CorpusSpec.from_dict(config.get("corpus")))
        expected = generator.expected()
        inbox = next(name for name, f in expected["folders"].items() if f["role"] == "inbox")
        count = expected["folders"][inbox]["count"]
        unread = sum(1 for i in range(count) if "$seen" not in generator.keywords(inbox, i))
        return {**expected, "inbox_folder": inbox, "inbox_messages": count, "inbox_unread": unread,
                "inbox_oldest_subject": generator.envelope(inbox, 0).subject if count else None,
                "inbox_newest_subject": generator.envelope(inbox, count - 1).subject if count else None}


class DisplayPlan:
    """The recorded area: the same for every app of the session. The app window gets 1280×940 logical pixels
    (physical pixels at the display's scale), at the primary monitor's top left, with the sync marker below it; a
    work area too small for that gets the largest such window that fits (at least 1100×700 logical)."""

    @staticmethod
    def compute(work_area: Rect, scale_percent: int, marker_cell: int = 12, gap: int = 4) -> dict:
        scale = scale_percent / 100
        marker_height = marker_cell + gap + 2
        width = min(round(1280 * scale), work_area.width)
        height = min(round(940 * scale), work_area.height - marker_height)
        width -= width % 2
        height -= height % 2
        ok = width >= 1100 * scale and height >= 700 * scale
        region = Rect(work_area.x, work_area.y, width, height)
        park_x = work_area.x + work_area.width - 8
        park_y = work_area.y + work_area.height - 8
        if park_x < region.x + width + 4:
            park_x = region.x + width + 4
        return {"ok": ok, "app_region": region.to_dict(), "pointer_park": {"x": park_x, "y": park_y},
                "scale_percent": scale_percent, "logical_size": f"{round(width / scale)}x{round(height / scale)}",
                "fix": None if ok else "Set the display scaling to 100 % (Settings → System → Display) or use a "
                                       "screen with at least 1100×720 logical pixels"}


class Check:
    def __init__(self, name: str, ok: bool, detail: str = "", fix: str | None = None, fatal: bool = True):
        self.name, self.ok, self.detail, self.fix, self.fatal = name, ok, detail, fix, fatal

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "detail": self.detail, "fix": self.fix, "fatal": self.fatal}


class Prerequisites:
    """Checked before anything changes on the computer; every failed check says how to fix it."""

    def __init__(self, config, desktop, core, progress=print, commands=None):
        self.config = config
        self.desktop = desktop
        self.core = core
        self.progress = progress
        self.commands = commands or subprocess.run

    def powershell(self, script: str) -> str:
        out = self.commands(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                            timeout=120)
        return (out.stdout or "").strip()

    def apps(self) -> list[Check]:
        checks = []
        for app_id in self.config.group_apps(self.first_comparison()):
            spec = self.config.app(app_id)
            launch = self.config.expand(spec.get("launch") or [])
            if spec.get("installed_check"):
                found = bool(self.powershell(spec["installed_check"]))
                checks.append(Check(f"{spec.get('name', app_id)} installed", found,
                                    "found" if found else "not found", spec.get("install_hint")))
            elif launch:
                found = Path(launch[0]).exists()
                checks.append(Check(f"{spec.get('name', app_id)} installed", found, launch[0] if found else
                                    f"missing: {launch[0]}", spec.get("install_hint")))
        return checks

    def first_comparison(self) -> str:
        return next(iter(self.config.get("comparisons")))

    def display(self) -> tuple[Check, dict]:
        primary = self.desktop.primary_monitor()
        plan = DisplayPlan.compute(primary["work_area"], self.desktop.scale_percent(),
                                   int(self.config.get("display.marker.cell", 12)))
        detail = (f"scaling {plan['scale_percent']} %, work area {primary['work_area'].width}×"
                  f"{primary['work_area'].height}, app window {plan['app_region']['width']}×"
                  f"{plan['app_region']['height']} ({plan['logical_size']} logical)")
        return Check("Display", plan["ok"], detail, plan["fix"]), plan

    def disk(self, root: Path) -> Check:
        need_gb = float(self.config.get("windows.min_free_gb", 60))
        free_gb = shutil.disk_usage(root).free / 1e9
        return Check("Free disk space", free_gb >= need_gb, f"{free_gb:.0f} GB free on {root.anchor or root}, "
                     f"{need_gb:.0f} GB needed (lossless screen recordings)",
                     f"Free at least {need_gb - free_gb:.0f} GB on that drive, or start the script from a folder on "
                     f"a drive with more space")

    def ffmpeg(self) -> Check:
        ffmpeg = self.config.tool("ffmpeg")
        filters = self.commands([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=60)
        encoders = self.commands([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=60)
        ok = "ddagrab" in (filters.stdout or "") and "libx264rgb" in (encoders.stdout or "")
        return Check("ffmpeg with ddagrab and libx264rgb", ok, ffmpeg)

    def account(self) -> list[Check]:
        try:
            report = self.core.check_account(repair=False)
        except Exception as ex:
            return [Check("Mail account reachable", False, f"{type(ex).__name__}: {ex}",
                          "Check the server name, the e-mail address and the password")]
        counts = ", ".join(f"{name} {v.get('actual')}/{v.get('expected')}" for name, v in
                           (report.get("folders") or {}).items())
        return [Check("Mail account reachable", True, f"logged in ({report.get('protocol', 'imap')})"),
                Check("Mail account seeded", bool(report.get("ok")), counts or "no folder counts",
                      "The account isn't seeded with the test messages (or differs from them). Seeding is done "
                      "once by the Parula team: please tell them, and run this script again afterwards.")]

    def running_apps(self) -> Check:
        names = [n for app_id in self.config.group_apps(self.first_comparison())
                 for n in self.config.app(app_id).get("process_names") or []]
        running = ProcessGuard(self.desktop).running(names)
        return Check("The test apps are closed", not running, ", ".join(running) or "none running",
                     "Close " + ", ".join(running) + " (also in the notification area)" if running else None,
                     fatal=False)

    def run(self, root: Path) -> dict:
        checks = [Check("Windows", True, self.powershell("(Get-CimInstance Win32_OperatingSystem).Caption"),
                        fatal=False)]
        checks += self.apps()
        display, plan = self.display()
        checks += [display, self.disk(root), self.ffmpeg(), self.running_apps()]
        checks += self.account()
        ok = all(c.ok or not c.fatal for c in checks)
        return {"ok": ok, "checks": [c.to_dict() for c in checks], "display": plan,
                "checked_utc": datetime.now(timezone.utc).isoformat()}


class OpenApps:
    """Windows of other apps that are open on the desktop (they could cover the recorded area, show pop-ups or use
    the CPU): the shell, the console running the test and system windows don't count."""

    def __init__(self, desktop):
        self.desktop = desktop

    def names(self) -> list[str]:
        shell_classes = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow"}
        own_processes = {"powershell.exe", "pwsh.exe", "windowsterminal.exe", "openconsole.exe", "conhost.exe",
                         "python.exe", "textinputhost.exe", "searchhost.exe", "startmenuexperiencehost.exe",
                         "shellexperiencehost.exe", "lockapp.exe", "applicationframehost.exe"}
        names = set()
        for hwnd, pid, title, cls in self.desktop.top_level_windows():
            if cls in shell_classes or not title or self.desktop.is_minimized(hwnd):
                continue
            geometry = self.desktop.window_geometry(hwnd)
            if geometry.width < 200 or geometry.height < 150 or not self.desktop.has_caption(hwnd):
                continue
            exe = self.desktop.process_image_name(pid)
            if exe and exe not in own_processes:
                names.add(exe)
        return sorted(names)

    def wait_closed(self, progress, timeout_s: float = 600, poll_s: float = 10) -> list[str]:
        """Asks to close them and waits; what is still open after `timeout_s` is returned (and recorded)."""
        deadline = time.monotonic() + timeout_s
        announced = None
        while True:
            open_now = self.names()
            if not open_now or time.monotonic() > deadline:
                return open_now
            if open_now != announced:
                progress(f"Please close these apps for the test (it waits up to {timeout_s / 60:.0f} minutes): "
                         f"{', '.join(open_now)}")
                announced = open_now
            time.sleep(poll_s)


class CoreServices:
    """The shared core's parts that the Windows session uses (account check and repair, result folder, network
    log, evidence, analysis): the one place where this module meets them."""

    def __init__(self, config, progress=print):
        self.config = config
        self.progress = progress
        self._server = None

    def account_server(self):
        from .account import AccountServer
        if self._server is None:
            self._server = AccountServer.from_config(self.config)
        return self._server

    def check_account(self, repair: bool) -> dict:
        from .account import AccountCheck
        generator = CorpusGenerator(CorpusSpec.from_dict(self.config.get("corpus")))
        return AccountCheck(self.account_server(), generator, self.progress).run(repair=repair)

    def result_folder(self, parent: Path):
        from .resultfolder import ResultFolder
        return ResultFolder.create(parent, "windows")

    def network_log(self, path: Path):
        from .netwatch import NetworkLog
        return NetworkLog(path)

    def mail_server_addresses(self) -> dict:
        from .evidence import MailServerAddresses
        return MailServerAddresses.for_server(self.account_server())

    def run_evidence(self, run_dir: Path, addresses: dict) -> dict:
        from .evidence import NetworkOwners, RunEvidence
        owners = NetworkOwners(Path(run_dir).parents[3] / "logs" / "network-owners.json")
        return RunEvidence(run_dir, owners).summarize(addresses)

    def analyzer(self):
        from .analyze import RunAnalyzer
        return RunAnalyzer(self.config, ScenarioLibrary(self.config.scenario_dir))

    def finish(self, folder, config_path: Path) -> dict:
        bench = Path(__file__).resolve().parent.parent / "bench.py"
        out = subprocess.run([sys.executable, str(bench), "--config", str(config_path), "analyze", "--results",
                              str(folder.path)], capture_output=True, text=True)
        (folder.path / "logs" / "analyze.log").write_text((out.stdout or "") + (out.stderr or ""), encoding="utf-8")
        return {"returncode": out.returncode}


class WindowsAppProcess(AppProcess):
    """An app whose windows come and go during its setup (Outlook's setup dialog before its main window, new
    Outlook's launcher that exits at once): its window is the keeper's main window, else the frontmost window of
    its process tree; keys go to it when the foreground window belongs to that tree."""

    def __init__(self, app_id: str, spec: dict, desktop, region: Rect, log, output: Path | None, process_ids):
        super().__init__(app_id, spec, desktop, region, log, output)
        self.process_ids = process_ids
        self.keeper = None

    def app_windows(self) -> list:
        pids = set(self.process_ids())
        return [hwnd for hwnd, pid, _, _ in self.desktop.top_level_windows() if pid in pids]

    def ensure_window(self, timeout_s: float = 120):
        deadline = time.monotonic() + timeout_s
        while True:
            main = self.keeper.main if self.keeper is not None else None
            if main is not None and self.desktop.is_window(main):
                self.window = main
                return main
            windows = self.app_windows()
            if windows:
                self.window = windows[0]
                return self.window
            if time.monotonic() > deadline:
                raise DriverError(f"{self.app_id}: no window of its processes within {timeout_s:.0f} s")
            time.sleep(0.2)

    def foreground_is_app(self) -> bool:
        foreground = self.desktop.user32.GetForegroundWindow()
        return bool(foreground) and self.desktop.window_process_id(foreground) in set(self.process_ids())

    def ensure_foreground(self):
        if self.foreground_is_app():
            return
        self.desktop.focus_window(self.ensure_window())
        time.sleep(0.2)
        if not self.foreground_is_app():
            raise FocusError(f"{self.app_id}: its window isn't in the foreground, so no keys were sent")


class AppAdapter:
    """One app's part of the session: its setup flow and UI Automation map, the fresh state before every run,
    what happens after a run, and what is undone at the end."""

    kind = ""

    def __init__(self, session: "WindowsSession", app_id: str):
        self.session = session
        self.app_id = app_id
        self.spec = session.config.expand(session.config.app(app_id), app_id)
        self.map = UiaAppMap.load(session.elements_path, self.kind)

    def flow(self):
        return SetupFlows.create(self.kind, **dict(self.spec.get("flow_options") or {}))

    def probe(self) -> UiaProbe:
        return UiaProbe(self.map)

    def before_session(self) -> list[str]:
        return []

    def prepare(self, probe: UiaProbe, driver: ScenarioDriver):
        pass

    def reset(self):
        pass

    def after_run(self, ctx: WindowsFlowContext, run_ok: bool) -> dict:
        return {}

    def after_close(self) -> dict:
        return {}

    def cleanup(self) -> list[str]:
        return []


class ParulaAdapter(AppAdapter):
    kind = "parula"

    def __init__(self, session, app_id):
        super().__init__(session, app_id)
        self.profile = ParulaProfile(session.state, session.root / "state" / "user-profiles")
        self.updates = ParulaUpdates(session.state, Path(self.spec["launch"][0]).parent)

    def before_session(self) -> list[str]:
        notes = []
        moved = self.profile.move_user_profile_aside()
        if moved:
            notes.append(f"Parula: the computer user's Parula profile was moved aside for the session and moved "
                         f"back afterwards ({len(moved)} folders)")
        if self.updates.disable():
            notes.append("Parula: its update check was off for the session (resources/app-update.yml renamed), "
                         "like the Linux .deb, which has none")
        return notes

    def reset(self):
        self.profile.reset()

    def prepare(self, probe: UiaProbe, driver: ScenarioDriver):
        """The first screen plays a background video: paused before the screen can settle (not a user action)."""
        found = probe.element("button.pause", timeout_s=30)
        if found is not None:
            driver.desktop.click(*found.center)
            driver.log.write("input", t=EventLog.now(), phase="prepare", action="click", arg="button.pause")
            if driver.park:
                driver.desktop.move(*driver.park)

    def after_close(self) -> dict:
        self.profile.mark()
        self.profile.reset()
        return {"profile_deleted": True}

    def cleanup(self) -> list[str]:
        done = []
        try:
            self.profile.mark()
            self.profile.reset()
        except Exception as ex:
            done.append(f"Parula profile: {ex}")
        restored = self.profile.restore_user_profile()
        if restored:
            done.append("Parula: the user's profile is back")
        self.updates.restore()
        return done


class OutlookClassicAdapter(AppAdapter):
    kind = "outlook-classic"

    def __init__(self, session, app_id):
        super().__init__(session, app_id)
        self.profile = OutlookClassicProfile(session.state, session.email,
                                             str(self.spec.get("profile_name", "ParulaBench")),
                                             runner=session.commands)

    def before_session(self) -> list[str]:
        self.profile.remember_existing()
        return [f"Outlook (classic): started with its own profile '{self.profile.profile_name}' (/profile), which "
                f"holds only the test account and is deleted after every run"]

    def reset(self):
        self.profile.create_empty()

    def after_close(self) -> dict:
        return self.profile.delete()

    def cleanup(self) -> list[str]:
        removed = self.profile.delete()
        return [f"Outlook (classic): profile removed {removed}"] if any(removed.values()) else []


class NewOutlookAdapter(AppAdapter):
    kind = "outlook-new"

    def removal(self) -> NewOutlookRemoval:
        return NewOutlookRemoval(self.session.email)

    def reset(self):
        last = self.session.state.get("outlook_new_removed_monotonic_utc")
        gap_s = float(self.spec.get("min_gap_after_removal_min", 10)) * 60
        if last:
            wait = gap_s - (time.time() - float(last))
            if wait > 0:
                self.session.progress(f"    waiting {wait / 60:.0f} min since new Outlook's last account removal")
                time.sleep(wait)

    def after_run(self, ctx: WindowsFlowContext, run_ok: bool) -> dict:
        """Keeps the account until the Inbox lists every message for `keep_after_complete_min` (the Microsoft Cloud
        has then stopped importing), at most `keep_max_min`; then removes it from all devices."""
        keep_after = float(self.spec.get("keep_after_complete_min", 3)) * 60
        keep_max = float(self.spec.get("keep_max_min", 120)) * 60
        started = time.monotonic()
        complete_since = None
        listed = {}
        while time.monotonic() - started < keep_max:
            listed = ctx.probe.inbox_listed(ctx.expected)
            if listed.get("complete"):
                complete_since = complete_since or time.monotonic()
                if time.monotonic() - complete_since >= keep_after:
                    break
            else:
                complete_since = None
            time.sleep(15)
        ctx.log.write("cloud_wait", seconds=round(time.monotonic() - started), listed=listed)
        self.session.state.set("outlook_new_account_pending", True)
        self.removal().run(ctx)
        self.session.state.set("outlook_new_account_pending", False)
        self.session.state.set("outlook_new_removed_monotonic_utc", time.time())
        return {"kept_s": round(time.monotonic() - started), "removed": True}

    def cleanup(self) -> list[str]:
        if not self.session.state.get("outlook_new_account_pending"):
            return []
        try:
            self.session.remove_new_outlook_account(self)
            return ["New Outlook: the test account was removed (from all devices)"]
        except Exception as ex:
            return [f"New Outlook: REMOVE THE TEST ACCOUNT BY HAND (Settings → Accounts → Manage → Remove → "
                    f"Remove from all devices): {ex}"]


class WindowsRunExecutor:
    """One run of one app, for the shared core's `Orchestrator` (plan, resume, re-recording at the end)."""

    server_log = None

    def __init__(self, session: "WindowsSession"):
        self.session = session
        self.config = session.config
        self.desktop = session.desktop
        self.layout = CaptureLayout.from_config(self.config)

    def run_dir(self, comparison: str, task: str, app_id: str, run_id: str) -> Path:
        return self.session.folder.run_dir(app_id, task, run_id)

    def variables(self) -> TextVariables:
        values = {"account.email": self.session.email, "account.username": self.session.email,
                  "account.name": str(self.config.get("account.display_name", "")),
                  "account.password": self.session.password, "server.host": self.session.server_host,
                  "server.jmap_url": str(self.config.get("server.jmap_session_url") or
                                         f"https://{self.session.server_host}/.well-known/jmap")}
        return TextVariables(values, {"account.password"})

    def capture(self, record_path: Path | None, log_path: Path) -> FFmpegCapture:
        settle = self.config.get("settle") or {}
        return FFmpegCapture(self.desktop, self.config.tool("ffmpeg"), self.layout,
                             int(self.config.get("capture.fps", 60)), record_path,
                             int(self.config.get("capture.live_scale", 4)), self.config.get("capture.cpus"),
                             bool(self.config.get("capture.draw_mouse", False)), log_path,
                             int(settle.get("live_pixel_threshold", 6)), int(settle.get("min_changed_pixels", 150)))

    def diagnostics(self, run_dir: Path, probe: UiaProbe | None, label: str):
        shots = run_dir / "screenshots"
        try:
            self.desktop.screenshot(shots / f"{label}.png")
        except Exception as ex:
            (shots / f"{label}-screenshot-error.txt").write_text(str(ex))
        if probe is not None and probe.tree is not None:
            try:
                probe.dump(shots / f"{label}-ui-dump.json")
            except Exception as ex:
                (shots / f"{label}-ui-dump-error.txt").write_text(str(ex))

    def execute(self, comparison: str, task: str, app_id: str, run_id: str, warmup: bool, order: int,
                reference_run: bool = False, record: bool = True, attempt: int = 1) -> Path:
        session = self.session
        adapter = session.adapters[app_id]
        run_dir = self.run_dir(comparison, task, app_id, run_id)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        (run_dir / "screenshots").mkdir(parents=True)
        settle = self.config.get("settle") or {}
        meta = {"run": run_id, "app": app_id, "task": task, "comparison": comparison, "warmup": warmup,
                "order": order, "attempt": attempt, "layout": self.layout.to_dict(),
                "started": datetime.now(timezone.utc).isoformat(), "status": "running",
                "task_timeout_s": float(settle.get("task_timeout_s", 7200)), "app_version": session.versions.get(app_id)}
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        log = EventLog(run_dir / "driver.jsonl")
        variables = self.variables()
        probe = adapter.probe()
        app = WindowsAppProcess(app_id, adapter.spec, self.desktop, self.layout.app_region, log,
                                run_dir / "app-output.log", probe.process_ids)
        probe.app = app
        probe.redact = variables.redact
        recording = marker = keeper = watcher = None
        ctx = None
        log.clock("start")
        try:
            account = session.core.check_account(repair=True)
            (run_dir / "account.json").write_text(json.dumps(account, indent=2, ensure_ascii=False))
            if not account.get("ok"):
                raise WindowsBenchError("the test account differs from the corpus even after the repair "
                                        "(account.json)")
            adapter.reset()
            addresses = session.core.mail_server_addresses()
            netlog = session.core.network_log(run_dir / "network.jsonl")
            watcher = WindowsConnectionWatcher(
                netlog, app_id, lambda: {app.process.pid} if app.process else set(),
                adapter.map.process_names, float(self.config.get("network.poll_hz", 10)),
                set(addresses.get("addresses") or []))
            watcher.start()
            for host, ips in (addresses.get("hosts") or {}).items():
                netlog.write("resolve", t=EventLog.now(), utc=time.time(), host=host, addresses=ips)
            driver = ScenarioDriver(self.desktop, app, session.calibration(), variables, log,
                                    type_delay_ms=int(self.config.get("driver.type_delay_ms", 40)),
                                    quiet_s=float(settle.get("quiet_s", 1.0)),
                                    step_timeout_s=float(settle.get("step_timeout_s", 300)),
                                    task_timeout_s=float(settle.get("task_timeout_s", 7200)),
                                    park=session.park_point, no_reaction_s=float(settle.get("no_reaction_s", 60)))
            preview = self.capture(None, run_dir / "ffmpeg-prepare.log")
            driver.live = preview.start()
            try:
                app.launch(place_window=False)
                log.write("input", t=EventLog.now(), phase="prepare", action="launch", arg=None)
                keeper = self.desktop.window_keeper(probe.process_ids, self.layout.app_region,
                                                    dict(adapter.spec.get("window") or {}),
                                                    adapter.spec.get("window_offsets") or {}).start()
                app.keeper = keeper
                probe.attach(app, float((adapter.spec.get("window") or {}).get("timeout_s", 180)))
                adapter.prepare(probe, driver)
                status, _ = driver.live.wait_settled(EventLog.now(), float(adapter.spec.get("start_quiet_s", 3)),
                                                     float((adapter.spec.get("window") or {}).get("timeout_s", 180)),
                                                     "prepare", expect_change=False)
                if status != "settled":
                    raise WindowsBenchError(f"{app_id}: its first screen didn't settle")
            finally:
                preview.stop()
            recording = self.capture(run_dir / "capture.mkv" if record else None, run_dir / "ffmpeg.log")
            driver.live = recording.start()
            x, y = self.layout.marker_screen_position
            marker = self.desktop.marker_window(x, y, self.layout.marker)
            driver.marker = marker
            driver.marker_burst("start")
            ctx = WindowsFlowContext(driver, probe, session.expected, run_dir / "screenshots",
                                     quiet_s=float(settle.get("quiet_s", 1.0)),
                                     step_timeout_s=float(settle.get("step_timeout_s", 300)),
                                     task_timeout_s=float(settle.get("task_timeout_s", 7200)),
                                     no_reaction_s=float(settle.get("no_reaction_s", 60)), progress=session.progress)
            try:
                adapter.flow().run(ctx)
                meta["status"] = "complete"
            except StepTimeout as ex:
                meta["status"] = "timeout"
                meta["timeout"] = {"step": ex.step, "limit_s": ex.limit_s}
                session.progress(f"    time limit reached in step {ex.step}")
            driver.marker_burst("end")
            tail = float(adapter.spec.get("tail_s", 30))
            if tail > 0 and meta["status"] == "complete":
                time.sleep(tail)
                driver.marker_burst("tail-end")
            time.sleep(0.3)
            recording.stop()
            recording = None
            marker.close()
            marker = None
            verify = ctx.verify()
            (run_dir / "verify.json").write_text(json.dumps(verify, indent=2, ensure_ascii=False))
            try:
                meta["after_run"] = adapter.after_run(ctx, meta["status"] == "complete")
            except Exception as ex:
                if adapter.kind == "outlook-new":
                    raise FinishError(f"{app_id}: removing the account failed: {ex}") from ex
                raise
        except FinishError as ex:
            meta.update(status="failed", failure="finish", error=variables.redact(f"{type(ex).__name__}: {ex}"))
            (run_dir / "error.txt").write_text(variables.redact(traceback.format_exc()))
            self.diagnostics(run_dir, probe, "finish-failed")
            session.progress(f"    {meta['error']}")
        except Exception as ex:
            meta.update(status="failed", failure="no-reaction" if isinstance(ex, NoReaction) else
                        "flow" if isinstance(ex, FlowError) else "technical",
                        error=variables.redact(f"{type(ex).__name__}: {ex}"))
            (run_dir / "error.txt").write_text(variables.redact(traceback.format_exc()))
            self.diagnostics(run_dir, probe, "failure")
            session.progress(f"    run failed: {meta['error']}")
        finally:
            if recording:
                recording.stop()
            if marker:
                marker.close()
            if keeper:
                keeper.stop()
                meta["windows_placed"] = keeper.placed
                if keeper.main is not None and self.desktop.is_window(keeper.main):
                    app.window = keeper.main
            meta["closed_cleanly"] = app.close()
            if watcher:
                watcher.stop()
                netlog.close()
            log.write("closed")
            log.clock("end")
            log.close()
            try:
                meta["after_close"] = adapter.after_close()
            except Exception as ex:
                meta["after_close_error"] = variables.redact(str(ex))
            if ctx is not None:
                meta.update(ctx.summary())
            meta["finished"] = datetime.now(timezone.utc).isoformat()
            if watcher:
                try:
                    session.core.run_evidence(run_dir, session.core.mail_server_addresses())
                except Exception as ex:
                    meta["evidence_error"] = variables.redact(f"{type(ex).__name__}: {ex}")
            (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        return run_dir


class Preflight:
    """Before the long series: every app starts from its fresh state, its automation finds the first page of its
    account setup, and its state can be reset again. The UI trees and screenshots go to preflight/ either way."""

    def __init__(self, session: "WindowsSession"):
        self.session = session

    def app(self, app_id: str, out: Path) -> dict:
        session = self.session
        adapter = session.adapters[app_id]
        result = {"app": app_id, "ok": False}
        probe = adapter.probe()
        app = WindowsAppProcess(app_id, adapter.spec, session.desktop, session.executor.layout.app_region, None,
                                out / f"{app_id}-output.log", probe.process_ids)
        probe.app = app
        keeper = None
        try:
            adapter.reset()
            app.launch(place_window=False)
            keeper = session.desktop.window_keeper(probe.process_ids, session.executor.layout.app_region,
                                                   dict(adapter.spec.get("window") or {})).start()
            app.keeper = keeper
            probe.attach(app, 180)
            flow = adapter.flow()
            pages = getattr(flow, "start_pages", None) or [next(iter(adapter.map.pages))]
            page, _ = probe.wait_page(pages, 120)
            result.update(page=page, language=probe.language, ok=page in pages)
            if not result["ok"]:
                result["error"] = f"expected one of {pages}, found '{page}'"
        except Exception as ex:
            result["error"] = f"{type(ex).__name__}: {ex}"
        finally:
            try:
                session.desktop.screenshot(out / f"{app_id}.png")
                if probe.tree is not None:
                    probe.dump(out / f"{app_id}-ui-dump.json")
            except Exception as ex:
                result["diagnostics_error"] = str(ex)
            if keeper:
                keeper.stop()
                if keeper.main is not None and session.desktop.is_window(keeper.main):
                    app.window = keeper.main
            result["closed_cleanly"] = app.close()
            try:
                adapter.after_close()
            except Exception as ex:
                result["reset_error"] = str(ex)
                result["ok"] = False
        return result

    def capture(self, out: Path) -> dict:
        recording = self.session.executor.capture(out / "capture-test.mkv", out / "capture-test-ffmpeg.log")
        try:
            live = recording.start()
            time.sleep(2)
            frames = len(live.arrivals)
        finally:
            recording.stop()
        return {"ok": frames >= 60, "frames_in_2s": frames}

    def network(self) -> dict:
        from .winnet import TcpTable
        rows = TcpTable().rows()
        return {"ok": True, "connections": len(rows)}

    def run(self) -> dict:
        out = self.session.folder.path / "preflight"
        out.mkdir(parents=True, exist_ok=True)
        results = {"capture": self.capture(out), "network": self.network(), "apps": {}}
        for app_id in self.session.app_ids:
            self.session.progress(f"preflight: {app_id}")
            results["apps"][app_id] = self.app(app_id, out)
        results["ok"] = results["capture"]["ok"] and all(a["ok"] for a in results["apps"].values())
        (out / "preflight.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
        return results


class WindowsSession:
    """The whole Windows test in one run: settings, preflight, the interleaved series of all apps (warm-up + 5
    measured runs each, failed runs re-recorded at the end), results, evidence, zip; everything it changed on the
    computer is undone in `cleanup()`, also after an error or Ctrl+C."""

    def __init__(self, config, config_path: Path, root: Path, desktop, core=None, progress=print,
                 password: str | None = None, commands: LocalCommands | None = None):
        self.config = config
        self.commands = commands or LocalCommands()
        self.config_path = Path(config_path)
        self.root = Path(root)
        self.desktop = desktop
        self.progress = progress
        self.core = core or CoreServices(config, progress)
        self.state = SessionState(self.root / "state" / "session-state.json")
        self.email = str(config.require("account.email"))
        self.server_host = str(config.require("server.host"))
        self.password = password if password is not None else config.secret("account.password_env")
        self.elements_path = Path(config.path(config.get("windows.elements", "uia-elements.yaml")))
        self.comparison = next(iter(config.get("comparisons")))
        self.app_ids = config.group_apps(self.comparison)
        adapter_kinds = {"parula": ParulaAdapter, "outlook-classic": OutlookClassicAdapter,
                         "outlook-new": NewOutlookAdapter}
        self.adapters = {app_id: adapter_kinds[config.app(app_id)["kind"]](self, app_id) for app_id in self.app_ids}
        self.versions: dict[str, str | None] = {}
        self.folder = None
        self.expected: dict = {}
        self.executor = WindowsRunExecutor(self)
        self.notes: list[str] = []

    @property
    def park_point(self) -> tuple[int, int] | None:
        park = self.config.get("display.pointer_park")
        return (int(park["x"]), int(park["y"])) if isinstance(park, dict) else None

    def calibration(self):
        from .winflows import PointLocator
        return PointLocator(self.executor.layout.app_region)

    def remove_new_outlook_account(self, adapter: NewOutlookAdapter):
        """Cleanup after an interrupted run: start new Outlook and remove the test account if it's still there."""
        log = EventLog(self.root / "state" / "cleanup-driver.jsonl")
        probe = adapter.probe()
        app = WindowsAppProcess(adapter.app_id, adapter.spec, self.desktop, self.executor.layout.app_region, log,
                                None, probe.process_ids)
        probe.app = app
        keeper = None
        try:
            app.launch(place_window=False)
            keeper = app.keeper = self.desktop.window_keeper(probe.process_ids, self.executor.layout.app_region,
                                                             dict(adapter.spec.get("window") or {})).start()
            probe.attach(app, 180)
            driver = ScenarioDriver(self.desktop, app, self.calibration(), self.executor.variables(), log,
                                    park=self.park_point)
            ctx = WindowsFlowContext(driver, probe, self.expected, self.root / "state")
            page, _ = probe.wait_page(None, 120)
            if page != "add-account":
                adapter.removal().run(ctx)
            self.state.set("outlook_new_account_pending", False)
        finally:
            if keeper:
                keeper.stop()
            app.close()
            log.close()

    def run(self) -> Path:
        self.folder = self.core.result_folder(self.root)
        self.progress(f"results: {self.folder.path}")
        self.expected = InboxExpectations.compute(self.config)
        settings = WindowsSettings(self.state, self.commands)
        self.notes += settings.apply()
        for adapter in self.adapters.values():
            self.notes += adapter.before_session()
            self.versions[adapter.app_id] = self.app_version(adapter)
        self.folder.write_manifest(deviations=list(self.config.get("deviations") or []) + self.notes,
                                   procedures=list(self.config.get("procedures") or []),
                                   apps={a: {"name": self.config.app(a).get("name"), "version": v}
                                         for a, v in self.versions.items()},
                                   corpus={k: self.expected.get(k) for k in
                                           ("profile", "inbox_messages", "inbox_unread", "attachment_messages",
                                            "inbox_oldest_subject", "inbox_newest_subject")})
        still_open = OpenApps(self.desktop).wait_closed(self.progress)
        if still_open:
            self.notes.append(f"Windows: other apps were open during the session: {', '.join(still_open)}")
        self.console_aside()
        self.folder.write_manifest(deviations=list(self.config.get("deviations") or []) + self.notes)
        preflight = Preflight(self).run()
        if not preflight["ok"]:
            raise WindowsBenchError(f"Preflight failed, so the long series didn't start: see "
                                    f"{self.folder.path / 'preflight' / 'preflight.json'}")
        Orchestrator(self.config, self.executor, self.progress, self.core.analyzer()).run_comparison(
            self.comparison, resume=False)
        self.core.finish(self.folder, self.config_path)
        return self.folder.path

    def console_aside(self):
        """The console that runs the test is minimized when it overlaps the recorded area (restored at the end)."""
        console = self.desktop.console_window()
        if not console:
            return
        geometry = self.desktop.window_geometry(console)
        region = self.executor.layout.capture_region
        overlaps = geometry.x < region.x + region.width and region.x < geometry.x + geometry.width and \
            geometry.y < region.y + region.height and region.y < geometry.y + geometry.height
        if overlaps:
            self.desktop.show_window(console, minimized=True)
            self.state.set("console_minimized", int(console))

    def app_version(self, adapter: AppAdapter) -> str | None:
        command = adapter.spec.get("version_command")
        if not command:
            return None
        try:
            out = self.commands.run(command, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        return (out.stdout or "").strip() or None

    def cleanup(self) -> list[str]:
        done = []
        for adapter in self.adapters.values():
            try:
                self.desktop.kill_by_name(adapter.map.process_names)
            except Exception:
                pass
        for adapter in self.adapters.values():
            try:
                done += adapter.cleanup()
            except Exception as ex:
                done.append(f"{adapter.app_id}: cleanup failed: {ex}")
        done += WindowsSettings(self.state, self.commands).revert()
        console = self.state.get("console_minimized")
        if console:
            try:
                self.desktop.show_window(console, minimized=False)
            except Exception:
                pass
            self.state.pop("console_minimized")
        return done


class ReadmeFirst:
    """The note for the person who ran the test: where the results are, how big, what to send."""

    @staticmethod
    def write(folder: Path, zip_path: Path | None, ok: bool, problem: str | None = None) -> str:
        def size(path: Path) -> str:
            total = sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else \
                path.stat().st_size
            return f"{total / 1e9:.1f} GB" if total >= 1e9 else f"{total / 1e6:.0f} MB"

        lines = ["Parula speed test on Windows: " + ("finished." if ok else "stopped before the end."), ""]
        if problem:
            lines += [f"Why: {problem}", ""]
        lines += [f"Results folder: {folder}  ({size(folder)})"]
        if zip_path is not None and zip_path.exists():
            lines += [f"Zip of it:      {zip_path}  ({size(zip_path)})", "",
                      "Please send the zip file to the Parula team (for example as a shared link from OneDrive, "
                      "Google Drive or Dropbox; it is too large for e-mail)."]
        else:
            lines += ["", "Please send the results folder to the Parula team (zip it first)."]
        lines += ["", "The folder contains the screen recordings, logs and measurements. It contains no password; "
                      "the e-mail address appears only as its domain.",
                  "Everything the test changed on this computer has been undone (see logs/cleanup.txt)."]
        text = "\n".join(lines) + "\n"
        (folder / "README-FIRST.txt").write_text(text, encoding="utf-8")
        return text


class WindowsConfig:
    """The session's config, made from windows/config.windows.yaml and the values the script was started with
    (server, e-mail address, tool paths); the password stays in the environment."""

    @staticmethod
    def build(template: Path, values: dict, display: dict | None = None) -> dict:
        text = Path(template).read_text(encoding="utf-8")
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", str(value).replace("\\", "/"))
        data = yaml.safe_load(text)
        if display:
            data.setdefault("display", {}).update(app_region=display["app_region"],
                                                  pointer_park=display["pointer_park"])
        cpus = os.cpu_count() or 1
        if cpus >= 6 and not (data.get("capture") or {}).get("cpus"):
            data.setdefault("capture", {})["cpus"] = f"{cpus - 2}-{cpus - 1}"
        return data
