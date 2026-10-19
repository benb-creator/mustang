import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .driver import AppProcess, Calibration, DriverError, EventLog, FocusError, ScenarioDriver
from .flows import FlowContext, NewOutlookRemoval
from .probe import Probes
from .runner import AppLifecycle, RunExecutor, SeriesStop
from .settle import Rect
from .winapps import (LocalCommands, OutlookClassicProfile, ParulaProfile, ParulaUpdates, ProcessGuard,
                      SessionState, WindowsSettings)


class WindowsBenchError(Exception):
    pass


class NoticeShown(Exception):
    """The app shows a first-run notice before its setup (the flow closes it in every run)."""


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
    """Checked before anything changes on the computer; every failed check says how to fix it. `account_check`
    is the shared account check (`AccountCheck.run`, called with `repair=False`)."""

    def __init__(self, config, desktop, account_check, progress=print, commands=None):
        self.config = config
        self.desktop = desktop
        self.account_check = account_check
        self.progress = progress
        self.commands = commands or subprocess.run

    def powershell(self, script: str) -> str:
        out = self.commands(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                            timeout=120)
        return (out.stdout or "").strip()

    def session_apps(self) -> list[str]:
        return list((self.config.get("sessions") or {})["windows"]["apps"])

    def apps(self) -> list[Check]:
        checks = []
        for app_id in self.session_apps():
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
            report = self.account_check(repair=False)
        except Exception as ex:
            return [Check("Mail account reachable", False, f"{type(ex).__name__}: {ex}",
                          "Check the server name, the e-mail address and the password")]
        folders = (report.get("before") or report).get("folders") or {}
        counts = ", ".join(f"{name} {v.get('actual')}/{v.get('expected')}" for name, v in folders.items())
        return [Check("Mail account reachable", True, f"logged in ({report.get('protocol', 'imap')})"),
                Check("Mail account seeded", bool(report.get("ok")), counts or "no folder counts",
                      "The account isn't seeded with the test messages (or differs from them). Seeding is done "
                      "once by the Parula team: please tell them, and run this script again afterwards.")]

    def power(self) -> Check:
        on_ac = self.desktop.on_ac_power()
        return Check("Power supply", on_ac is not False, {True: "plugged in", False: "on battery",
                                                          None: "unknown"}[on_ac],
                     "Plug in the power supply: on battery Windows slows the computer down")

    def running_apps(self) -> Check:
        names = [n for app_id in self.session_apps() for n in self.config.app(app_id).get("process_names") or []]
        running = ProcessGuard(self.desktop).running(names)
        return Check("The test apps are closed", not running, ", ".join(running) or "none running",
                     "Close " + ", ".join(running) + " (also in the notification area)" if running else None,
                     fatal=False)

    def run(self, root: Path) -> dict:
        checks = [Check("Windows", True, self.powershell("(Get-CimInstance Win32_OperatingSystem).Caption"),
                        fatal=False)]
        checks += self.apps()
        display, plan = self.display()
        checks += [display, self.disk(root), self.ffmpeg(), self.power(), self.running_apps()]
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


class WindowsAppProcess(AppProcess):
    """An app on Windows: its windows are kept in the recorded area while it runs (`WindowKeeper`: the main window
    at the region, setup dialogs moved to its center), and its windows come and go during its setup (Outlook's
    setup dialog before its main window, new Outlook's launcher that exits at once): its window is the keeper's
    main window, else the frontmost window of its process tree; keys go to it when the foreground window belongs
    to that tree."""

    def __init__(self, app_id: str, spec: dict, desktop, region: Rect, log, output: Path | None,
                 hide_address=lambda text: text):
        super().__init__(app_id, spec, desktop, region, log, output)
        self.keeper = None
        self.hide_address = hide_address

    def process_ids(self) -> set[int]:
        from .winnet import ProcessTable
        roots = {self.process.pid} if self.process is not None else set()
        names = {n.lower() for n in self.spec.get("process_names") or []}
        return set(ProcessTable.tree(ProcessTable().snapshot(), roots, names))

    def launch(self, place_window: bool = True):
        super().launch(place_window=False)
        self.keeper = self.desktop.window_keeper(self.process_ids, self.region, dict(self.spec.get("window") or {}),
                                                 self.spec.get("window_offsets") or {}).start()
        return None

    def app_windows(self) -> list:
        pids = self.process_ids()
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
        return bool(foreground) and self.desktop.window_process_id(foreground) in self.process_ids()

    def ensure_foreground(self):
        if self.foreground_is_app():
            return
        self.desktop.focus_window(self.ensure_window())
        time.sleep(0.2)
        if not self.foreground_is_app():
            raise FocusError(f"{self.app_id}: its window isn't in the foreground, so no keys were sent")

    def client_origin(self) -> tuple[int, int] | None:
        return self.desktop.client_origin(self.ensure_window())

    def close(self) -> bool:
        if self.keeper is not None:
            self.keeper.stop()
            if self.keeper.main is not None and self.desktop.is_window(self.keeper.main):
                self.window = self.keeper.main
        return super().close()

    def notes(self) -> dict:
        if self.keeper is None:
            return {}
        return {"windows_placed": [{**w, "title": self.hide_address(w.get("title") or "")} for w in self.keeper.placed]}


class WindowsLifecycle(AppLifecycle):
    """One app's part of the Windows session: its fresh state before every run, what happens after a run, what is
    set aside for the session and undone at its end."""

    def __init__(self, session: "WindowsSession", app_id: str):
        self.session = session
        self.app_id = app_id
        self.spec = session.config.expand(session.config.app(app_id), app_id)

    def app_process(self, app_id: str, spec: dict, desktop, region, log, output) -> AppProcess:
        return WindowsAppProcess(app_id, spec, desktop, region, log, output, self.session.hide_address)

    def before_session(self) -> list[str]:
        return []

    def cleanup(self) -> list[str]:
        return []


class ParulaLifecycle(WindowsLifecycle):
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

    def after_close(self) -> dict:
        self.profile.mark()
        self.profile.reset()
        return {"profile_deleted": True}

    def cleanup(self) -> list[str]:
        done = []
        if self.session.state.get("parula_aside"):
            try:
                self.profile.mark()
                self.profile.reset()
            except Exception as ex:
                done.append(f"Parula profile: {ex}")
        if self.profile.restore_user_profile():
            done.append("Parula: the user's profile is back")
        self.updates.restore()
        return done


class OutlookClassicLifecycle(WindowsLifecycle):
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


class NewOutlookLifecycle(WindowsLifecycle):
    """Every run is a new account setup: after the measured end the account stays until new Outlook's Inbox has
    listed every message for `keep_after_complete_min` (the Microsoft Cloud has then stopped importing), at most
    `keep_max_min`; then it is removed from all devices. The next run starts `min_gap_after_removal_min` later."""

    def reset(self):
        last = self.session.state.get("outlook_new_removed_utc")
        gap_s = float(self.spec.get("min_gap_after_removal_min", 10)) * 60
        if last:
            wait = gap_s - (time.time() - float(last))
            if wait > 0:
                self.session.pipeline.progress(f"    waiting {wait / 60:.0f} min since new Outlook's last account "
                                               f"removal")
                time.sleep(wait)
        self.session.state.set("outlook_new_account_pending", True)

    def remove(self, driver: ScenarioDriver, probe):
        NewOutlookRemoval(FlowContext(driver, probe, {}, {}), self.session.email).run()
        self.session.state.set("outlook_new_account_pending", False)
        self.session.state.set("outlook_new_removed_utc", time.time())

    def finish(self, driver: ScenarioDriver, probe) -> dict:
        keep_after = float(self.spec.get("keep_after_complete_min", 3)) * 60
        keep_max = float(self.spec.get("keep_max_min", 120)) * 60
        started = time.monotonic()
        complete_since = None
        listed = {}
        while time.monotonic() - started < keep_max:
            listed = probe.inbox_listed(driver.expected)
            if listed.get("complete"):
                complete_since = complete_since or time.monotonic()
                if time.monotonic() - complete_since >= keep_after:
                    break
            else:
                complete_since = None
            time.sleep(15)
        driver.log.write("cloud_wait", seconds=round(time.monotonic() - started), listed=listed)
        self.remove(driver, probe)
        return {"kept_s": round(time.monotonic() - started), "removed": True}

    def after_failure(self, driver: ScenarioDriver, probe) -> dict | None:
        """A failed run may have added the account: removed when new Outlook lists it, so the next run starts
        without it."""
        if probe.page() != "mail":
            return None
        self.remove(driver, probe)
        return {"removed": True}

    def cleanup(self) -> list[str]:
        if not self.session.state.get("outlook_new_account_pending"):
            return []
        try:
            self.session.remove_new_outlook_account(self)
            return ["New Outlook: the test account was removed (from all devices) if it was there"]
        except Exception as ex:
            return [f"New Outlook: REMOVE THE TEST ACCOUNT BY HAND (Settings → Accounts → Manage → Remove → "
                    f"Remove from all devices): {ex}"]


class Preflight:
    """Before the long series: every app starts from its fresh state, its instrumentation finds the first page of
    its account setup, and its state can be reset again. The UI trees and screenshots go to preflight/ either
    way."""

    def __init__(self, session: "WindowsSession"):
        self.session = session

    def app(self, app_id: str, out: Path) -> dict:
        session = self.session
        config = session.config
        lifecycle = session.lifecycles[app_id]
        spec = config.expand(config.app(app_id), app_id)
        result = {"app": app_id, "ok": False}
        probe = Probes.create(spec.get("probe"), config)
        executor = session.executor()
        app = lifecycle.app_process(app_id, spec, session.pipeline.desktop, executor.layout.app_region, None,
                                    out / f"{app_id}-output.log")
        try:
            lifecycle.reset()
            app.launch()
            probe.attach(app, float((spec.get("probe") or {}).get("timeout_s", 180)))
            pages = set(spec.get("start_pages") or [])

            def notice(element: str):
                raise NoticeShown(element)

            try:
                page = probe.wait_page(pages, 120, on_interruption=notice)
            except NoticeShown as shown:
                page = f"notice closed by {shown}"
            result.update(page=page, language=getattr(probe, "language", None), ok=True)
        except Exception as ex:
            result["error"] = session.hide_address(f"{type(ex).__name__}: {ex}")
        finally:
            try:
                session.pipeline.desktop.screenshot(out / f"{app_id}.png")
                probe.dump(out / f"{app_id}-ui-dump.json")
            except Exception as ex:
                result["diagnostics_error"] = str(ex)
            probe.close()
            result["closed_cleanly"] = app.close()
            try:
                lifecycle.after_close()
            except Exception as ex:
                result["reset_error"] = str(ex)
                result["ok"] = False
        return result

    def capture(self, out: Path) -> dict:
        recording = self.session.executor().capture(out / "capture-test.mkv", out / "capture-test-ffmpeg.log")
        try:
            live = recording.start()
            time.sleep(2)
            frames = len(live.arrivals)
        finally:
            recording.stop()
        (out / "capture-test.mkv").unlink(missing_ok=True)
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
            self.session.pipeline.progress(f"preflight: {app_id}")
            results["apps"][app_id] = self.app(app_id, out)
        results["ok"] = results["capture"]["ok"] and all(a["ok"] for a in results["apps"].values())
        (out / "preflight.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
        return results


class WindowsSession:
    """The whole Windows test in one run: settings, preflight, then the shared core's session (`Pipeline`: the
    interleaved series of all apps, warm-up + 5 measured runs each, failed runs re-recorded at the end, analysis,
    results, evidence); everything it changed on the computer is undone in `cleanup()`, also after an error or
    Ctrl+C."""

    lifecycle_kinds = {"parula": ParulaLifecycle, "outlook-classic": OutlookClassicLifecycle,
                       "outlook-new": NewOutlookLifecycle}

    def __init__(self, config, root: Path, progress=print, commands: LocalCommands | None = None, desktop=None):
        from .stages import Pipeline
        self.config = config
        self.commands = commands or LocalCommands()
        self.root = Path(root)
        self.state = SessionState(self.root / "state" / "session-state.json")
        self.email = str(config.require("account.email"))
        self.app_ids = list((config.get("sessions") or {})["windows"]["apps"])
        self.lifecycles = {app_id: self.lifecycle_kinds[config.app(app_id)["kind"]](self, app_id)
                           for app_id in self.app_ids}
        self.pipeline = Pipeline(config, progress, lifecycles=self.lifecycles, desktop=desktop)
        self.folder = None

    def executor(self) -> RunExecutor:
        """The shared core's run executor for the session's layout, capture and typed values (no result folder)."""
        return RunExecutor(self.config, self.pipeline.desktop, self.pipeline.scenarios, account=self.pipeline.account(),
                           lifecycles=self.lifecycles)

    def hide_address(self, text: str) -> str:
        """The test account's address appears only as its domain in the result folder."""
        local, _, domain = self.email.partition("@")
        return text.replace(self.email, f"<account>@{domain}") if local else text

    def remove_new_outlook_account(self, lifecycle: NewOutlookLifecycle):
        """Cleanup after an interrupted run: start new Outlook and remove the test account if it's still there."""
        executor = self.executor()
        region = executor.layout.app_region
        log = EventLog(self.root / "state" / "cleanup-driver.jsonl")
        spec = lifecycle.spec
        probe = Probes.create(spec.get("probe"), self.config)
        app = lifecycle.app_process(lifecycle.app_id, spec, self.pipeline.desktop, region, log, None)
        try:
            app.launch()
            probe.attach(app, 180)
            driver = ScenarioDriver(self.pipeline.desktop, app, Calibration(self.root / "state" / "none.yaml", region),
                                    executor.variables(), log, probe=probe)
            page = probe.wait_page({"add-account", "mail"}, 120)
            if page == "mail":
                lifecycle.remove(driver, probe)
            self.state.set("outlook_new_account_pending", False)
        finally:
            probe.close()
            app.close()
            log.close()

    def run(self) -> str | None:
        """The session; returns why the series stopped early, or None."""
        pipeline = self.pipeline
        self.folder = pipeline.results_folder()
        notes = WindowsSettings(self.state, self.commands).apply()
        for lifecycle in self.lifecycles.values():
            notes += lifecycle.before_session()
        still_open = OpenApps(pipeline.desktop).wait_closed(pipeline.progress)
        if still_open:
            notes.append(f"Windows: other apps were open during the session: {', '.join(still_open)}")
        self.console_aside()
        pipeline.notes += notes
        pipeline.write_manifest()
        preflight = Preflight(self).run()
        if not preflight["ok"]:
            raise WindowsBenchError(f"Preflight failed, so the long series didn't start: see "
                                    f"{self.folder.path / 'preflight' / 'preflight.json'}")
        try:
            pipeline.run_session("windows", resume=False, package=False)
        except SeriesStop as ex:
            return str(ex)
        return None

    def console_aside(self):
        """The console that runs the test is minimized when it overlaps the recorded area (restored at the end)."""
        desktop = self.pipeline.desktop
        console = desktop.console_window()
        if not console:
            return
        geometry = desktop.window_geometry(console)
        region = self.executor().layout.capture_region
        overlaps = geometry.x < region.x + region.width and region.x < geometry.x + geometry.width and \
            geometry.y < region.y + region.height and region.y < geometry.y + geometry.height
        if overlaps:
            desktop.show_window(console, minimized=True)
            self.state.set("console_minimized", int(console))

    def cleanup(self) -> list[str]:
        done = []
        desktop = self.pipeline.desktop
        for app_id in self.app_ids:
            try:
                desktop.kill_by_name(self.config.app(app_id).get("process_names") or [])
            except Exception:
                pass
        for lifecycle in self.lifecycles.values():
            try:
                done += lifecycle.cleanup()
            except Exception as ex:
                done.append(f"{lifecycle.app_id}: cleanup failed: {ex}")
        done += WindowsSettings(self.state, self.commands).revert()
        console = self.state.get("console_minimized")
        if console:
            try:
                desktop.show_window(console, minimized=False)
            except Exception:
                pass
            self.state.pop("console_minimized")
        return done


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
