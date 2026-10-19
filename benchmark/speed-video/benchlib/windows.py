import ctypes
import re
import subprocess
import threading
import time
from ctypes import wintypes
from pathlib import Path

from .marker import MarkerCode
from .settle import Rect


class WindowsDesktopError(Exception):
    pass


ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


class WindowsDesktop:
    platform = "windows"
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004

    virtual_keys = {
        "return": 0x0D, "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B, "space": 0x20,
        "backspace": 0x08, "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23, "prior": 0x21,
        "page_up": 0x21, "next": 0x22, "page_down": 0x22, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
        "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "super": 0x5B, "win": 0x5B,
        **{f"f{i}": 0x6F + i for i in range(1, 13)},
    }
    extended_keys = {0x2E, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x25, 0x26, 0x27, 0x28}

    def __init__(self, monitor_index: int = 0):
        self.monitor_index = monitor_index
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        if hasattr(self.user32, "SetProcessDpiAwarenessContext"):
            self.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        else:
            self.user32.SetProcessDPIAware()
        self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self.user32.VkKeyScanW.restype = ctypes.c_short
        self.user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.GetAncestor.restype = wintypes.HWND
        self.kernel32.OpenProcess.restype = wintypes.HANDLE
        self.kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.kernel32.SetProcessAffinityMask.argtypes = (wintypes.HANDLE, ctypes.c_size_t)
        self.kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                             ctypes.POINTER(wintypes.DWORD))

    def send(self, *inputs: INPUT):
        array = (INPUT * len(inputs))(*inputs)
        sent = self.user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
        if sent != len(inputs):
            raise WindowsDesktopError(f"SendInput sent {sent} of {len(inputs)} events (error {ctypes.get_last_error()})")

    def key_input(self, vk: int, up: bool) -> INPUT:
        KEYEVENTF_EXTENDEDKEY = 0x0001
        flags = (self.KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in self.extended_keys else 0)
        return INPUT(self.INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(vk, 0, flags, 0, 0)))

    def vk_for(self, name: str) -> list[int]:
        """Virtual keys for one key name: modifiers that VkKeyScanW reports (shift, ctrl, alt), then the key."""
        lower = name.lower()
        if lower in self.virtual_keys:
            return [self.virtual_keys[lower]]
        if len(name) == 1:
            result = self.user32.VkKeyScanW(name)
            if result == -1:
                raise WindowsDesktopError(f"No virtual key for '{name}'")
            shift_state = (result >> 8) & 0xFF
            modifiers = [vk for bit, vk in ((1, 0x10), (2, 0x11), (4, 0x12)) if shift_state & bit]
            return [*modifiers, result & 0xFF]
        raise WindowsDesktopError(f"Unknown key name '{name}'")

    def key(self, combo: str):
        for chord in combo.split():
            keys = []
            for name in chord.split("+"):
                keys += [vk for vk in self.vk_for(name) if vk not in keys]
            self.send(*[self.key_input(vk, False) for vk in keys], *[self.key_input(vk, True) for vk in reversed(keys)])

    def type_text(self, text: str, delay_ms: int):
        KEYEVENTF_UNICODE = 0x0004
        for ch in text:
            units = ch.encode("utf-16-le")
            for i in range(0, len(units), 2):
                code = int.from_bytes(units[i:i + 2], "little")
                down = INPUT(self.INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0)))
                up = INPUT(self.INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE |
                                                                          self.KEYEVENTF_KEYUP, 0, 0)))
                self.send(down, up)
            time.sleep(delay_ms / 1000)

    def virtual_screen(self) -> Rect:
        return Rect(self.user32.GetSystemMetrics(76), self.user32.GetSystemMetrics(77),
                    self.user32.GetSystemMetrics(78), self.user32.GetSystemMetrics(79))

    def mouse_input(self, flags: int, x: int = 0, y: int = 0, data: int = 0) -> INPUT:
        INPUT_MOUSE = 0
        return INPUT(INPUT_MOUSE, _INPUTUNION(mi=MOUSEINPUT(x, y, data, flags, 0, 0)))

    def move(self, x: int, y: int):
        MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_VIRTUALDESK = 0x0001, 0x8000, 0x4000
        screen = self.virtual_screen()
        nx = round((x - screen.x) * 65535 / max(1, screen.width - 1))
        ny = round((y - screen.y) * 65535 / max(1, screen.height - 1))
        self.send(self.mouse_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny))

    def click(self, x: int, y: int, button: int = 1, count: int = 1, hover_s: float = 0.15):
        MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
        self.move(x, y)
        time.sleep(hover_s)
        down, up = (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP) if button == 3 else \
            (self.MOUSEEVENTF_LEFTDOWN, self.MOUSEEVENTF_LEFTUP)
        for i in range(count):
            self.send(self.mouse_input(down), self.mouse_input(up))
            if i + 1 < count:
                time.sleep(0.08)

    def drag(self, x0: int, y0: int, x1: int, y1: int, duration_s: float):
        self.move(x0, y0)
        time.sleep(0.15)
        self.send(self.mouse_input(self.MOUSEEVENTF_LEFTDOWN))
        steps = 12
        for i in range(1, steps + 1):
            time.sleep(duration_s / steps)
            self.move(x0 + (x1 - x0) * i // steps, y0 + (y1 - y0) * i // steps)
        time.sleep(0.15)
        self.send(self.mouse_input(self.MOUSEEVENTF_LEFTUP))

    def scroll(self, x: int, y: int, clicks: int):
        MOUSEEVENTF_WHEEL = 0x0800
        self.move(x, y)
        for _ in range(abs(clicks)):
            self.send(self.mouse_input(MOUSEEVENTF_WHEEL, data=ctypes.c_uint32(-120 if clicks > 0 else 120).value))
            time.sleep(0.03)

    def pointer_position(self) -> tuple[int, int]:
        point = wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def top_level_windows(self) -> list[tuple[int, int, str, str]]:
        windows = []
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, _):
            if not self.user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            title = ctypes.create_unicode_buffer(512)
            self.user32.GetWindowTextW(hwnd, title, 512)
            cls = ctypes.create_unicode_buffer(256)
            self.user32.GetClassNameW(hwnd, cls, 256)
            windows.append((hwnd, pid.value, title.value, cls.value))
            return True

        self.user32.EnumWindows(enum_proc(callback), 0)
        return windows

    def process_image_name(self, pid: int) -> str:
        handle = self.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(1024)
            if self.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return Path(buf.value).name.lower()
            return ""
        finally:
            self.kernel32.CloseHandle(handle)

    def find_window(self, match: dict, pid: int | None, timeout_s: float):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            candidates = []
            for hwnd, wpid, title, cls in self.top_level_windows():
                if match.get("class") and cls != match["class"]:
                    continue
                if match.get("name") and not re.search(match["name"], title):
                    continue
                if match.get("process") and self.process_image_name(wpid) != match["process"].lower():
                    continue
                if not (match.get("class") or match.get("name") or match.get("process")) and wpid != pid:
                    continue
                candidates.append(hwnd)
            if candidates:
                return max(candidates, key=lambda h: self.window_geometry(h).width * self.window_geometry(h).height)
            time.sleep(0.05)
        raise WindowsDesktopError(f"No window matching {match} appeared within {timeout_s:.0f} s")

    def window_geometry(self, hwnd) -> Rect:
        rect = wintypes.RECT()
        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return Rect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

    def place_window(self, hwnd, region: Rect, offsets: dict):
        self.user32.ShowWindow(hwnd, 9)
        self.user32.MoveWindow(hwnd, region.x + int(offsets.get("x", 0)), region.y + int(offsets.get("y", 0)),
                               region.width + int(offsets.get("width", 0)),
                               region.height + int(offsets.get("height", 0)), True)

    def window_process_id(self, hwnd) -> int:
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def foreground_matches(self, match: dict, pid: int | None, hwnd) -> bool:
        GA_ROOTOWNER = 3
        foreground = self.user32.GetForegroundWindow()
        if not foreground:
            return False
        if foreground == hwnd or self.user32.GetAncestor(foreground, GA_ROOTOWNER) == hwnd:
            return True
        foreground_pid = self.window_process_id(foreground)
        if foreground_pid in (pid, self.window_process_id(hwnd)):
            return True
        return bool(match.get("process")) and self.process_image_name(foreground_pid) == match["process"].lower()

    def focus_window(self, hwnd):
        """SetForegroundWindow only works for the foreground process; attach to its input queue first."""
        foreground = self.user32.GetForegroundWindow()
        own_thread = self.kernel32.GetCurrentThreadId()
        other_thread = self.user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        attached = bool(other_thread and other_thread != own_thread and
                        self.user32.AttachThreadInput(own_thread, other_thread, True))
        try:
            self.user32.ShowWindow(hwnd, 9)
            self.user32.BringWindowToTop(hwnd)
            self.user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                self.user32.AttachThreadInput(own_thread, other_thread, False)

    def start_process(self, command: list[str], env: dict, cwd: str | None, output: Path | None = None):
        out = open(output, "ab") if output else subprocess.DEVNULL
        return subprocess.Popen(command, env=env, cwd=cwd, stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

    def terminate(self, process: subprocess.Popen):
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T"], capture_output=True)

    def kill_tree(self, process: subprocess.Popen):
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)

    def running_image_names(self) -> set[str]:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
        return {line.split('","')[0].strip('"').lower() for line in out.splitlines() if line}

    def processes_running(self, names: list[str], env: dict | None = None) -> bool:
        running = self.running_image_names()
        return any(n.lower() in running for n in names)

    def kill_by_name(self, names: list[str], env: dict | None = None):
        for name in names:
            subprocess.run(["taskkill", "/IM", name, "/T", "/F"], capture_output=True)

    def marker_window(self, x: int, y: int, code: MarkerCode) -> "WindowsMarkerWindow":
        return WindowsMarkerWindow(self.user32, x, y, code)

    def ffmpeg_input(self, region: Rect, fps: int, draw_mouse: bool) -> list[str]:
        source = (f"ddagrab=output_idx={self.monitor_index}:framerate={fps}:draw_mouse={int(draw_mouse)}"
                  f":offset_x={region.x}:offset_y={region.y}:video_size={region.width}x{region.height}")
        return ["-f", "lavfi", "-i", source]

    def capture_prefilter(self) -> str:
        return "hwdownload,format=bgra"

    def affinity_prefix(self, cpus: str | None) -> list[str]:
        return []

    def set_affinity(self, process: subprocess.Popen, cpus: str | None):
        if not cpus:
            return
        mask = 0
        for part in cpus.split(","):
            low, _, high = part.partition("-")
            for cpu in range(int(low), int(high or low) + 1):
                mask |= 1 << cpu
        handle = self.kernel32.OpenProcess(0x0200 | 0x0400, False, process.pid)
        try:
            self.kernel32.SetProcessAffinityMask(handle, ctypes.c_size_t(mask))
        finally:
            self.kernel32.CloseHandle(handle)

    def describe_display(self, xdpyinfo: str = "") -> dict:
        screen = self.virtual_screen()
        primary = self.primary_monitor()
        return {"resolution": f"{screen.width}x{screen.height}", "scale_percent": self.scale_percent(),
                "primary": primary["monitor"].to_dict(), "work_area": primary["work_area"].to_dict(),
                "monitors": self.monitor_count()}

    def scale_percent(self) -> int:
        return round(self.user32.GetDpiForSystem() * 100 / 96)

    def monitor_count(self) -> int:
        return int(self.user32.GetSystemMetrics(80))

    def primary_monitor(self) -> dict:
        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD)]

        MONITOR_DEFAULTTOPRIMARY = 1
        self.user32.MonitorFromPoint.restype = wintypes.HANDLE
        self.user32.MonitorFromPoint.argtypes = (wintypes.POINT, wintypes.DWORD)
        self.user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
        monitor = self.user32.MonitorFromPoint(wintypes.POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        self.user32.GetMonitorInfoW(monitor, ctypes.byref(info))

        def rect(r):
            return Rect(r.left, r.top, r.right - r.left, r.bottom - r.top)

        return {"monitor": rect(info.rcMonitor), "work_area": rect(info.rcWork)}

    def ui_language(self) -> str:
        lang_id = self.kernel32.GetUserDefaultUILanguage()
        return {0x07: "de", 0x09: "en"}.get(lang_id & 0x3FF, f"0x{lang_id:04x}")

    def screenshot(self, path: Path) -> Path:
        from PIL import ImageGrab
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        ImageGrab.grab(all_screens=True).save(path)
        return path

    def move_window(self, hwnd, x: int, y: int):
        SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0004, 0x0010
        self.user32.SetWindowPos(hwnd, None, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    def is_window(self, hwnd) -> bool:
        return bool(self.user32.IsWindow(hwnd))

    def is_minimized(self, hwnd) -> bool:
        return bool(self.user32.IsIconic(hwnd))

    def console_window(self):
        self.kernel32.GetConsoleWindow.restype = wintypes.HWND
        return self.kernel32.GetConsoleWindow()

    def show_window(self, hwnd, minimized: bool):
        SW_MINIMIZE, SW_RESTORE = 6, 9
        self.user32.ShowWindow(hwnd, SW_MINIMIZE if minimized else SW_RESTORE)

    def has_caption(self, hwnd) -> bool:
        GWL_STYLE, WS_CAPTION = -16, 0x00C00000
        return self.user32.GetWindowLongW(hwnd, GWL_STYLE) & WS_CAPTION == WS_CAPTION

    def window_keeper(self, process_ids, region: Rect, main_match: dict, offsets: dict | None = None,
                      poll_s: float = 0.05) -> "WindowKeeper":
        return WindowKeeper(self, process_ids, region, main_match, offsets or {}, poll_s)


class WindowKeeper:
    """Keeps an app's windows in the recorded area while it runs: the main window (by class or process match) gets
    the app region's position and size, every other new window of the app's processes (setup dialogs) is moved,
    at its own size, to the region's center. Runs in its own thread; `placed` lists what it did."""

    def __init__(self, desktop: WindowsDesktop, process_ids, region: Rect, main_match: dict, offsets: dict,
                 poll_s: float = 0.05):
        self.desktop = desktop
        self.process_ids = process_ids
        self.region = region
        self.main_match = main_match
        self.offsets = offsets
        self.poll_s = poll_s
        self.known: set = set()
        self.placed: list[dict] = []
        self.main = None
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def start(self) -> "WindowKeeper":
        self.thread.start()
        return self

    def is_main(self, hwnd, title: str, cls: str, geometry: Rect) -> bool:
        if self.main_match.get("class"):
            return cls == self.main_match["class"]
        if self.main_match.get("name"):
            return bool(re.search(self.main_match["name"], title))
        main_gone = self.main is None or not self.desktop.is_window(self.main)
        return main_gone and geometry.width >= 400 and geometry.height >= 300

    def inside_region(self, geometry: Rect) -> bool:
        r = self.region
        return geometry.x >= r.x and geometry.y >= r.y and geometry.x + geometry.width <= r.x + r.width and \
            geometry.y + geometry.height <= r.y + r.height

    def target(self, hwnd, title: str, cls: str) -> tuple[str, Rect] | None:
        """Popups (menus, drop-down lists, tooltips) have no caption and stay where the app puts them."""
        geometry = self.desktop.window_geometry(hwnd)
        if self.is_main(hwnd, title, cls, geometry):
            return "main", self.region
        if not self.desktop.has_caption(hwnd) or self.inside_region(geometry):
            return None
        x = self.region.x + max(0, (self.region.width - geometry.width) // 2)
        y = self.region.y + max(0, (self.region.height - geometry.height) // 2)
        return "dialog", Rect(x, y, geometry.width, geometry.height)

    def check(self):
        pids = set(self.process_ids())
        for hwnd, pid, title, cls in self.desktop.top_level_windows():
            if pid not in pids or hwnd in self.known:
                continue
            self.known.add(hwnd)
            placement = self.target(hwnd, title, cls)
            if placement is None:
                continue
            kind, rect = placement
            if kind == "main":
                self.main = hwnd
                self.desktop.place_window(hwnd, rect, self.offsets)
            else:
                self.desktop.move_window(hwnd, rect.x, rect.y)
            self.placed.append({"t": time.perf_counter(), "kind": kind, "class": cls, "title": title,
                                "rect": rect.to_dict()})

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.check()
            except Exception:
                pass
            self.stop_event.wait(self.poll_s)

    def stop(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(2)


class WindowsMarkerWindow:
    """Topmost popup window, painted from its own message-loop thread."""

    def __init__(self, user32, x: int, y: int, code: MarkerCode):
        self.user32 = user32
        self.gdi32 = ctypes.WinDLL("gdi32")
        self.code = code
        self.cells = code.cells(0)
        self.hwnd = None
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self.message_loop, args=(x, y), daemon=True)
        self.thread.start()
        if not self.ready.wait(10):
            raise WindowsDesktopError("Marker window didn't start")

    def message_loop(self, x: int, y: int):
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32, gdi32 = self.user32, self.gdi32
        user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.DefWindowProcW.restype = ctypes.c_ssize_t

        class PAINTSTRUCT(ctypes.Structure):
            _fields_ = [("hdc", wintypes.HDC), ("fErase", wintypes.BOOL), ("rcPaint", wintypes.RECT),
                        ("fRestore", wintypes.BOOL), ("fIncUpdate", wintypes.BOOL), ("rgbReserved", ctypes.c_byte * 32)]

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

        gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
        user32.BeginPaint.restype = wintypes.HDC
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                           wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        white = gdi32.CreateSolidBrush(0x00FFFFFF)
        black = gdi32.CreateSolidBrush(0x00000000)
        cell = self.code.cell_px

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == 0x000F:
                ps = PAINTSTRUCT()
                hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
                for i, is_white in enumerate(self.cells):
                    rect = wintypes.RECT(i * cell, 0, (i + 1) * cell, cell)
                    user32.FillRect(hdc, ctypes.byref(rect), white if is_white else black)
                user32.EndPaint(hwnd, ctypes.byref(ps))
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self.wndproc = WNDPROC(wndproc)
        wc = WNDCLASSW(lpfnWndProc=self.wndproc, lpszClassName="BenchSyncMarker",
                       hInstance=kernel32.GetModuleHandleW(None))
        user32.RegisterClassW(ctypes.byref(wc))
        WS_POPUP, WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000000, 0x8, 0x80, 0x08000000
        self.hwnd = user32.CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, "BenchSyncMarker", "",
                                           WS_POPUP, x, y, self.code.width, self.code.height, None, None,
                                           wc.hInstance, None)
        user32.ShowWindow(self.hwnd, 4)
        self.ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def show(self, code: int) -> float:
        self.cells = self.code.cells(code)
        self.user32.InvalidateRect(self.hwnd, None, False)
        self.user32.RedrawWindow(self.hwnd, None, None, 0x0001 | 0x0100)
        return time.perf_counter()

    def close(self):
        self.user32.PostMessageW(self.hwnd, 0x0010, 0, 0)
