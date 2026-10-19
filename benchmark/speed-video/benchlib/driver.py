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


class StepTimeout(DriverError):
    """The app didn't finish a step within the task's time limit: a measurement ("not done within N s")."""

    def __init__(self, step: str, limit_s: float):
        super().__init__(f"Step '{step}' didn't settle within its time limit of {limit_s:.0f} s")
        self.step = step
        self.limit_s = limit_s


class NoReaction(DriverError):
    pass


class FocusError(DriverError):
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

    def clock(self, label: str) -> float:
        """Pairs the monotonic clock with UTC wall time, to match the run with the server's log."""
        return self.write("clock", label=label, utc=time.time())

    def close(self):
        self.file.close()

    @staticmethod
    def read(path: Path) -> list[dict]:
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    @staticmethod
    def utc_offset(events: list[dict]) -> float | None:
        clocks = [e for e in events if e["type"] == "clock"]
        return clocks[0]["utc"] - clocks[0]["t"] if clocks else None


class Calibration:
    """Screen points and regions per app and layout, stored relative to the app region's top left corner."""

    def __init__(self, path: Path, region: Rect):
        self.path = Path(path)
        self.region = region
        self.points: dict = {}
        self.regions: dict = {}
        self.window: dict = {}
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.points = dict(data.get("points") or {})
            self.regions = dict(data.get("regions") or {})
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

    def set_region(self, name: str, corner_a: tuple[int, int], corner_b: tuple[int, int]):
        (xa, ya), (xb, yb) = corner_a, corner_b
        self.regions[name] = {"x": min(xa, xb) - self.region.x, "y": min(ya, yb) - self.region.y,
                              "width": abs(xb - xa) + 1, "height": abs(yb - ya) + 1}

    def region_rects(self) -> dict[str, Rect]:
        return {name: Rect.from_dict(r) for name, r in self.regions.items()}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"region": self.region.to_dict(), "window": self.window, "points": self.points,
                            "regions": self.regions}, f, sort_keys=True)


class TextVariables:
    def __init__(self, values: dict[str, str], secret_names: set[str] | None = None):
        self.values = values
        self.secret_names = set(secret_names or ())

    @property
    def secrets(self) -> list[str]:
        return [self.values[n] for n in self.secret_names if self.values.get(n)]

    def expand(self, text: str) -> str:
        def lookup(m):
            if m.group(1) not in self.values:
                raise DriverError(f"Unknown variable ${{{m.group(1)}}} in typed text")
            return self.values[m.group(1)]
        return re.sub(r"\$\{([\w.]+)\}", lookup, text)

    def is_secret(self, text: str) -> bool:
        return any(f"${{{name}}}" in text for name in self.secret_names)

    def redact(self, text: str) -> str:
        for secret in sorted(self.secrets, key=len, reverse=True):
            text = text.replace(secret, "<secret>")
        return text


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

    def client_origin(self) -> tuple[int, int] | None:
        """The screen position of the app window's client area, where the window system knows it better than the
        app (Windows); None: the app's own value counts."""
        return None

    def notes(self) -> dict:
        """What the run's meta.json records about the app's windows."""
        return {}

    def ensure_foreground(self):
        """Keys and typed text go to the foreground window: make sure it is the app's, or fail."""
        if self.spec.get("focus_check") is False:
            return
        window = self.ensure_window()
        match = dict(self.spec.get("window") or {})
        pid = self.process.pid if self.process else None
        if self.desktop.foreground_matches(match, pid, window):
            return
        self.desktop.focus_window(window)
        time.sleep(0.2)
        if not self.desktop.foreground_matches(match, pid, window):
            raise FocusError(f"{self.app_id}: its window isn't in the foreground, so no keys were sent")

    def close(self) -> bool:
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
        return self.wait_exit(timeout)

    def wait_exit(self, timeout: float) -> bool:
        names = self.spec.get("process_names") or []
        env = self.spec.get("process_env")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            own_exited = self.process is None or self.process.poll() is not None
            if own_exited and not (names and self.desktop.processes_running(names, env)):
                return True
            time.sleep(0.2)
        if self.process is not None and self.process.poll() is None:
            self.desktop.kill_tree(self.process)
        if names:
            self.desktop.kill_by_name(names, env)
        if self.log:
            self.log.write("killed_after_timeout", app=self.app_id)
        return False


class ProbeInputs:
    """Inputs of a probe's completeness check after the measured end (e.g. End in the message list): logged with
    phase "verify", never user actions."""

    def __init__(self, driver: "ScenarioDriver"):
        self.driver = driver

    def click(self, x: int, y: int):
        t_before = EventLog.now()
        self.driver.desktop.click(x, y)
        self.driver.log.write("input", t=EventLog.now(), phase="verify", action="click", arg={"x": x, "y": y},
                              t_before=t_before)
        if self.driver.park:
            self.driver.desktop.move(*self.driver.park)

    def key(self, combo: str):
        self.driver.app.ensure_foreground()
        t_before = EventLog.now()
        self.driver.desktop.key(combo)
        self.driver.log.write("input", t=EventLog.now(), phase="verify", action="key", arg=combo, t_before=t_before)


class MovingAreaWatcher:
    """Asks the probe `hz` times a second where the app shows content that changes by itself (Parula's setup
    video) and keeps the live gate's mask up to date. Every change is logged (`mask`: the rectangles in screen
    pixels; `since_t`: the previous poll, which still saw the old ones), so the analysis applies the same masks to
    the recording. It stops once that content is gone after it was there (the setup has ended)."""

    def __init__(self, probe, log: EventLog, hz: float = 10):
        self.probe = probe
        self.log = log
        self.period_s = 1.0 / hz
        self.rects: list[dict] = []
        self.live = None
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.polls = 0

    def show_to(self, live):
        self.live = live
        if live is not None:
            live.set_masks(self.rects)

    def start(self) -> "MovingAreaWatcher":
        self.thread.start()
        return self

    def loop(self):
        previous_t = None
        seen = False
        failed = False
        while not self.stop_event.is_set():
            t_before = EventLog.now()
            try:
                areas = self.probe.moving_areas()
            except Exception as ex:
                if not failed:
                    self.log.write("mask_error", error=f"{type(ex).__name__}: {ex}")
                failed = True
                self.stop_event.wait(self.period_s)
                continue
            t = EventLog.now()
            self.polls += 1
            rects = [{k: int(r[k]) for k in ("x", "y", "w", "h")} for r in areas or []]
            if rects != self.rects:
                self.log.write("mask", t=t, t_before=t_before, since_t=previous_t, rects=rects)
                self.rects = rects
                if self.live is not None:
                    self.live.set_masks(rects)
            if areas is not None:
                seen = True
            elif seen:
                self.log.write("mask_end", t=t, polls=self.polls)
                return
            previous_t = t
            self.stop_event.wait(max(0.0, self.period_s - (EventLog.now() - t_before)))

    def stop(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(5)


class ScenarioDriver:
    def __init__(self, desktop, app: AppProcess, calibration: Calibration, variables: TextVariables,
                 log: EventLog, marker=None, live=None, type_delay_ms: int = 40, quiet_s: float = 1.0,
                 step_timeout_s: float = 300.0, task_timeout_s: float | None = None,
                 park: tuple[int, int] | None = None, no_reaction_s: float | None = 60.0,
                 grace_s: float | None = 20.0, server_log=None, probe=None, expected: dict | None = None,
                 verify_path: Path | None = None, probe_interval_s: float = 1.0):
        self.desktop = desktop
        self.app = app
        self.calibration = calibration
        self.variables = variables
        self.log = log
        self.marker = marker
        self.live = live
        self.type_delay_ms = type_delay_ms
        self.quiet_s = quiet_s
        self.step_timeout_s = step_timeout_s
        self.task_timeout_s = task_timeout_s
        self.park = park
        self.no_reaction_s = no_reaction_s
        self.grace_s = grace_s
        self.server_log = server_log
        self.next_marker_code = 1
        self.live_references: dict = {}
        self.live_regions: dict = {}
        self.quiet_by_step: dict = {}
        self.probe = probe
        self.expected = dict(expected or {})
        self.verify_path = verify_path
        self.probe_interval_s = probe_interval_s
        self.waited = 0.0
        self.verify_result: dict | None = None

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
            if i == trigger_index and self.marker is not None:
                self.show_marker(f"{phase}:{step.name}")
            t_before = EventLog.now()
            t_after = self.perform(action)
            if action.is_input:
                fields = {"phase": phase, "action": action.kind, "arg": self.loggable_arg(action),
                          "t_before": t_before}
                if step is not None:
                    fields["step"] = step.name
                self.log.write("input", t=t_after, **fields)
                if i == trigger_index:
                    kind = "verify_start" if phase == "verify" else "step_start"
                    trigger_time = self.log.write(kind, t=t_after, step=step.name, measure=step.measure,
                                                  checks=step.checks)
        return trigger_time

    def loggable_arg(self, action: Action):
        if action.kind == "type" and self.variables.is_secret(str(action.arg)):
            return "<secret>"
        return action.arg

    def run_steps(self, scenario: AppScenario):
        for step in scenario.steps:
            self.run_step(step)

    def run_step(self, step: Step):
        """The step's actions; its last input starts the step's timer, which runs until the screen settles (and,
        with `complete`, until the app's probe confirms the result during a quiet period)."""
        trigger = step.trigger_index if step.measure else -1
        since = self.do_actions(step.actions, "step", step, trigger)
        if not step.measure:
            return
        limit = float(step.timeout_s or self.step_timeout_s)
        if self.task_timeout_s is not None:
            remaining = max(0.0, self.task_timeout_s - self.waited)
            limit = remaining if step.complete == "inbox_listed" or step.becomes_final else min(limit, remaining)
        complete = self.completion_check(step) if step.complete or step.becomes_final else None
        status, info = self.live.wait_settled(
            since, self.quiet_by_step.get(step.name, self.quiet_s), limit, step.name,
            reference=self.live_references.get(step.name), regions=self.live_regions.get(step.name),
            no_reaction_s=self.no_reaction_s, grace_s=self.grace_s, complete=complete,
            probe_interval_s=self.probe_interval_s)
        self.log.write(f"step_live_{status.replace('-', '_')}", step=step.name, limit_s=limit, **info)
        if status == "timeout":
            raise StepTimeout(step.name, limit)
        if status == "no-reaction":
            raise NoReaction(f"Step '{step.name}': no screen change within {self.no_reaction_s:.0f} s after "
                             f"its input (a missed click or key?)")
        self.waited += (info.get("live_end") or EventLog.now()) - since
        if step.final_reached:
            self.log.write("step_final", step=step.name)
        if step.verify:
            self.do_actions(step.verify.actions, "verify", step, Step("verify", step.verify.actions).trigger_index)
            self.live.wait_settled(EventLog.now(), self.quiet_s, max(step.verify.within_s, self.quiet_s) + 5,
                                   f"{step.name}:verify", expect_change=False)
        if step.verify_probe or (step.final_reached and step.as_final().verify_probe):
            self.probe_verify(step)

    def completion_check(self, step: Step):
        """The probe's check of a step's result: `inbox_listed`, or {"pages": [...], "fail": [...]} = the app shows
        one of these pages (a page starting with a `fail` prefix also ends the step; the flow then stops). A page of
        `becomes_final` turns the step into the final one: from then on it waits for the complete Inbox listing."""
        def check() -> bool:
            t_before = EventLog.now()
            try:
                if step.complete == "inbox_listed" or step.final_reached:
                    result = self.probe.inbox_listed(self.expected)
                else:
                    page = self.probe.page()
                    if step.becomes_final and page in step.becomes_final["pages"]:
                        step.final_reached = True
                        result = {**self.probe.inbox_listed(self.expected), "page": page, "became_final": True}
                    else:
                        failed = any(page.startswith(prefix) for prefix in (step.complete or {}).get("fail", []))
                        result = {"complete": page in (step.complete or {}).get("pages", []) or failed,
                                  "page": page, "failed": failed}
            except Exception as ex:
                result = {"complete": False, "error": self.variables.redact(f"{type(ex).__name__}: {ex}")}
            self.log.write("probe", step=step.name, check="inbox_listed" if step.final_reached else step.complete,
                           t_before=t_before, **result)
            return bool(result.get("complete"))
        return check

    def probe_verify(self, step: Step):
        """After the measured end: the probe checks completeness (e.g. all messages listed, the oldest one
        reachable). Not waiting time; its screen changes come after the step's analysis window."""
        self.log.write("verify_start", step=step.name, method=self.probe.method)
        self.probe.inputs = ProbeInputs(self)
        try:
            result = self.probe.verify(self.expected)
        except Exception as ex:
            result = {"version": 1, "method": self.probe.method, "inbox_complete": False,
                      "error": self.variables.redact(f"{type(ex).__name__}: {ex}")}
        result["step"] = step.name
        self.verify_result = result
        if self.verify_path is not None:
            self.verify_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        self.log.write("verify_end", step=step.name, inbox_complete=result.get("inbox_complete"))

    def point(self, name) -> tuple[int, int]:
        """A named UI element found by the app's probe, else a calibrated point."""
        if self.probe is not None and isinstance(name, str) and self.probe.method != "none":
            element = self.probe.wait_for(name, timeout_s=30)
            if element.get("hit") is False:
                raise DriverError(f"Element '{name}' is covered by another element at its center")
            return element.center
        return self.calibration.absolute(name)

    def perform(self, action: Action) -> float:
        kind = action.kind
        if kind == "launch":
            self.app.launch(place_window=bool(action.options.get("place_window", True)))
        elif kind == "close":
            self.app.close()
        elif kind == "key":
            self.app.ensure_foreground()
            for _ in range(int(action.options.get("repeat", 1))):
                self.desktop.key(str(action.arg))
        elif kind == "type":
            self.app.ensure_foreground()
            delay = int(action.options.get("delay_ms", self.type_delay_ms))
            self.desktop.type_text(self.variables.expand(str(action.arg)), delay)
        elif kind in ("click", "double_click", "right_click"):
            x, y = self.point(action.arg)
            button = 3 if kind == "right_click" else 1
            self.desktop.click(x, y, button, 2 if kind == "double_click" else 1,
                               float(action.options.get("hover_s", 0.15)))
        elif kind == "scroll":
            x, y = self.point(action.arg)
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
            match = {k: v for k, v in action.options.items() if k in ("name", "class", "classname", "process")}
            if match:
                window = self.desktop.find_window(match, None, float(action.options.get("timeout_s", 60)))
            else:
                window = self.app.ensure_window()
            self.desktop.focus_window(window)
        elif kind == "wait_settled":
            since = EventLog.now()
            quiet = float(action.options.get("quiet_s", self.quiet_s))
            timeout = float(action.options.get("timeout_s", self.step_timeout_s))
            status, _ = self.live.wait_settled(since, quiet, timeout, "prepare",
                                               expect_change=bool(action.options.get("expect_change", False)))
            if status != "settled":
                raise DriverError(f"Screen didn't settle within {timeout:.0f} s while preparing")
        elif kind == "wait_cloud_quiet":
            if self.server_log is None:
                raise DriverError("wait_cloud_quiet needs server.log in the config (the server's evidence log)")
            minutes = float(action.options.get("minutes", action.arg or 10))
            watch = str(action.options.get("watch", "logins"))
            info = self.server_log.wait_quiet(minutes * 60, float(action.options.get("timeout_min", 120)) * 60, watch)
            self.log.write("cloud_quiet", **info)
            if not info.get("quiet") and action.options.get("required", watch == "logins"):
                raise DriverError(f"{watch.capitalize()} from outside the benchmark computer didn't stop within "
                                  f"{info.get('timeout_s', 0) / 60:.0f} minutes")
        else:
            raise DriverError(f"Action '{kind}' not supported")
        done = EventLog.now()
        if self.park and kind in ("click", "double_click", "right_click", "scroll", "drag"):
            self.desktop.move(*self.park)
        return done
