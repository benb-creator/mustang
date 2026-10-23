import json
import os
import platform
import re
import socket
import ssl
import statistics
import struct
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class EnvironmentProbe:
    def __init__(self, config, desktop=None):
        self.config = config
        self.desktop = desktop

    def collect(self, app_ids: list[str]) -> dict:
        env = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "os": self.os_name(),
               "kernel": platform.release(), "cpu": self.cpu(), "cpu_cores": os.cpu_count(), "ram": self.ram(),
               "ram_limit": self.ram_limit(), "gpu": self.gpu(), "python": platform.python_version(),
               "ffmpeg": self.ffmpeg_version()}
        if self.desktop is not None:
            env["display"] = self.desktop.describe_display()
        env["window"] = self.config.get("display.app_region")
        env["apps"] = {app_id: self.app_version(app_id) for app_id in app_ids}
        env["server"] = {"software": self.config.get("server.software") or self.config.get("server.name"),
                         "version": self.server_version(), "host": self.config.get("server.host")}
        env["rtt_ms"] = self.round_trip_ms()
        env.update(self.config.get("environment_overrides") or {})
        return env

    def os_name(self) -> str:
        if platform.system() == "Linux":
            try:
                text = Path("/etc/os-release").read_text()
                m = re.search(r'^PRETTY_NAME="?([^"\n]+)"?', text, re.M)
                if m:
                    return m.group(1)
            except OSError:
                pass
        if platform.system() == "Windows":
            return f"Windows {platform.release()} ({platform.version()})"
        return f"{platform.system()} {platform.release()}"

    def cpu(self) -> str:
        if platform.system() == "Linux":
            try:
                for line in Path("/proc/cpuinfo").read_text().splitlines():
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
            except OSError:
                pass
        if platform.system() == "Windows":
            return self.powershell("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name") or platform.processor()
        return platform.processor()

    def ram(self) -> str:
        if platform.system() == "Linux":
            try:
                kb = int(re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text()).group(1))
                return f"{kb / 1024 / 1024:.0f} GB"
            except (OSError, AttributeError):
                return ""
        if platform.system() == "Windows":
            total = self.powershell("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")
            return f"{int(total) / 1024 ** 3:.0f} GB" if total.isdigit() else ""
        return ""

    def ram_limit(self) -> str | None:
        """The memory limit of the container the session runs in (cgroup v2 memory.max, v1 limit_in_bytes), when
        it is below the computer's RAM."""
        if platform.system() != "Linux":
            return None
        for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
            try:
                text = Path(path).read_text().strip()
                total_kb = int(re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text()).group(1))
            except (OSError, AttributeError):
                continue
            if text.isdigit() and int(text) < total_kb * 1024:
                return f"{int(text) / 1024 ** 3:.0f} GB"
        return None

    @staticmethod
    def published(env: dict) -> dict:
        """The environment as the cards and method texts show it (spec v5): on Linux the CPU with its logical CPU
        count, and the container's memory limit as the RAM when there is one (the host's RAM stays in `ram_host`)."""
        out = dict(env)
        linux = not str(env.get("os") or "").startswith("Windows")
        if linux and env.get("cpu") and env.get("cpu_cores") and "vCPU" not in str(env["cpu"]):
            out["cpu"] = f"{env['cpu']}, {env['cpu_cores']} vCPUs"
        if env.get("ram_limit"):
            out["ram"], out["ram_host"] = env["ram_limit"], env.get("ram")
        return out

    def gpu(self) -> str:
        if platform.system() == "Linux":
            try:
                out = subprocess.run(["lspci"], capture_output=True, text=True, timeout=10).stdout
                gpus = [line.split(": ", 1)[1] for line in out.splitlines() if re.search(r"VGA|3D|Display", line)]
                return "; ".join(gpus)
            except (OSError, subprocess.TimeoutExpired):
                return ""
        if platform.system() == "Windows":
            return self.powershell("(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join '; '")
        return ""

    def powershell(self, script: str) -> str:
        try:
            return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                                  timeout=30).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return ""

    def ffmpeg_version(self) -> str:
        try:
            out = subprocess.run([self.config.tool("ffmpeg"), "-version"], capture_output=True, text=True,
                                 timeout=10).stdout
            return out.split("\n")[0].replace("ffmpeg version ", "").split(" Copyright")[0]
        except (OSError, subprocess.TimeoutExpired):
            return ""

    @staticmethod
    def asar_package_version(asar: Path) -> str | None:
        with open(asar, "rb") as f:
            head = f.read(16)
            header_size = struct.unpack_from("<I", head, 4)[0]
            json_size = struct.unpack_from("<I", head, 12)[0]
            header = json.loads(f.read(json_size))
            entry = header["files"]["package.json"]
            f.seek(8 + header_size + int(entry["offset"]))
            return json.loads(f.read(int(entry["size"]))).get("version")

    def app_version(self, app_id: str) -> dict:
        spec = self.config.expand(self.config.app(app_id), app_id)
        version = spec.get("version")
        source = spec.get("version_from") or {}
        try:
            if isinstance(source, dict) and source.get("asar"):
                version = self.asar_package_version(Path(source["asar"]))
            elif isinstance(source, dict) and source.get("command"):
                out = subprocess.run(source["command"], capture_output=True, text=True, timeout=60).stdout
                m = re.search(source.get("regex", r"(\d+(?:\.\d+)+)"), out)
                version = m.group(1) if m else out.strip()
            elif isinstance(source, dict) and source.get("ini"):
                text = Path(source["ini"]).read_text(errors="replace")
                m = re.search(r"^Version=(.+)$", text, re.M)
                version = m.group(1).strip() if m else version
        except Exception as ex:
            version = version or f"unknown ({type(ex).__name__})"
        return {"name": spec.get("name", app_id), "version": version, "protocol": spec.get("protocol"),
                "os": spec.get("os")}

    def server_version(self) -> str | None:
        if self.config.get("server.version"):
            return str(self.config.get("server.version"))
        command = self.config.get("server.version_command")
        if command:
            from .snapshot import CommandRunner
            try:
                return CommandRunner(self.config.get("server.snapshot.ssh")).run(command, timeout=60).strip()
            except Exception:
                pass
        context = ssl.create_default_context()
        if self.config.get("server.ca_file"):
            context.load_verify_locations(cafile=str(self.config.path(self.config.get("server.ca_file"))))
        try:
            with urllib.request.urlopen(self.config.require("server.jmap_session_url"), timeout=10,
                                        context=context) as resp:
                header = resp.headers.get("Server")
        except urllib.error.HTTPError as ex:
            header = ex.headers.get("Server")
        except OSError:
            return None
        return header if header and re.search(r"\d", header) else None

    def round_trip_ms(self) -> dict:
        targets = {}
        host = self.config.get("server.imap.host")
        if host:
            targets["imap_connect"] = (host, int(self.config.get("server.imap.port", 993)))
        url = self.config.get("server.jmap_session_url")
        if url:
            from urllib.parse import urlparse
            u = urlparse(url)
            targets["https_connect"] = (u.hostname, u.port or (443 if u.scheme == "https" else 80))
        result = {}
        for name, (h, port) in targets.items():
            samples = []
            for _ in range(10):
                start = time.perf_counter()
                try:
                    with socket.create_connection((h, port), timeout=5):
                        samples.append((time.perf_counter() - start) * 1000)
                except OSError:
                    pass
                time.sleep(0.05)
            result[name] = round(statistics.median(samples), 2) if samples else None
        return result
