import json
import threading
import time
from datetime import datetime
from pathlib import Path

from .driver import EventLog


class CpuPressureLog:
    """`logs/cpu-pressure.jsonl` of a Linux session (README, "Result folder format"): once a second the CPU stall
    counters of /proc/pressure/cpu (`some` and `full` totals in µs), the container's cgroup cpu.pressure `some` total
    and /proc/loadavg, with the time (`utc`). Runs for the whole session, so every run's share can be computed
    later from the result folder alone."""

    file_name = "cpu-pressure.jsonl"

    def __init__(self, path: Path, interval_s: float = 1.0):
        self.path = Path(path)
        self.interval_s = interval_s
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    @staticmethod
    def available() -> bool:
        return Path("/proc/pressure/cpu").exists()

    @staticmethod
    def totals(path: str) -> dict:
        out = {}
        try:
            for line in Path(path).read_text().splitlines():
                kind, *fields = line.split()
                out[kind] = int(dict(f.split("=") for f in fields)["total"])
        except (OSError, ValueError, KeyError):
            pass
        return out

    @classmethod
    def sample(cls) -> dict:
        system, cgroup = cls.totals("/proc/pressure/cpu"), cls.totals("/sys/fs/cgroup/cpu.pressure")
        try:
            load = [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
        except (OSError, ValueError):
            load = None
        return {"utc": time.time(), "some_us": system.get("some"), "full_us": system.get("full"),
                "cgroup_some_us": cgroup.get("some"), "loadavg": load}

    def start(self) -> "CpuPressureLog":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        return self

    def loop(self):
        with open(self.path, "a", encoding="utf-8") as out:
            while not self.stop_event.is_set():
                started = time.monotonic()
                out.write(json.dumps(self.sample()) + "\n")
                out.flush()
                self.stop_event.wait(max(0.0, self.interval_s - (time.monotonic() - started)))

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(5)

    @staticmethod
    def read(path: Path) -> list[dict]:
        if not Path(path).exists():
            return []
        with open(path, encoding="utf-8") as f:
            samples = [json.loads(line) for line in f if line.strip()]
        return sorted((s for s in samples if s.get("utc") is not None and s.get("some_us") is not None),
                      key=lambda s: s["utc"])


class CpuPressure:
    """The CPU stall share of a run (spec v6, `env.<C>.cpu_pressure`): how much the `some` total of
    /proc/pressure/cpu grew, divided by the time, over the run's measured window (its whole run where it has none),
    from the session's cpu-pressure.jsonl; with the load average at the start and the end. Above `limit_pct`
    (`configured_limit`) a run counts as a technical failure and is recorded again."""

    def __init__(self, samples: list[dict], limit_pct: float | None):
        self.samples = samples
        self.limit_pct = limit_pct

    @staticmethod
    def configured_limit(config) -> float | None:
        """`runs.max_cpu_pressure_pct`, default 15 (the capture and software rendering alone stall 6-8 %, so only
        more means interference); null records the CPU stall without re-recording."""
        limit = config.get("runs.max_cpu_pressure_pct", 15)
        return None if limit is None else float(limit)

    @classmethod
    def for_folder(cls, folder, limit_pct: float | None) -> "CpuPressure | None":
        samples = CpuPressureLog.read(folder.logs_dir / CpuPressureLog.file_name)
        return cls(samples, limit_pct) if samples else None

    @staticmethod
    def window_utc(run_dir: Path) -> tuple[float, float, str] | None:
        analysis_path, driver_path, meta_path = (run_dir / n for n in ("analysis.json", "driver.jsonl", "meta.json"))
        window = json.loads(analysis_path.read_text()).get("measured_window") if analysis_path.exists() else None
        events = EventLog.read(driver_path) if driver_path.exists() else []
        offset = EventLog.utc_offset(events)
        if window and offset is not None:
            return window["from_t"] + offset, window["to_t"] + offset, "measured window"
        clocks = [e for e in events if e["type"] == "clock"]
        if len(clocks) >= 2:
            return clocks[0]["utc"], clocks[-1]["utc"], "whole run"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta.get("started") and meta.get("finished"):
                return (datetime.fromisoformat(meta["started"]).timestamp(),
                        datetime.fromisoformat(meta["finished"]).timestamp(), "whole run")
        return None

    def of_window(self, start: float, end: float) -> dict | None:
        before = [s for s in self.samples if s["utc"] <= start]
        after = [s for s in self.samples if s["utc"] >= end]
        if not before or not after or end <= start:
            return None
        first, last = before[-1], after[0]
        span = last["utc"] - first["utc"]
        if span <= 0 or span > (end - start) + 10:
            return None
        pct = (last["some_us"] - first["some_us"]) / 1e6 / span * 100
        cgroup = None
        if first.get("cgroup_some_us") is not None and last.get("cgroup_some_us") is not None:
            cgroup = round((last["cgroup_some_us"] - first["cgroup_some_us"]) / 1e6 / span * 100, 2)
        return {"pct": round(pct, 2), "cgroup_pct": cgroup, "from_utc": first["utc"], "to_utc": last["utc"],
                "loadavg_start": first.get("loadavg"), "loadavg_end": last.get("loadavg")}

    def of_run(self, run_dir: Path) -> dict | None:
        window = self.window_utc(Path(run_dir))
        if window is None:
            return None
        result = self.of_window(window[0], window[1])
        if result is None:
            return None
        return {"version": 1, "source": "/proc/pressure/cpu some total", "basis": window[2], **result,
                "limit_pct": self.limit_pct,
                "over_limit": self.limit_pct is not None and result["pct"] > self.limit_pct}

    def write(self, run_dir: Path) -> dict | None:
        result = self.of_run(run_dir)
        if result is not None:
            (Path(run_dir) / "cpu-pressure.json").write_text(json.dumps(result, indent=2))
        return result
