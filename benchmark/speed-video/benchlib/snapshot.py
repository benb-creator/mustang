import json
import platform
import posixpath
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
        cmd = ["ssh", *self.ssh_options, self.ssh, "sh", "-s"] if self.ssh else ["sh", "-s"]
        result = subprocess.run(cmd, input=script, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise SnapshotError(f"Server command failed (exit {result.returncode}): {result.stderr.strip()}\n"
                                f"Script: {script}")
        return result.stdout


class StorageSnapshot:
    """Snapshot of the whole dedicated benchmark Stalwart instance: stop, copy the data dir, start.

    Files are only touched when the instance dir has the BENCHMARK-INSTANCE marker, the data dir has the
    BENCHMARK-DATA marker, both data and snapshot dir lie inside the instance dir (checked here and, after resolving
    symlinks, on the server), the stop command succeeded and no process of the instance is left."""

    marker_file = "BENCHMARK-INSTANCE"
    data_marker_file = "BENCHMARK-DATA"

    def __init__(self, spec: dict, runner: CommandRunner, wait_ready):
        self.instance_dir = posixpath.normpath(spec["instance_dir"])
        self.data_dir = posixpath.normpath(spec.get("data_dir") or f"{self.instance_dir}/data")
        self.snapshot_dir = posixpath.normpath(spec.get("snapshot_dir") or f"{self.instance_dir}/snapshots")
        self.stop_command = spec["stop"]
        self.start_command = spec["start"]
        self.running_check = spec.get("running_check") or self.default_running_check()
        self.stop_wait_s = int(spec.get("stop_wait_s", 60))
        self.runner = runner
        self.wait_ready = wait_ready
        for name, path in (("data_dir", self.data_dir), ("snapshot_dir", self.snapshot_dir)):
            if not posixpath.isabs(path) or not path.startswith(self.instance_dir + "/"):
                raise SnapshotError(f"server.snapshot.{name} ({path}) must be a directory inside instance_dir "
                                    f"({self.instance_dir})")
        if self.data_dir == self.snapshot_dir or self.snapshot_dir.startswith(self.data_dir + "/"):
            raise SnapshotError("server.snapshot.snapshot_dir must not be the data dir or inside it")

    def default_running_check(self) -> str:
        """A `stalwart` process whose command line names the instance dir (its binary or its config file)."""
        special = set(".[]()*+?{}|^$\\")
        instance = "".join("\\" + c if c in special else c for c in self.instance_dir)
        return f"pgrep -f -- {shlex.quote(f'^([^ ]*/)?stalwart( .*)?{instance}/')} >/dev/null"

    def guard(self) -> str:
        instance = shlex.quote(self.instance_dir)
        marker = shlex.quote(f"{self.instance_dir}/{self.marker_file}")
        refuse = "{ echo \"Refusing: $1\" >&2; exit 3; }"
        return (f"refuse() {refuse}; "
                f"test -f {marker} || refuse '{self.instance_dir} has no {self.marker_file} file, so it is not the "
                f"dedicated benchmark instance'; "
                f"real_instance=$(realpath -e {instance}) || refuse 'instance dir missing'; "
                f"for d in {shlex.quote(self.data_dir)} {shlex.quote(self.snapshot_dir)}; do "
                f"r=$(realpath -m \"$d\"); case \"$r/\" in \"$real_instance\"/?*) ;; "
                f"*) refuse \"$d resolves to $r, outside $real_instance\";; esac; done")

    def data_guard(self, directory: str) -> str:
        marker = shlex.quote(f"{directory}/{self.data_marker_file}")
        return (f"test -f {marker} || refuse '{directory} has no {self.data_marker_file} file (create it once in the "
                f"benchmark data dir)'")

    def snapshot_path(self, name: str) -> str:
        if not name.replace("-", "").replace("_", "").isalnum():
            raise SnapshotError(f"Bad snapshot name '{name}'")
        return f"{self.snapshot_dir}/{name}"

    def stopped(self) -> str:
        return (f"{{ {self.stop_command}; }} || {{ echo 'Stop command failed; nothing was changed' >&2; exit 4; }}; "
                f"n=0; while {self.running_check}; do n=$((n+1)); "
                f"if [ $n -gt {self.stop_wait_s} ]; then echo 'Instance still running after the stop command; "
                f"nothing was changed' >&2; {self.start_command}; exit 5; fi; sleep 1; done")

    def wrapped(self, checks: str, body: str) -> str:
        return (f"set -u; {self.guard()}; {checks}; {self.stopped()}; ( set -e; {body} ); status=$?; "
                f"{self.start_command}; exit $status")

    def take(self, name: str):
        target = shlex.quote(self.snapshot_path(name))
        tmp = shlex.quote(self.snapshot_path(name) + ".tmp")
        data = shlex.quote(self.data_dir)
        self.runner.run(self.wrapped(
            self.data_guard(self.data_dir),
            f"mkdir -p {shlex.quote(self.snapshot_dir)}; rm -rf {tmp}; cp -a --reflink=auto {data} {tmp}; "
            f"rm -rf {target}; mv {tmp} {target}"))
        self.wait_ready()

    def restore(self, name: str):
        source = shlex.quote(self.snapshot_path(name))
        data = shlex.quote(self.data_dir)
        self.runner.run(self.wrapped(
            f"test -d {source} || refuse 'no snapshot {name}'; {self.data_guard(self.data_dir)}; "
            f"{self.data_guard(self.snapshot_path(name))}",
            f"rm -rf {data}; cp -a --reflink=auto {source} {data}"))
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
        for target, source in (spec.get("links") or {}).items():
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            if Path(source).exists() and not path.exists():
                path.symlink_to(source)
        for key in spec.get("registry") or []:
            self.registry_delete(key)
            if spec.get("registry_create_empty"):
                subprocess.run(["reg", "add", key, "/f"], capture_output=True, check=True)
        for target in spec.get("credential_targets") or []:
            subprocess.run(["cmdkey", f"/delete:{target}"], capture_output=True)

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


class PasswordRotation:
    """After every server restore, the test account gets a new random password of the same length, which the
    driver types (typing time unchanged). A password an app or a cloud service kept from an earlier run then
    no longer works, and its login attempts show up in the server log as failed. Uses Stalwart's management API
    as an administrator (`server.password_rotation`); never logs the password."""

    def __init__(self, config):
        spec = config.get("server.password_rotation") or {}
        self.enabled = bool(spec)
        if not self.enabled:
            return
        session = config.require("server.jmap_session_url")
        origin = "/".join(session.split("/", 3)[:3])
        self.api_url = spec.get("api_url") or f"{origin}/jmap/"
        self.admin_user = spec["admin_user"]
        self.admin_password = config.secret("server.password_rotation.admin_password_env")
        self.account_id = spec.get("account_id")
        self.username = str(config.get("account.username") or config.require("account.email"))
        self.length = len(config.secret("account.password_env"))

    def call(self, method_calls: list) -> list:
        import base64
        import urllib.request
        body = json.dumps({"using": ["urn:ietf:params:jmap:core", "urn:stalwart:jmap"], "methodCalls": method_calls})
        token = base64.b64encode(f"{self.admin_user}:{self.admin_password}".encode()).decode()
        request = urllib.request.Request(self.api_url, data=body.encode(), method="POST",
                                         headers={"Content-Type": "application/json", "Authorization": f"Basic {token}"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())["methodResponses"]

    def account(self) -> str:
        if self.account_id:
            return self.account_id
        local = self.username.split("@")[0]
        ids = self.call([["x:Account/query", {"filter": {"name": local}}, "q"]])[0][1].get("ids") or []
        if len(ids) != 1:
            raise SnapshotError(f"Found {len(ids)} accounts named '{local}'; set server.password_rotation.account_id")
        self.account_id = ids[0]
        return self.account_id

    def rotate(self) -> str:
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        password = "".join(secrets.choice(alphabet) for _ in range(self.length))
        account = self.account()
        result = self.call([["x:Account/set", {"update": {account: {"credentials/0/secret": password}}}, "s"]])[0][1]
        if account not in (result.get("updated") or {}):
            raise SnapshotError(f"Changing the test account's password failed: {result.get('notUpdated')}")
        return password
