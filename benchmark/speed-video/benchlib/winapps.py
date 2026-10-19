import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path


class AppStateError(Exception):
    pass


class SessionState:
    """What the session changed on this computer and must undo, in a JSON file next to the results, so a later
    start (after a crash or a power cut) can still undo it: `bench cleanup` reads it."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()

    def pop(self, key: str, default=None):
        value = self.data.pop(key, default)
        self.save()
        return value


class LocalCommands:
    def run(self, command: list[str], check: bool = False, timeout: float = 120) -> subprocess.CompletedProcess:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=check,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class ParulaProfile:
    """Parula keeps its data in %APPDATA%\\Parula (settings, mail database, Electron data) and its files in
    %USERPROFILE%\\Parula; Electron's appData path ignores environment variables, so a separate profile isn't
    possible. A profile of the computer's user is moved aside for the session and moved back at its end."""

    marker = ".bench-profile"

    def __init__(self, state: SessionState, aside_root: Path, appdata: Path | None = None, home: Path | None = None):
        self.state = state
        self.aside_root = Path(aside_root)
        appdata = appdata or os.environ.get("APPDATA")
        home = home or os.environ.get("USERPROFILE")
        if not appdata or not home:
            raise AppStateError("APPDATA and USERPROFILE must be set to find Parula's profile")
        self.dirs = [Path(appdata) / "Parula", Path(home) / "Parula"]

    def owned(self, directory: Path) -> bool:
        return (directory / self.marker).exists()

    def move_user_profile_aside(self) -> list[dict]:
        moved = list(self.state.get("parula_moved", []))
        for i, directory in enumerate(self.dirs):
            if directory.exists() and not self.owned(directory) and \
                    not any(m["original"] == str(directory) for m in moved):
                target = self.aside_root / f"parula-{i}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(directory), str(target))
                moved.append({"original": str(directory), "aside": str(target)})
                self.state.set("parula_moved", moved)
        return moved

    def reset(self):
        for directory in self.dirs:
            if directory.exists():
                if not self.owned(directory):
                    raise AppStateError(f"{directory} isn't the benchmark's Parula profile (no {self.marker}); "
                                        f"refusing to delete it")
                shutil.rmtree(directory)

    def mark(self):
        for directory in self.dirs:
            if directory.exists():
                (directory / self.marker).write_text("Parula benchmark profile, deleted after each run\n")

    def restore_user_profile(self) -> list[str]:
        restored = []
        moved = list(self.state.get("parula_moved", []))
        for entry in list(moved):
            original, aside = Path(entry["original"]), Path(entry["aside"])
            if original.exists():
                if not self.owned(original):
                    continue
                shutil.rmtree(original)
            if aside.exists():
                shutil.move(str(aside), str(original))
                restored.append(str(original))
            moved.remove(entry)
            self.state.set("parula_moved", moved)
        return restored


class ParulaUpdates:
    """The Windows installer's build updates itself (electron-updater: download at start, install on quit); the
    Linux .deb has no update configuration. For the session, resources/app-update.yml is renamed, so the installed
    version stays the same in every run; it is renamed back at the end."""

    def __init__(self, state: SessionState, install_dir: Path):
        self.state = state
        self.config = Path(install_dir) / "resources" / "app-update.yml"
        self.disabled = self.config.with_name("app-update.yml.bench-disabled")

    def disable(self) -> bool:
        if self.config.exists():
            try:
                os.replace(self.config, self.disabled)
            except OSError as ex:
                self.state.set("parula_updates", f"could not disable: {ex}")
                return False
            self.state.set("parula_updates", "disabled")
            return True
        return False

    def restore(self):
        if self.disabled.exists() and not self.config.exists():
            os.replace(self.disabled, self.config)
        if self.state.get("parula_updates"):
            self.state.pop("parula_updates")


class CredentialManager:
    """Windows Credential Manager entries (cmdkey). Only entries that name the test account and weren't there when
    the session started are deleted."""

    def __init__(self, runner: LocalCommands | None = None):
        self.runner = runner or LocalCommands()

    @staticmethod
    def parse_targets(output: str) -> list[str]:
        targets = []
        for line in output.splitlines():
            matched = re.match(r"\s*(Target|Ziel)\s*:\s*(.+)$", line)
            if matched:
                target = matched.group(2).strip()
                target = re.sub(r"^(LegacyGeneric|Domain|Generic|WindowsLive|Domäne|Generisch)[^=]*=", "", target)
                targets.append(target.strip())
        return targets

    def targets(self) -> list[str]:
        return self.parse_targets(self.runner.run(["cmdkey", "/list"]).stdout)

    def delete_new(self, email: str, before: list[str]) -> list[str]:
        deleted = []
        for target in self.targets():
            if email.lower() in target.lower() and target not in before:
                self.runner.run(["cmdkey", f"/delete:{target}"])
                deleted.append(target)
        return deleted


class OutlookClassicProfile:
    """A separate Outlook profile for the test account (`outlook.exe /profile <name>`): an empty profile makes
    Outlook open its own account setup. After a run the profile, the test account's data files and its new
    Credential Manager entries are deleted; the computer user's own profiles and files are never touched."""

    def __init__(self, state: SessionState, email: str, profile_name: str = "ParulaBench",
                 data_dir: Path | None = None, runner: LocalCommands | None = None,
                 credentials: CredentialManager | None = None, office_version: str = "16.0"):
        self.state = state
        self.email = email
        self.profile_name = profile_name
        if data_dir is None and not os.environ.get("LOCALAPPDATA"):
            raise AppStateError("LOCALAPPDATA must be set to find Outlook's data files")
        self.data_dir = Path(data_dir or Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Outlook")
        self.runner = runner or LocalCommands()
        self.credentials = credentials or CredentialManager(self.runner)
        self.key = f"HKCU\\Software\\Microsoft\\Office\\{office_version}\\Outlook\\Profiles\\{profile_name}"

    def remember_existing(self):
        if self.state.get("outlook_before") is None:
            files = sorted(p.name for p in self.data_dir.iterdir()) if self.data_dir.exists() else []
            self.state.set("outlook_before", {"files": files, "credentials": self.credentials.targets()})

    def profile_exists(self) -> bool:
        return self.runner.run(["reg", "query", self.key]).returncode == 0

    def create_empty(self):
        self.delete()
        self.runner.run(["reg", "add", self.key, "/f"], check=True)
        self.state.set("outlook_profile", self.profile_name)

    def account_files(self) -> list[Path]:
        before = set((self.state.get("outlook_before") or {}).get("files", []))
        if not self.data_dir.exists():
            return []
        prefix = self.email.lower()
        return [p for p in self.data_dir.iterdir() if p.name.lower().startswith(prefix) and p.name not in before]

    def delete(self) -> dict:
        removed = {"profile": False, "files": [], "credentials": []}
        if self.profile_exists():
            self.runner.run(["reg", "delete", self.key, "/f"])
            removed["profile"] = True
        for path in self.account_files():
            for attempt in range(10):
                try:
                    path.unlink() if path.is_file() else shutil.rmtree(path)
                    removed["files"].append(path.name)
                    break
                except OSError:
                    time.sleep(1)
        before = (self.state.get("outlook_before") or {}).get("credentials", [])
        removed["credentials"] = self.credentials.delete_new(self.email, before)
        if self.state.get("outlook_profile"):
            self.state.pop("outlook_profile")
        return removed


class WindowsSettings:
    """Session settings that make the runs comparable, each saved before it is changed and reverted at the end:
    the power plan (High performance when the computer has it), toast notifications off, and no sleep or display
    timeout while the session runs (SetThreadExecutionState, which ends with the process)."""

    high_performance = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
    toast_key = r"HKCU\Software\Microsoft\Windows\CurrentVersion\PushNotifications"

    def __init__(self, state: SessionState, runner: LocalCommands | None = None):
        self.state = state
        self.runner = runner or LocalCommands()

    @staticmethod
    def parse_scheme(output: str) -> str | None:
        matched = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", output, re.I)
        return matched.group(1).lower() if matched else None

    @staticmethod
    def parse_reg_dword(output: str, name: str) -> int | None:
        matched = re.search(rf"{re.escape(name)}\s+REG_DWORD\s+0x([0-9a-f]+)", output, re.I)
        return int(matched.group(1), 16) if matched else None

    def apply(self) -> list[str]:
        changes = []
        saved = dict(self.state.get("settings_saved") or {})
        if "power_scheme" not in saved:
            active = self.parse_scheme(self.runner.run(["powercfg", "/getactivescheme"]).stdout)
            schemes = self.runner.run(["powercfg", "/list"]).stdout.lower()
            if active and self.high_performance in schemes and active != self.high_performance:
                saved["power_scheme"] = active
                self.state.set("settings_saved", saved)
                self.runner.run(["powercfg", "/setactive", self.high_performance])
                changes.append("Power plan: High performance for the session (was " + active + ")")
            else:
                changes.append(f"Power plan: unchanged ({active or 'unknown'})")
        if "toasts" not in saved:
            query = self.runner.run(["reg", "query", self.toast_key, "/v", "ToastEnabled"])
            previous = self.parse_reg_dword(query.stdout, "ToastEnabled") if query.returncode == 0 else None
            saved["toasts"] = previous if previous is not None else "absent"
            self.state.set("settings_saved", saved)
            self.runner.run(["reg", "add", self.toast_key, "/v", "ToastEnabled", "/t", "REG_DWORD", "/d", "0", "/f"])
            changes.append("Windows notifications (toasts) off for the session")
        self.keep_awake()
        changes.append("Sleep and display timeout suspended while the session runs")
        return changes

    def keep_awake(self):
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
        import ctypes
        if hasattr(ctypes, "WinDLL"):
            ctypes.WinDLL("kernel32").SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED |
                                                              ES_DISPLAY_REQUIRED)

    def revert(self) -> list[str]:
        reverted = []
        saved = dict(self.state.get("settings_saved") or {})
        if saved.get("power_scheme"):
            self.runner.run(["powercfg", "/setactive", saved["power_scheme"]])
            reverted.append(f"power plan {saved['power_scheme']}")
        if "toasts" in saved:
            if saved["toasts"] == "absent":
                self.runner.run(["reg", "delete", self.toast_key, "/v", "ToastEnabled", "/f"])
            else:
                self.runner.run(["reg", "add", self.toast_key, "/v", "ToastEnabled", "/t", "REG_DWORD", "/d",
                                 str(saved["toasts"]), "/f"])
            reverted.append("notifications")
        if saved:
            self.state.pop("settings_saved")
        return reverted


class ProcessGuard:
    """The apps under test must not be running when the session starts (Outlook and new Outlook are single
    instance: a second start would only bring up the user's own window)."""

    def __init__(self, desktop):
        self.desktop = desktop

    def running(self, names: list[str]) -> list[str]:
        running = self.desktop.running_image_names()
        return [n for n in names if n.lower() in running]

    def wait_closed(self, names: list[str], progress, timeout_s: float = 3600, poll_s: float = 10) -> bool:
        deadline = time.monotonic() + timeout_s
        announced = None
        while True:
            open_now = self.running(names)
            if not open_now:
                return True
            if open_now != announced:
                progress(f"Please close {', '.join(open_now)}: the test starts these apps itself. Waiting…")
                announced = open_now
            if time.monotonic() > deadline:
                return False
            time.sleep(poll_s)
