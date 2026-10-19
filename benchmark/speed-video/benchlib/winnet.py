import ctypes
import ipaddress
import socket
import struct
import threading
import time
from dataclasses import dataclass


class WinNetError(Exception):
    pass


@dataclass(frozen=True)
class ProcessEntry:
    pid: int
    parent_pid: int
    exe: str


class ProcessTable:
    """The process list (Toolhelp32 snapshot) and the process tree of an app."""

    def snapshot(self) -> list[ProcessEntry]:
        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [("dwSize", ctypes.c_uint32), ("cntUsage", ctypes.c_uint32),
                        ("th32ProcessID", ctypes.c_uint32), ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", ctypes.c_uint32), ("cntThreads", ctypes.c_uint32),
                        ("th32ParentProcessID", ctypes.c_uint32), ("pcPriClassBase", ctypes.c_long),
                        ("dwFlags", ctypes.c_uint32), ("szExeFile", ctypes.c_wchar * 260)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
        kernel32.Process32FirstW.argtypes = (ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W))
        kernel32.Process32NextW.argtypes = (ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W))
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        handle = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not handle or handle == INVALID_HANDLE_VALUE:
            raise WinNetError(f"CreateToolhelp32Snapshot failed (error {ctypes.get_last_error()})")
        entries = []
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            more = kernel32.Process32FirstW(handle, ctypes.byref(entry))
            while more:
                entries.append(ProcessEntry(entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile.lower()))
                more = kernel32.Process32NextW(handle, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(handle)
        return entries

    @staticmethod
    def tree(entries: list[ProcessEntry], root_pids: set[int], names: set[str]) -> dict[int, str]:
        """The root processes, every process with one of the names, and all their descendants: pid -> exe."""
        names = {n.lower() for n in names}
        children: dict[int, list[ProcessEntry]] = {}
        for e in entries:
            if e.pid != e.parent_pid:
                children.setdefault(e.parent_pid, []).append(e)
        selected = {e.pid: e.exe for e in entries if e.pid in root_pids or e.exe in names}
        pending = list(selected)
        while pending:
            pid = pending.pop()
            for child in children.get(pid, []):
                if child.pid not in selected:
                    selected[child.pid] = child.exe
                    pending.append(child.pid)
        return selected


@dataclass(frozen=True)
class TcpRow:
    local: str
    local_port: int
    remote: str
    remote_port: int
    state: str
    pid: int

    @property
    def key(self) -> tuple[str, str, int]:
        return f"{self.local}:{self.local_port}" if ":" not in self.local else f"[{self.local}]:{self.local_port}", \
            self.remote, self.remote_port


class TcpTable:
    """All TCP connections with their owning process, from the IP Helper API (GetExtendedTcpTable), IPv4 and IPv6.
    Needs no administrator rights."""

    states = {1: "CLOSED", 2: "LISTEN", 3: "SYN_SENT", 4: "SYN_RCVD", 5: "ESTABLISHED", 6: "FIN_WAIT1",
              7: "FIN_WAIT2", 8: "CLOSE_WAIT", 9: "CLOSING", 10: "LAST_ACK", 11: "TIME_WAIT", 12: "DELETE_TCB"}

    def __init__(self):
        self.iphlpapi = ctypes.WinDLL("iphlpapi")
        self.iphlpapi.GetExtendedTcpTable.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
                                                      ctypes.c_int, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        self.iphlpapi.GetExtendedTcpTable.restype = ctypes.c_uint32
        self.buffers = {}

    def raw(self, family: int) -> bytes:
        TCP_TABLE_OWNER_PID_ALL, NO_ERROR, ERROR_INSUFFICIENT_BUFFER = 5, 0, 122
        size = ctypes.c_uint32(len(self.buffers.get(family, b"")) or 65536)
        for _ in range(8):
            buffer = self.buffers.get(family)
            if buffer is None or len(buffer) < size.value:
                buffer = ctypes.create_string_buffer(size.value + 4096)
                self.buffers[family] = buffer
                size = ctypes.c_uint32(len(buffer))
            result = self.iphlpapi.GetExtendedTcpTable(buffer, ctypes.byref(size), False, family,
                                                       TCP_TABLE_OWNER_PID_ALL, 0)
            if result == NO_ERROR:
                return buffer.raw[:size.value]
            if result != ERROR_INSUFFICIENT_BUFFER:
                raise WinNetError(f"GetExtendedTcpTable failed with {result}")
        raise WinNetError("GetExtendedTcpTable: the table kept growing")

    def rows(self) -> list[TcpRow]:
        return self.parse_ipv4(self.raw(socket.AF_INET)) + self.parse_ipv6(self.raw(socket.AF_INET6))

    @staticmethod
    def port(value: int) -> int:
        return socket.ntohs(value & 0xFFFF)

    @classmethod
    def parse_ipv4(cls, data: bytes) -> list[TcpRow]:
        """MIB_TCPTABLE_OWNER_PID: count, then rows of state, local addr, local port, remote addr, remote port, pid."""
        if len(data) < 4:
            return []
        (count,) = struct.unpack_from("<I", data, 0)
        rows = []
        for i in range(count):
            state, local, local_port, remote, remote_port, pid = struct.unpack_from("<I4sI4sII", data, 4 + i * 24)
            rows.append(TcpRow(socket.inet_ntop(socket.AF_INET, local), cls.port(local_port),
                               socket.inet_ntop(socket.AF_INET, remote), cls.port(remote_port),
                               cls.states.get(state, str(state)), pid))
        return rows

    @classmethod
    def parse_ipv6(cls, data: bytes) -> list[TcpRow]:
        """MIB_TCP6TABLE_OWNER_PID: count, then rows of local addr, scope, port, remote addr, scope, port, state, pid."""
        if len(data) < 4:
            return []
        (count,) = struct.unpack_from("<I", data, 0)
        rows = []
        for i in range(count):
            local, _, local_port, remote, _, remote_port, state, pid = struct.unpack_from(
                "<16sII16sIIII", data, 4 + i * 56)
            rows.append(TcpRow(cls.ipv6_text(local), cls.port(local_port), cls.ipv6_text(remote),
                               cls.port(remote_port), cls.states.get(state, str(state)), pid))
        return rows

    @staticmethod
    def ipv6_text(packed: bytes) -> str:
        address = ipaddress.IPv6Address(packed)
        return str(address.ipv4_mapped) if address.ipv4_mapped else str(address)


class ConnectionTracker:
    """Turns successive connection tables into open/state/close events of the app's process tree. Connections of
    processes outside the tree to the watched addresses (the mail server) are reported too, as `open_outside_tree`,
    so a connection that another process made for the app can't go unnoticed."""

    def __init__(self, watched_addresses: set[str] | None = None):
        self.watched = set(watched_addresses or ())
        self.known: dict[tuple, TcpRow] = {}
        self.seen_in_tree: set[tuple] = set()
        self.outside: set[tuple] = set()

    def update(self, rows: list[TcpRow], tree: dict[int, str]) -> list[dict]:
        events = []
        current = {}
        for row in rows:
            if row.state == "LISTEN" or row.remote_port == 0:
                continue
            if row.pid in tree:
                current[row.key] = row
            elif row.remote in self.watched and row.key not in self.outside and row.key not in self.seen_in_tree:
                self.outside.add(row.key)
                events.append({"type": "open_outside_tree", "pid": row.pid, "process": tree.get(row.pid),
                               "local": row.key[0], "remote": row.remote, "remote_port": row.remote_port,
                               "state": row.state})
        self.seen_in_tree.update(current)
        for key, row in current.items():
            known = self.known.get(key)
            if known is None:
                events.append({"type": "open", "pid": row.pid, "process": tree.get(row.pid), "local": key[0],
                               "remote": row.remote, "remote_port": row.remote_port, "state": row.state})
            elif known.state != row.state:
                events.append({"type": "state", "pid": row.pid, "local": key[0], "remote": row.remote,
                               "remote_port": row.remote_port, "state": row.state})
        for key, row in self.known.items():
            if key not in current:
                events.append({"type": "close", "pid": row.pid, "local": key[0], "remote": row.remote,
                               "remote_port": row.remote_port})
        self.known = current
        return events


class WindowsConnectionWatcher:
    """Polls the TCP table at `poll_hz` and writes the app's process tree's connections to a network log
    (`benchlib.netwatch.NetworkLog`: `header(**fields)`, `write(type, **fields)`)."""

    def __init__(self, log, app_id: str, root_pids, process_names: list[str], poll_hz: float = 10,
                 watched_addresses: set[str] | None = None, tcp_table=None, process_table=None, clock=time.perf_counter):
        self.log = log
        self.app_id = app_id
        self.root_pids = root_pids
        self.process_names = set(process_names)
        self.poll_hz = poll_hz
        self.tracker = ConnectionTracker(watched_addresses)
        self.tcp_table = tcp_table or TcpTable()
        self.process_table = process_table or ProcessTable()
        self.clock = clock
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.intervals: list[float] = []
        self.processes_seen: dict[str, set[int]] = {}
        self.error: str | None = None

    def current_roots(self) -> set[int]:
        return set(self.root_pids() if callable(self.root_pids) else self.root_pids)

    def poll(self) -> list[dict]:
        tree = ProcessTable.tree(self.process_table.snapshot(), self.current_roots(), self.process_names)
        for pid, exe in tree.items():
            self.processes_seen.setdefault(exe, set()).add(pid)
        events = self.tracker.update(self.tcp_table.rows(), tree)
        now = self.clock()
        utc = time.time()
        for event in events:
            kind = event.pop("type")
            self.log.write(kind, t=now, utc=utc, **event)
        return events

    def start(self):
        now = self.clock()
        self.log.header(version=1, os="windows", app=self.app_id, source="iphlpapi", poll_hz=self.poll_hz,
                        root_pids=sorted(self.current_roots()), process_names=sorted(self.process_names),
                        utc_offset=time.time() - now, watched_addresses=sorted(self.tracker.watched))
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def loop(self):
        period = 1.0 / self.poll_hz
        last = None
        while not self.stop_event.is_set():
            started = self.clock()
            if last is not None:
                self.intervals.append(started - last)
            last = started
            try:
                self.poll()
            except Exception as ex:
                self.error = f"{type(ex).__name__}: {ex}"
                self.log.write("error", t=self.clock(), utc=time.time(), error=self.error)
            self.stop_event.wait(max(0.0, period - (self.clock() - started)))

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(5)
        intervals = self.intervals or [0.0]
        self.log.write("stats", t=self.clock(), utc=time.time(), polls=len(self.intervals) + 1,
                       mean_interval_s=round(sum(intervals) / len(intervals), 4),
                       max_interval_s=round(max(intervals), 4),
                       processes_seen={exe: len(pids) for exe, pids in sorted(self.processes_seen.items())})
