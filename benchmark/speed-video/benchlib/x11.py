import os
import re
import signal
import subprocess
import time
from pathlib import Path

from .marker import MarkerCode
from .settle import Rect


class X11Error(Exception):
    pass


class X11Desktop:
    platform = "linux"

    def __init__(self, display: str, xdotool: str = "xdotool"):
        self.display = display
        self.xdotool_path = xdotool
        self.env = {**os.environ, "DISPLAY": display}

    def xdotool(self, *args, timeout: float = 30, check: bool = True) -> str:
        result = subprocess.run([self.xdotool_path, *map(str, args)], env=self.env, capture_output=True, text=True,
                                timeout=timeout)
        if check and result.returncode != 0:
            raise X11Error(f"xdotool {' '.join(map(str, args))} failed: {result.stderr.strip()}")
        return result.stdout

    def key(self, combo: str):
        self.xdotool("key", *combo.split())

    def type_text(self, text: str, delay_ms: int):
        self.xdotool("type", "--delay", delay_ms, "--", text, timeout=60 + len(text) * delay_ms / 1000)

    def move(self, x: int, y: int):
        self.xdotool("mousemove", "--sync", x, y)

    def click(self, x: int, y: int, button: int = 1, count: int = 1, hover_s: float = 0.15):
        self.move(x, y)
        time.sleep(hover_s)
        self.xdotool("click", "--repeat", count, "--delay", 80, button)

    def drag(self, x0: int, y0: int, x1: int, y1: int, duration_s: float):
        self.move(x0, y0)
        time.sleep(0.15)
        self.xdotool("mousedown", 1)
        steps = 12
        for i in range(1, steps + 1):
            time.sleep(duration_s / steps)
            self.move(x0 + (x1 - x0) * i // steps, y0 + (y1 - y0) * i // steps)
        time.sleep(0.15)
        self.xdotool("mouseup", 1)

    def scroll(self, x: int, y: int, clicks: int):
        self.move(x, y)
        self.xdotool("click", "--repeat", abs(clicks), "--delay", 30, 5 if clicks > 0 else 4)

    def pointer_position(self) -> tuple[int, int]:
        out = self.xdotool("getmouselocation", "--shell")
        values = dict(line.split("=", 1) for line in out.split() if "=" in line)
        return int(values["X"]), int(values["Y"])

    def find_window(self, match: dict, pid: int | None, timeout_s: float):
        args = ["search", "--onlyvisible"]
        if match.get("class"):
            args += ["--class", match["class"]]
        elif match.get("classname"):
            args += ["--classname", match["classname"]]
        elif match.get("name"):
            args += ["--name", match["name"]]
        elif pid:
            args += ["--pid", pid]
        else:
            raise X11Error("Window match needs class, classname, name or a process id")
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            out = self.xdotool(*args, check=False)
            ids = [w for w in out.split() if w.isdigit()]
            if ids:
                return self.largest_window(ids)
            time.sleep(0.05)
        raise X11Error(f"No window matching {match} appeared within {timeout_s:.0f} s; visible windows: "
                       f"{self.visible_window_names()}")

    def visible_window_names(self) -> list[str]:
        ids = self.xdotool("search", "--onlyvisible", "--name", ".", check=False).split()
        return [self.xdotool("getwindowname", wid, check=False).strip() for wid in ids]

    def largest_window(self, ids: list[str]) -> str:
        def area(wid):
            try:
                g = self.window_geometry(wid)
                return g.width * g.height
            except X11Error:
                return 0
        return max(ids, key=area)

    def window_geometry(self, wid) -> Rect:
        out = self.xdotool("getwindowgeometry", "--shell", wid)
        values = dict(line.split("=", 1) for line in out.split() if "=" in line)
        return Rect(int(values["X"]), int(values["Y"]), int(values["WIDTH"]), int(values["HEIGHT"]))

    def place_window(self, wid, region: Rect, offsets: dict):
        x = region.x + int(offsets.get("x", 0))
        y = region.y + int(offsets.get("y", 0))
        width = region.width + int(offsets.get("width", 0))
        height = region.height + int(offsets.get("height", 0))
        self.xdotool("windowsize", wid, width, height)
        self.xdotool("windowmove", wid, x, y)

    def focus_window(self, wid):
        activated = subprocess.run([self.xdotool_path, "windowactivate", "--sync", str(wid)], env=self.env,
                                   capture_output=True, timeout=5).returncode == 0
        if not activated:
            self.xdotool("windowfocus", "--sync", wid, check=False, timeout=5)

    def start_process(self, command: list[str], env: dict, cwd: str | None, output: Path | None = None):
        env = {**env, "DISPLAY": self.display}
        out = open(output, "ab") if output else subprocess.DEVNULL
        return subprocess.Popen(command, env=env, cwd=cwd, stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)

    def terminate(self, process: subprocess.Popen):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def kill_tree(self, process: subprocess.Popen):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def matching_pids(self, patterns: list[str]) -> list[int]:
        own_uid = os.getuid()
        pids = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit() or int(entry.name) == os.getpid():
                continue
            try:
                if entry.stat().st_uid != own_uid:
                    continue
                cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                continue
            if any(re.search(p, cmdline) for p in patterns):
                pids.append(int(entry.name))
        return pids

    def processes_running(self, patterns: list[str]) -> bool:
        return bool(self.matching_pids(patterns))

    def kill_by_name(self, patterns: list[str]):
        for pid in self.matching_pids(patterns):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def marker_window(self, x: int, y: int, code: MarkerCode) -> "X11MarkerWindow":
        return X11MarkerWindow(self.display, x, y, code)

    def ffmpeg_input(self, region: Rect, fps: int, draw_mouse: bool) -> list[str]:
        return ["-f", "x11grab", "-framerate", str(fps), "-video_size", f"{region.width}x{region.height}",
                "-draw_mouse", "1" if draw_mouse else "0", "-thread_queue_size", "512",
                "-i", f"{self.display}+{region.x},{region.y}"]

    def affinity_prefix(self, cpus: str | None) -> list[str]:
        return ["taskset", "-c", cpus] if cpus else []

    def set_affinity(self, process: subprocess.Popen, cpus: str | None):
        pass

    def describe_display(self, xdpyinfo: str = "xdpyinfo") -> dict:
        info = {"display": self.display, "session_type": os.environ.get("XDG_SESSION_TYPE", "x11")}
        try:
            out = subprocess.run([xdpyinfo], env=self.env, capture_output=True, text=True, timeout=10).stdout
            m = re.search(r"dimensions:\s+(\d+x\d+)", out)
            if m:
                info["resolution"] = m.group(1)
            m = re.search(r"depth of root window:\s+(\d+)", out)
            if m:
                info["depth"] = int(m.group(1))
        except (OSError, subprocess.TimeoutExpired):
            pass
        return info


class X11MarkerWindow:
    def __init__(self, display_name: str, x: int, y: int, code: MarkerCode):
        from Xlib import X, display as xdisplay

        self.X = X
        self.code = code
        self.display = xdisplay.Display(display_name)
        screen = self.display.screen()
        self.window = screen.root.create_window(
            x, y, code.width, code.height, 0, screen.root_depth, X.InputOutput, X.CopyFromParent,
            background_pixel=screen.black_pixel, override_redirect=True, backing_store=X.Always,
            event_mask=X.ExposureMask)
        self.white = self.window.create_gc(foreground=screen.white_pixel)
        self.black = self.window.create_gc(foreground=screen.black_pixel)
        self.window.map()
        self.display.sync()

    def show(self, code: int) -> float:
        cell = self.code.cell_px
        self.window.configure(stack_mode=self.X.Above)
        for i, white in enumerate(self.code.cells(code)):
            self.window.fill_rectangle(self.white if white else self.black, i * cell, 0, cell, cell)
        self.display.sync()
        return time.perf_counter()

    def close(self):
        self.window.destroy()
        self.display.sync()
        self.display.close()
