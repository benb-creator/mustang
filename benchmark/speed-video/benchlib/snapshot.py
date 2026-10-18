import json
import platform
import shlex
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


class SnapshotError(Exception):
    pass


class CommandRunner:
    def __init__(self, ssh: str | None = None, ssh_options: list[str] | None = None):
        self.ssh = ssh
        self.ssh_options = ssh_options or ["-o", "BatchMode=yes"]

    def run(self, script: str, timeout: float = 1800) -> str:
        cmd = ["ssh", *self.ssh_options, self.ssh, script] if self.ssh else ["sh", "-c", script]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise SnapshotError(f"Server command failed (exit {result.returncode}): {result.stderr.strip()}\n"
                                f"Script: {script}")
        return result.stdout


class StorageSnapshot:
    """Snapshot of the whole dedicated benchmark Stalwart instance: stop, copy the data dir, start."""

    marker_file = "BENCHMARK-INSTANCE"

    def __init__(self, spec: dict, runner: CommandRunner, wait_ready):
        self.instance_dir = spec["instance_dir"]
        self.data_dir = spec.get("data_dir") or f"{self.instance_dir}/data"
        self.snapshot_dir = spec.get("snapshot_dir") or f"{self.instance_dir}/snapshots"
        self.stop_command = spec["stop"]
        self.start_command = spec["start"]
        self.runner = runner
        self.wait_ready = wait_ready

    def guard(self) -> str:
        marker = shlex.quote(f"{self.instance_dir}/{self.marker_file}")
        return (f"test -f {marker} || {{ echo 'Refusing: {self.instance_dir} has no {self.marker_file} file, "
                f"so it is not the dedicated benchmark instance' >&2; exit 3; }}")

    def snapshot_path(self, name: str) -> str:
        if not name.replace("-", "").replace("_", "").isalnum():
            raise SnapshotError(f"Bad snapshot name '{name}'")
        return f"{self.snapshot_dir}/{name}"

    def wrapped(self, body: str) -> str:
        return (f"set -u; {self.guard()}; {self.stop_command}; ( set -e; {body} ); status=$?; "
                f"{self.start_command}; exit $status")

    def take(self, name: str):
        target = shlex.quote(self.snapshot_path(name))
        tmp = shlex.quote(self.snapshot_path(name) + ".tmp")
        data = shlex.quote(self.data_dir)
        self.runner.run(self.wrapped(
            f"mkdir -p {shlex.quote(self.snapshot_dir)}; rm -rf {tmp}; cp -a --reflink=auto {data} {tmp}; "
            f"rm -rf {target}; mv {tmp} {target}"))
        self.wait_ready()

    def restore(self, name: str):
        source = shlex.quote(self.snapshot_path(name))
        data = shlex.quote(self.data_dir)
        self.runner.run(self.wrapped(
            f"test -d {source}; rm -rf {data}; cp -a --reflink=auto {source} {data}"))
        self.wait_ready()

    def list(self) -> list[str]:
        out = self.runner.run(f"ls -1 {shlex.quote(self.snapshot_dir)} 2>/dev/null || true")
        return [line for line in out.split() if not line.endswith(".tmp")]


class ProtocolSnapshot:
    """Fallback without shell access: wipe the benchmark account and import the corpus again.
    Message ids, IMAP UIDs and UIDVALIDITY change, so client caches must be rebuilt after a restore."""

    def __init__(self, seeder):
        self.seeder = seeder

    def take(self, name: str):
        pass

    def restore(self, name: str):
        self.seeder.wipe()
        self.seeder.seed()

    def list(self) -> list[str]:
        return ["(protocol level: every name restores the seeded corpus)"]


class ClientProfiles:
    """Copies of each app's profile/data directories (and Windows registry keys), guarded by a marker file."""

    marker_file = ".bench-profile"

    def __init__(self, config):
        self.config = config

    def spec(self, app_id: str) -> dict:
        return self.config.expand(self.config.app(app_id).get("profile") or {}, app_id)

    def directories(self, app_id: str) -> list[Path]:
        return [Path(d) for d in self.spec(app_id).get("dirs") or []]

    def snapshot_root(self, name: str, app_id: str) -> Path:
        return self.config.workdir / "snapshots" / name / "client" / app_id

    def check_owned(self, directory: Path):
        if directory.exists() and any(directory.iterdir()) and not (directory / self.marker_file).exists():
            raise SnapshotError(f"Refusing to replace {directory}: it has no {self.marker_file} file, "
                                f"so it may be a real profile")

    def reset(self, app_id: str):
        spec = self.spec(app_id)
        for directory in self.directories(app_id):
            self.check_owned(directory)
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True)
            (directory / self.marker_file).write_text(f"benchmark profile of {app_id}\n")
        for target, content in (spec.get("files") or {}).items():
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        for key in spec.get("registry") or []:
            self.registry_delete(key)

    def take(self, app_id: str, name: str):
        root = self.snapshot_root(name, app_id)
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        for i, directory in enumerate(self.directories(app_id)):
            if not (directory / self.marker_file).exists():
                raise SnapshotError(f"{directory} isn't a benchmark profile (no {self.marker_file})")
            shutil.copytree(directory, root / f"{i}", symlinks=True)
        for i, key in enumerate(self.spec(app_id).get("registry") or []):
            subprocess.run(["reg", "export", key, str(root / f"registry-{i}.reg"), "/y"], check=True)
        meta = {"app": app_id, "name": name, "taken": datetime.now(timezone.utc).isoformat(),
                "dirs": [str(d) for d in self.directories(app_id)], "host": platform.node()}
        (root / "meta.json").write_text(json.dumps(meta, indent=2))

    def restore(self, app_id: str, name: str):
        if name == "fresh":
            self.reset(app_id)
            return
        root = self.snapshot_root(name, app_id)
        if not root.exists():
            raise SnapshotError(f"No client snapshot '{name}' for {app_id} in {root}")
        for i, directory in enumerate(self.directories(app_id)):
            self.check_owned(directory)
            if directory.exists():
                shutil.rmtree(directory)
            shutil.copytree(root / f"{i}", directory, symlinks=True)
        for i, key in enumerate(self.spec(app_id).get("registry") or []):
            self.registry_delete(key)
            subprocess.run(["reg", "import", str(root / f"registry-{i}.reg")], check=True)

    def registry_delete(self, key: str):
        subprocess.run(["reg", "delete", key, "/f"], capture_output=True)


class ServerReadiness:
    def __init__(self, session_url: str, imap_host: str | None, imap_port: int | None, timeout_s: float = 180):
        self.session_url = session_url
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.timeout_s = timeout_s

    def __call__(self):
        import socket
        import urllib.error
        import urllib.request

        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(self.session_url, timeout=5).close()
                http_ok = True
            except urllib.error.HTTPError:
                http_ok = True
            except OSError:
                http_ok = False
            imap_ok = True
            if http_ok and self.imap_host:
                try:
                    with socket.create_connection((self.imap_host, self.imap_port), timeout=5):
                        pass
                except OSError:
                    imap_ok = False
            if http_ok and imap_ok:
                return
            time.sleep(0.5)
        raise SnapshotError(f"Server didn't come back within {self.timeout_s:.0f} s ({self.session_url})")
