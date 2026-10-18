from dataclasses import dataclass, field
from typing import Callable, Iterable

import numpy as np


@dataclass
class SettleParams:
    pixel_threshold: int = 8
    min_changed_pixels: int = 150
    quiet_s: float = 1.0
    expect_change: bool = True
    reference_pixel_threshold: int = 24
    reference_tolerance: float = 0.02

    @classmethod
    def from_dict(cls, *layers: dict | None) -> "SettleParams":
        params = cls()
        for layer in layers:
            for key, value in (layer or {}).items():
                if hasattr(params, key):
                    setattr(params, key, type(getattr(params, key))(value))
        return params


@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, d: dict) -> "Rect":
        return cls(int(d["x"]), int(d["y"]), int(d["width"]), int(d["height"]))

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


class FrameDiff:
    """Counts changed pixels between consecutive RGB frames, ignoring masked rectangles."""

    def __init__(self, width: int, height: int, pixel_threshold: int, masks: Iterable[Rect] = ()):
        self.pixel_threshold = pixel_threshold
        self.keep = np.ones((height, width), dtype=bool)
        for m in masks:
            self.keep[max(0, m.y):m.y + m.height, max(0, m.x):m.x + m.width] = False

    def changed_pixels(self, prev: np.ndarray, cur: np.ndarray) -> int:
        return int(np.count_nonzero(self.changed_mask(prev, cur, self.pixel_threshold)))

    def changed_mask(self, a: np.ndarray, b: np.ndarray, threshold: int) -> np.ndarray:
        diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
        if diff.ndim == 3:
            diff = diff.max(axis=2)
        return (diff > threshold) & self.keep

    def reference_distance(self, frame: np.ndarray, reference: np.ndarray, threshold: int) -> float:
        """Fraction of unmasked pixels that differ from the reference image."""
        return float(np.count_nonzero(self.changed_mask(frame, reference, threshold))) / max(1, int(self.keep.sum()))


@dataclass
class ChangeSeries:
    """Per-frame presentation times and changed-pixel counts against the previous frame (index 0 has count 0)."""
    times: np.ndarray
    counts: np.ndarray
    reference_distances: dict = field(default_factory=dict)

    def save(self, path):
        refs = {f"ref:{name}": dist for name, dist in self.reference_distances.items()}
        np.savez_compressed(path, times=self.times, counts=self.counts, **refs)

    @classmethod
    def load(cls, path) -> "ChangeSeries":
        with np.load(path) as data:
            refs = {key[4:]: data[key] for key in data.files if key.startswith("ref:")}
            return cls(data["times"], data["counts"], refs)


@dataclass
class SettleResult:
    status: str
    start_time: float
    end_index: int | None = None
    end_time: float | None = None
    first_change_time: float | None = None
    rejected_candidates: int = 0

    @property
    def duration(self) -> float | None:
        return None if self.end_time is None else self.end_time - self.start_time

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "start_time": self.start_time,
            "end_index": self.end_index,
            "end_time": self.end_time,
            "duration_s": self.duration,
            "first_change_time": self.first_change_time,
            "rejected_candidates": self.rejected_candidates,
        }


class SettleDetector:
    """Finds the end of a step: the last significant change before a quiet period."""

    def __init__(self, params: SettleParams):
        self.params = params

    def find_end(self, series: ChangeSeries, start_time: float, window_end: float | None = None,
                 accept: Callable[[int], bool] | None = None) -> SettleResult:
        times, counts = series.times, series.counts
        if window_end is None:
            window_end = float(times[-1]) if len(times) else start_time
        window_end = min(window_end, float(times[-1])) if len(times) else window_end
        first = int(np.searchsorted(times, start_time, side="right"))
        last = int(np.searchsorted(times, window_end, side="right"))
        significant = [i for i in range(first, last) if counts[i] >= self.params.min_changed_pixels]

        if not significant:
            if self.params.expect_change:
                return SettleResult("no-change", start_time)
            if window_end - start_time < self.params.quiet_s:
                return SettleResult("unsettled", start_time)
            return SettleResult("settled", start_time, max(first - 1, 0), start_time)

        rejected = 0
        for k, index in enumerate(significant):
            next_time = float(times[significant[k + 1]]) if k + 1 < len(significant) else window_end
            if next_time - float(times[index]) < self.params.quiet_s:
                continue
            if accept is not None and not accept(index):
                rejected += 1
                continue
            return SettleResult("settled", start_time, index, float(times[index]),
                                float(times[significant[0]]), rejected)
        status = "reference-mismatch" if rejected else "unsettled"
        return SettleResult(status, start_time, None, None, float(times[significant[0]]), rejected)


class LiveSettleState:
    """Incremental settle check on a live low-resolution stream; conservative, only gates the next action."""

    def __init__(self, min_changed_pixels: int, quiet_s: float, expect_change: bool = True):
        self.min_changed_pixels = min_changed_pixels
        self.quiet_s = quiet_s
        self.expect_change = expect_change
        self.last_change_time: float | None = None
        self.since: float = 0.0

    def reset(self, since: float):
        self.since = since
        self.last_change_time = None

    def add(self, arrival_time: float, changed: int):
        if arrival_time >= self.since and changed >= self.min_changed_pixels:
            self.last_change_time = arrival_time

    def is_settled(self, now: float) -> bool:
        if self.last_change_time is None:
            return not self.expect_change and now - self.since >= self.quiet_s
        return now - self.last_change_time >= self.quiet_s
