import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import yaml

from .scenario import Action, AppScenario, Step
from .settle import Rect


class DriverError(Exception):
    pass


class EventLog:
    """JSON lines with the monotonic clock (`time.perf_counter()`, CLOCK_MONOTONIC / QueryPerformanceCounter)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.file = open(self.path, "a", encoding="utf-8")
        self.lock = threading.Lock()

    @staticmethod
    def now() -> float:
        return time.perf_counter()

    def write(self, type: str, t: float | None = None, **fields) -> float:
        t = self.now() if t is None else t
        with self.lock:
            self.file.write(json.dumps({"t": t, "type": type, **fields}, ensure_ascii=False) + "\n")
            self.file.flush()
        return t

    def close(self):
        self.file.close()

    @staticmethod
    def read(path: Path) -> list[dict]:
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


class Calibration:
    """Screen points per app and layout, stored relative to the app region's top left corner."""

    def __init__(self, path: Path, region: Rect):
        self.path = Path(path)
        self.region = region
        self.points: dict = {}
        self.window: dict = {}
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.points = dict(data.get("points") or {})
            self.window = dict(data.get("window") or {})

    def absolute(self, point) -> tuple[int, int]:
        if isinstance(point, dict):
            rel = point
        else:
            if point not in self.points:
                raise DriverError(f"Point '{point}' is not calibrated in {self.path}. "
                                  f"Run: bench.py calibrate points --app ...")
            rel = self.points[point]
        return self.region.x + int(rel["x"]), self.region.y + int(rel["y"])

    def set_point(self, name: str, absolute_x: int, absolute_y: int):
        self.points[name] = {"x": absolute_x - self.region.x, "y": absolute_y - self.region.y}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"region": self.region.to_dict(), "window": self.window, "points": self.points}, f,
                           sort_keys=True)


class TextVariables:
    def __init__(self, values: dict[str, str]):
        self.values = values

    def expand(self, text: str) -> str:
        def lookup(m):
            if m.group(1) not in self.values:
                raise DriverError(f"Unknown variable ${{{m.group(1)}}} in typed text")
            return self.values[m.group(1)]
        return re.sub(r"\$\{([\w.]+)\}", lookup, text)


class AppProcess:
    def __init__(self, app_id: str, spec: dict, desktop, region: Rect, log: EventLog | None = None,
                 output: Path | None = None):
        self.app_id = app_id
        self.output = output
        self.spec = spec
        self.desktop = desktop
        self.region = region
        self.log = log
        self.process: subprocess.Popen | None = None
        self.window = None
        self.window_error: Exception | None = None

    def launch(self, place_window: bool = True) -> threading.Thread | None:
        env = dict(os.environ)
        env.update({k: str(v) for k, v in (self.spec.get("env") or {}).items()})
        for key in self.spec.get("unset_env") or []:
            env.pop(key, None)
        for directory in self.spec.get("create_dirs") or []:
            Path(directory).mkdir(parents=True, exist_ok=True)
        command = self.spec["launch"]
        self.process = self.desktop.start_process(command, env, self.spec.get("cwd"), self.output)
        if not place_window:
            return None
        thread = threading.Thread(target=self._find_and_place, daemon=True)
        thread.start()
        return thread

    def _find_and_place(self):
        try:
            match = dict(self.spec.get("window") or {})
            self.window = self.desktop.find_window(match, self.process.pid if self.process else None,
                                                   float(match.get("timeout_s", 120)))
            self.desktop.place_window(self.window, self.region, self.spec.get("window_offsets") or {})
            if self.log:
                self.log.write("window_placed", window=str(self.window))
        except Exception as ex:
            self.window_error = ex
            if self.log:
                self.log.write("window_error", error=str(ex))

    def ensure_window(self, timeout_s: float = 120) -> object:
        if self.window is None:
            self._find_and_place()
        if self.window is None:
            raise DriverError(f"{self.app_id}: window not found: {self.window_error}")
        return self.window

    def close(self):
        close = self.spec.get("close") or {"key": "ctrl+q"}
        timeout = float(close.get("timeout_s", 60))
        try:
            if "key" in close and self.window is not None:
                self.desktop.focus_window(self.window)
                self.desktop.key(close["key"])
            elif "command" in close:
                subprocess.run(close["command"], check=False, timeout=timeout)
            elif self.process is not None:
                self.desktop.terminate(self.process)
        except Exception as ex:
            if self.log:
                self.log.write("close_error", error=str(ex))
        self.wait_exit(timeout)

    def wait_exit(self, timeout: float):
        names = self.spec.get("process_names") or []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            own_exited = self.process is None or self.process.poll() is not None
            if own_exited and not (names and self.desktop.processes_running(names)):
                return
            time.sleep(0.2)
        if self.process is not None and self.process.poll() is None:
            self.desktop.kill_tree(self.process)
        if names:
            self.desktop.kill_by_name(names)
        if self.log:
            self.log.write("killed_after_timeout", app=self.app_id)


class ScenarioDriver:
    def __init__(self, desktop, app: AppProcess, calibration: Calibration, variables: TextVariables,
                 log: EventLog, marker=None, live=None, type_delay_ms: int = 40, live_quiet_s: float = 1.5,
                 step_timeout_s: float = 300.0):
        self.desktop = desktop
        self.app = app
        self.calibration = calibration
        self.variables = variables
        self.log = log
        self.marker = marker
        self.live = live
        self.type_delay_ms = type_delay_ms
        self.live_quiet_s = live_quiet_s
        self.step_timeout_s = step_timeout_s
        self.next_marker_code = 1
        self.live_references: dict = {}

    def show_marker(self, label: str) -> float:
        code = self.next_marker_code
        self.next_marker_code += 1
        t = self.marker.show(code)
        self.log.write("marker", t=t, code=code, label=label)
        return t

    def marker_burst(self, label: str, count: int = 5, spacing_s: float = 0.12):
        for _ in range(count):
            self.show_marker(label)
            time.sleep(spacing_s)

    def do_actions(self, actions: list[Action], phase: str, step: Step | None = None,
                   trigger_index: int = -1) -> float | None:
        trigger_time = None
        for i, action in enumerate(actions):
            if i == trigger_index:
                self.show_marker(f"step:{step.name}")
            t_before = EventLog.now()
            self.perform(action)
            t_after = EventLog.now()
            if action.is_input:
                fields = {"phase": phase, "action": action.kind, "arg": self.loggable_arg(action),
                          "t_before": t_before}
                if step is not None:
                    fields["step"] = step.name
                self.log.write("input", t=t_after, **fields)
                if i == trigger_index:
                    trigger_time = self.log.write("step_start", t=t_after, step=step.name, measure=step.measure)
        return trigger_time

    def loggable_arg(self, action: Action):
        if action.kind == "type" and "password" in str(action.arg):
            return "<password>"
        return action.arg

    def run_steps(self, scenario: AppScenario, live_quiet_overrides: dict | None = None):
        for step in scenario.steps:
            trigger = step.trigger_index if step.measure else -1
            since = self.do_actions(step.actions, "step", step, trigger)
            if not step.measure:
                continue
            timeout = float(step.timeout_s or self.step_timeout_s)
            quiet = float((live_quiet_overrides or {}).get(step.name, self.live_quiet_s))
            settled, info = self.live.wait_settled(since, quiet, timeout, step.name,
                                                   reference=self.live_references.get(step.name))
            self.log.write("step_live_settled" if settled else "step_live_timeout", step=step.name, **info)
            if not settled:
                raise DriverError(f"Step '{step.name}' didn't settle within {timeout:.0f} s")

    def perform(self, action: Action):
        kind = action.kind
        if kind == "launch":
            self.app.launch(place_window=bool(action.options.get("place_window", True)))
        elif kind == "close":
            self.app.close()
        elif kind == "key":
            for _ in range(int(action.options.get("repeat", 1))):
                self.desktop.key(str(action.arg))
        elif kind == "type":
            delay = int(action.options.get("delay_ms", self.type_delay_ms))
            self.desktop.type_text(self.variables.expand(str(action.arg)), delay)
        elif kind in ("click", "double_click", "right_click"):
            x, y = self.calibration.absolute(action.arg)
            button = 3 if kind == "right_click" else 1
            self.desktop.click(x, y, button, 2 if kind == "double_click" else 1,
                               float(action.options.get("hover_s", 0.15)))
        elif kind == "scroll":
            x, y = self.calibration.absolute(action.arg)
            self.desktop.scroll(x, y, int(action.options.get("clicks", 5)))
        elif kind == "drag":
            x0, y0 = self.calibration.absolute(action.arg)
            x1, y1 = self.calibration.absolute(action.options["to"])
            self.desktop.drag(x0, y0, x1, y1, float(action.options.get("duration_s", 0.6)))
        elif kind == "sleep":
            time.sleep(float(action.arg))
        elif kind == "wait_window":
            self.app.ensure_window(float(action.options.get("timeout_s", 120)))
        elif kind == "focus":
            self.desktop.focus_window(self.app.ensure_window())
        elif kind == "wait_settled":
            since = EventLog.now()
            quiet = float(action.options.get("quiet_s", self.live_quiet_s))
            timeout = float(action.options.get("timeout_s", self.step_timeout_s))
            settled, info = self.live.wait_settled(since, quiet, timeout, "prepare",
                                                   expect_change=bool(action.options.get("expect_change", False)))
            if not settled:
                raise DriverError(f"Screen didn't settle within {timeout:.0f} s while preparing")
        else:
            raise DriverError(f"Action '{kind}' not supported")
