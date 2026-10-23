import json
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path


class NetworkLog:
    """`network.jsonl` of a run (README, "Result folder format"): one JSON object per line, `t` on the driver's clock
    (`time.perf_counter()`), `utc` = `time.time()`."""

    version = 1

    def __init__(self, path: Path):
        self.path = Path(path)
        self.file = open(self.path, "a", encoding="utf-8")
        self.lock = threading.Lock()

    def write(self, type: str, t: float | None = None, **fields):
        t = time.perf_counter() if t is None else t
        line = json.dumps({"type": type, "t": t, "utc": time.time(), **fields}, ensure_ascii=False)
        with self.lock:
            self.file.write(line + "\n")
            self.file.flush()

    def header(self, os_name: str, app_id: str, source: str, poll_hz: float, root_pids: list[int]):
        self.write("header", version=self.version, os=os_name, app=app_id, source=source, poll_hz=poll_hz,
                   root_pids=root_pids, script_pid=os.getpid(), utc_offset=time.time() - time.perf_counter())

    def close(self):
        with self.lock:
            self.file.close()

    @staticmethod
    def read(path: Path) -> list[dict]:
        if not Path(path).exists():
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


class ProcNet:
    """Parses the kernel's TCP tables (/proc/net/tcp, /proc/net/tcp6)."""

    @staticmethod
    def address(hex_address: str) -> tuple[str, int]:
        host, port = hex_address.split(":")
        raw = bytes.fromhex(host)
        if len(raw) == 4:
            ip = socket.inet_ntop(socket.AF_INET, raw[::-1])
        else:
            words = b"".join(raw[i:i + 4][::-1] for i in range(0, 16, 4))
            ip = socket.inet_ntop(socket.AF_INET6, words)
            if ip.startswith("::ffff:") and "." in ip:
                ip = ip[7:]
        return ip, int(port, 16)

    @classmethod
    def parse(cls, text: str) -> list[dict]:
        states = {"01": "ESTABLISHED", "02": "SYN_SENT", "03": "SYN_RECV", "04": "FIN_WAIT1", "05": "FIN_WAIT2",
                  "06": "TIME_WAIT", "07": "CLOSE", "08": "CLOSE_WAIT", "09": "LAST_ACK", "0A": "LISTEN", "0B": "CLOSING"}
        out = []
        for line in text.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 10:
                continue
            local_ip, local_port = cls.address(parts[1])
            remote_ip, remote_port = cls.address(parts[2])
            out.append({"local": f"{local_ip}:{local_port}", "remote": remote_ip, "remote_port": remote_port,
                        "state": states.get(parts[3].upper(), parts[3]), "inode": int(parts[9])})
        return out

    @classmethod
    def connections(cls) -> list[dict]:
        out = []
        for name in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                out += cls.parse(Path(name).read_text())
            except OSError:
                pass
        return out


class ProcessTree:
    @staticmethod
    def children() -> dict[int, list[int]]:
        tree: dict[int, list[int]] = {}
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                stat = Path(f"/proc/{entry}/stat").read_text()
            except OSError:
                continue
            ppid = int(stat[stat.rindex(")") + 2:].split()[1])
            tree.setdefault(ppid, []).append(int(entry))
        return tree

    @staticmethod
    def direct_children(pid: int) -> list[int] | None:
        """From /proc/<pid>/task/<tid>/children (cheap); None where the kernel doesn't provide it."""
        try:
            tasks = os.listdir(f"/proc/{pid}/task")
        except OSError:
            return []
        out = []
        for tid in tasks:
            try:
                out += [int(c) for c in Path(f"/proc/{pid}/task/{tid}/children").read_text().split()]
            except FileNotFoundError:
                return None
            except OSError:
                continue
        return out

    @classmethod
    def descendants(cls, roots: list[int]) -> set[int]:
        found, stack, tree = set(), list(roots), None
        while stack:
            pid = stack.pop()
            if pid in found or not Path(f"/proc/{pid}").exists():
                continue
            found.add(pid)
            children = cls.direct_children(pid)
            if children is None:
                tree = tree if tree is not None else cls.children()
                children = tree.get(pid, [])
            stack += children
        return found

    @staticmethod
    def name(pid: int) -> str:
        try:
            return Path(f"/proc/{pid}/comm").read_text().strip()
        except OSError:
            return "?"

    @staticmethod
    def socket_inodes(pid: int) -> set[int]:
        inodes = set()
        try:
            for fd in os.listdir(f"/proc/{pid}/fd"):
                try:
                    target = os.readlink(f"/proc/{pid}/fd/{fd}")
                except OSError:
                    continue
                if target.startswith("socket:["):
                    inodes.add(int(target[8:-1]))
        except OSError:
            pass
        return inodes


class LinuxConnectionWatcher:
    """Polls the TCP connections of an app's process tree (/proc, ≥ 5 Hz) into network.jsonl; byte counters per
    connection come from `ss -tni` once a second (a lower bound: a connection that closes between two readings
    keeps its last value)."""

    def __init__(self, log: NetworkLog, app_id: str, roots, extra_pids=None, poll_hz: float = 10,
                 bytes_every_s: float = 1.0, ss: str = "ss"):
        self.log = log
        self.app_id = app_id
        self.roots = roots
        self.extra_pids = extra_pids or (lambda: [])
        self.poll_s = 1.0 / poll_hz
        self.poll_hz = poll_hz
        self.bytes_every_s = bytes_every_s
        self.ss = ss
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.known: dict[tuple, dict] = {}
        self.bytes_seen: dict[tuple, tuple] = {}
        self.intervals: list[float] = []
        self.processes_seen: dict[str, int] = {}
        self.extra_cache: tuple[float, set[int]] = (0.0, set())

    def start(self):
        self.log.header("linux", self.app_id, "proc", self.poll_hz, list(self.roots()))
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(10)
        self.poll()
        for key, entry in list(self.known.items()):
            self.log.write("close", pid=entry["pid"], local=key[0], remote=key[1], remote_port=key[2], at_end=True)
        mean = sum(self.intervals) / len(self.intervals) if self.intervals else None
        self.log.write("stats", polls=len(self.intervals) + 1, mean_interval_s=mean,
                       max_interval_s=max(self.intervals) if self.intervals else None,
                       processes_seen=self.processes_seen)

    def loop(self):
        last_poll = None
        last_bytes = 0.0
        while not self.stop_event.is_set():
            now = time.perf_counter()
            if last_poll is not None:
                self.intervals.append(now - last_poll)
            last_poll = now
            try:
                self.poll()
                if now - last_bytes >= self.bytes_every_s:
                    last_bytes = now
                    self.read_bytes()
            except Exception as ex:
                self.log.write("error", error=f"{type(ex).__name__}: {ex}")
            self.stop_event.wait(max(0.0, self.poll_s - (time.perf_counter() - now)))

    def pids(self) -> set[int]:
        """The launched process tree; processes matched by name (e.g. reparented helpers) every 2 s, since
        finding them reads every process's command line."""
        now = time.perf_counter()
        if now - self.extra_cache[0] >= 2.0:
            self.extra_cache = (now, set(self.extra_pids()))
        return ProcessTree.descendants([p for p in self.roots() if p]) | self.extra_cache[1]

    def poll(self):
        owners = {}
        for pid in self.pids():
            for inode in ProcessTree.socket_inodes(pid):
                owners[inode] = pid
        current = {}
        for conn in ProcNet.connections():
            pid = owners.get(conn["inode"])
            if pid is None or conn["state"] == "LISTEN":
                continue
            current[(conn["local"], conn["remote"], conn["remote_port"])] = {"pid": pid, "state": conn["state"]}
        for key, entry in current.items():
            known = self.known.get(key)
            if known is None:
                process = ProcessTree.name(entry["pid"])
                self.processes_seen[process] = self.processes_seen.get(process, 0) + 1
                self.log.write("open", pid=entry["pid"], process=process, local=key[0], remote=key[1],
                               remote_port=key[2], state=entry["state"])
            elif known["state"] != entry["state"]:
                self.log.write("state", pid=entry["pid"], local=key[0], remote=key[1], remote_port=key[2],
                               state=entry["state"])
        for key, entry in self.known.items():
            if key not in current:
                self.log.write("close", pid=entry["pid"], local=key[0], remote=key[1], remote_port=key[2])
        self.known = current

    def read_bytes(self):
        if not self.known:
            return
        try:
            text = subprocess.run([self.ss, "-tniH"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.TimeoutExpired):
            return
        for local, remote, received, sent in SsOutput.parse(text):
            remote_ip, _, remote_port = remote.rpartition(":")
            key = (local, remote_ip.strip("[]"), int(remote_port))
            if key in self.known and self.bytes_seen.get(key) != (received, sent):
                self.bytes_seen[key] = (received, sent)
                self.log.write("bytes", local=key[0], remote=key[1], remote_port=key[2], received=received, sent=sent)


class SsOutput:
    @staticmethod
    def parse(text: str) -> list[tuple[str, str, int, int]]:
        """(local, remote, bytes_received, bytes_sent) per connection of `ss -tniH` (two lines per socket)."""
        out = []
        current = None
        for line in text.splitlines():
            if not line.startswith(("\t", " ")):
                parts = line.split()
                current = (SsOutput.address(parts[3]), SsOutput.address(parts[4])) if len(parts) >= 5 else None
                continue
            if current is None:
                continue
            received = re.search(r"bytes_received:(\d+)", line)
            sent = re.search(r"bytes_sent:(\d+)", line)
            out.append((current[0], current[1], int(received.group(1)) if received else 0,
                        int(sent.group(1)) if sent else 0))
            current = None
        return out

    @staticmethod
    def address(text: str) -> str:
        host, _, port = text.rpartition(":")
        host = host.strip("[]")
        if host.startswith("::ffff:") and "." in host:
            host = host[7:]
        return f"{host}:{port}"
