from collections import deque
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
    fade_lag_frames: int = 6
    max_gap_frames: float = 3.0
    no_reaction_s: float = 60.0
    roi_grace_s: float = 20.0
    reference_quiet_s: float = 4.0

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

    def crop(self, image: np.ndarray) -> np.ndarray:
        return image[max(0, self.y):self.y + self.height, max(0, self.x):self.x + self.width]

    def scaled(self, factor: int) -> "Rect":
        return Rect(self.x // factor, self.y // factor, max(1, self.width // factor), max(1, self.height // factor))


@dataclass
class Region:
    """A region of interest of a step: a calibrated rectangle and, once calibrated, its expected content."""
    name: str
    rect: Rect
    reference: np.ndarray | None = None
    tolerance: float = 0.0
    pixel_threshold: int = 24

    def distance(self, frame: np.ndarray) -> float:
        if self.reference is None:
            return 1.0
        crop = self.rect.crop(frame)
        if crop.shape != self.reference.shape:
            return 1.0
        diff = np.abs(crop.astype(np.int16) - self.reference.astype(np.int16))
        if diff.ndim == 3:
            diff = diff.max(axis=2)
        return float(np.count_nonzero(diff > self.pixel_threshold)) / max(1, diff.size)

    def matches(self, frame: np.ndarray) -> bool:
        return self.distance(frame) <= self.tolerance


class FrameDiff:
    """Counts changed pixels between RGB frames, ignoring masked rectangles."""

    def __init__(self, width: int, height: int, pixel_threshold: int, masks: Iterable[Rect] = ()):
        self.pixel_threshold = pixel_threshold
        self.keep = np.ones((height, width), dtype=bool)
        for m in masks:
            self.keep[max(0, m.y):m.y + m.height, max(0, m.x):m.x + m.width] = False

    def changed_pixels(self, prev: np.ndarray, cur: np.ndarray, threshold: int | None = None) -> int:
        return int(np.count_nonzero(self.changed_mask(prev, cur, self.pixel_threshold if threshold is None
                                                      else threshold)))

    @staticmethod
    def absdiff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Largest channel difference per pixel, computed in uint8 (no widening copy)."""
        diff = np.maximum(a, b)
        diff -= np.minimum(a, b)
        if diff.ndim != 3:
            return diff
        largest = np.maximum(diff[:, :, 0], diff[:, :, 1])
        return np.maximum(largest, diff[:, :, 2], out=largest)

    def count(self, diff: np.ndarray, threshold: int) -> int:
        return int(np.count_nonzero(diff[self.keep] > threshold if not self.keep.all() else diff > threshold))

    def changed_counts(self, prev: np.ndarray, cur: np.ndarray, thresholds: tuple[int, ...]) -> list[int]:
        diff = np.abs(prev.astype(np.int16) - cur.astype(np.int16))
        if diff.ndim == 3:
            diff = diff.max(axis=2)
        diff = diff[self.keep] if not self.keep.all() else diff
        return [int(np.count_nonzero(diff > t)) for t in thresholds]

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
    """Per-frame presentation times and change measures; index 0 has no previous frame (all counts 0).

    counts: changed pixels against the previous frame; fine_counts: the same with threshold 0 (anything changed);
    lag_counts: changed pixels against the frame `fade_lag_frames` earlier (finds slow fades); region_changes: per
    region, changed pixels against the previous frame; reference_distances / region_distances: per frame, the
    fraction of pixels that differ from a step's full-frame reference / a region's reference."""
    times: np.ndarray
    counts: np.ndarray
    reference_distances: dict = field(default_factory=dict)
    fine_counts: np.ndarray | None = None
    lag_counts: np.ndarray | None = None
    region_changes: dict = field(default_factory=dict)
    region_distances: dict = field(default_factory=dict)

    def save(self, path):
        arrays = {"times": self.times, "counts": self.counts}
        if self.fine_counts is not None:
            arrays["fine_counts"] = self.fine_counts
        if self.lag_counts is not None:
            arrays["lag_counts"] = self.lag_counts
        arrays.update({f"ref:{name}": dist for name, dist in self.reference_distances.items()})
        arrays.update({f"roi-change:{name}": c for name, c in self.region_changes.items()})
        arrays.update({f"roi-ref:{name}": d for name, d in self.region_distances.items()})
        np.savez_compressed(path, **arrays)

    @classmethod
    def load(cls, path) -> "ChangeSeries":
        with np.load(path) as data:
            def prefixed(prefix):
                return {key[len(prefix):]: data[key] for key in data.files if key.startswith(prefix)}
            return cls(data["times"], data["counts"], prefixed("ref:"),
                       data["fine_counts"] if "fine_counts" in data.files else None,
                       data["lag_counts"] if "lag_counts" in data.files else None,
                       prefixed("roi-change:"), prefixed("roi-ref:"))

    def significant(self, params: SettleParams, regions: Iterable[str] = ()) -> np.ndarray:
        mask = self.counts >= params.min_changed_pixels
        if self.lag_counts is not None and self.fine_counts is not None:
            mask |= (self.lag_counts >= params.min_changed_pixels) & (self.fine_counts >= params.min_changed_pixels)
        for name in regions:
            if name in self.region_changes:
                mask |= self.region_changes[name] > 0
        return mask


class MovingMasks:
    """Masks over content that changes by itself while the run goes on (Parula's setup video): the driver's `mask`
    lines, each a set of rectangles (app-capture pixels) that the probe saw at `t`, while the poll before (`since_t`)
    still saw the previous set. Per frame the analysis counts the changed pixels inside each distinct set
    (`measure`, through a grid of cells cut by all rectangle edges); `schedule` decides which set applies to each
    frame: the previous one stays until the first frame after `since_t` that changes outside it (the layout change
    itself, still counted), the new one from the frame after that, or from `latency_s` after `t` at the latest."""

    def __init__(self, changes: list[dict], width: int, height: int):
        self.width, self.height = width, height
        self.sets: list[tuple] = [()]
        self.changes = []
        for change in sorted(changes, key=lambda c: c["t"]):
            rects = []
            for r in change["rects"]:
                x0, y0 = max(0, r.x), max(0, r.y)
                x1, y1 = min(width, r.x + r.width), min(height, r.y + r.height)
                if x1 > x0 and y1 > y0:
                    rects.append((x0, y0, x1, y1))
            key = tuple(sorted(rects))
            if key not in self.sets:
                self.sets.append(key)
            self.changes.append({"t": change["t"], "since_t": change.get("since_t"), "set": self.sets.index(key)})
        self.xs = sorted({0, width} | {v for key in self.sets for r in key for v in (r[0], r[2])})
        self.ys = sorted({0, height} | {v for key in self.sets for r in key for v in (r[1], r[3])})
        self.blocks = [[(self.ys.index(y0), self.ys.index(y1), self.xs.index(x0), self.xs.index(x1))
                        for x0, y0, x1, y1 in key] for key in self.sets]

    def measure(self, changed: np.ndarray) -> tuple[int, np.ndarray]:
        """All changed pixels of a frame, and those inside each distinct set."""
        cells = np.add.reduceat(np.add.reduceat(changed, self.ys[:-1], axis=0, dtype=np.int64), self.xs[:-1],
                                axis=1)
        inside = np.array([sum(int(cells[a:b, c:d].sum()) for a, b, c, d in blocks) for blocks in self.blocks],
                          dtype=np.int64)
        return int(cells.sum()), inside

    def schedule(self, times: np.ndarray, totals: np.ndarray, inside: np.ndarray, to_video, min_changed: int,
                 latency_s: float = 0.1) -> np.ndarray:
        index = np.zeros(len(times), dtype=np.int64)
        current, start = 0, 0
        for change in self.changes:
            new = change["set"]
            if new == current:
                continue
            seen = to_video(change["t"])
            opened = to_video(change["since_t"]) if change["since_t"] is not None else seen
            first = max(start, int(np.searchsorted(times, opened, side="left")))
            last = max(first, int(np.searchsorted(times, seen + latency_s, side="right")))
            outside_old = totals[first:last] - inside[first:last, current]
            hits = np.flatnonzero(outside_old >= min_changed)
            switch = first + int(hits[0]) + 1 if len(hits) else last
            index[start:switch] = current
            current, start = new, switch
        index[start:] = current
        return index

    def summary(self, times: np.ndarray, index: np.ndarray) -> dict:
        switches = np.flatnonzero(np.diff(index)) + 1
        return {"sets": [[{"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0} for x0, y0, x1, y1 in key]
                         for key in self.sets],
                "changes": len(self.changes),
                "applied": [{"time": float(times[i]), "set": int(index[i])} for i in ([0] if len(index) else [])]
                + [{"time": float(times[i]), "set": int(index[i])} for i in switches]}


class FrameAnalyzer:
    """Builds a ChangeSeries from a sequence of frames (the app area, RGB). With `moving` (MovingMasks), the change
    counts inside each of its sets are kept per frame and `series(..., to_video)` applies its schedule."""

    def __init__(self, width: int, height: int, params: SettleParams, masks: Iterable[Rect] = (),
                 references: dict | None = None, regions: Iterable[Region] = (), reference_thresholds: dict | None = None,
                 moving: MovingMasks | None = None):
        self.params = params
        self.diff = FrameDiff(width, height, params.pixel_threshold, masks)
        self.references = dict(references or {})
        self.reference_thresholds = dict(reference_thresholds or {})
        self.regions = {r.name: r for r in regions}
        self.moving = moving
        self.history: deque = deque(maxlen=max(1, params.fade_lag_frames))
        self.times, self.counts, self.fine, self.lag = [], [], [], []
        self.inside: dict[str, list] = {"counts": [], "fine": [], "lag": []}
        self.ref_distances = {name: [] for name in self.references}
        self.region_changes = {name: [] for name in self.regions}
        self.region_distances = {name: [] for name, r in self.regions.items() if r.reference is not None}
        self.schedule_summary: dict | None = None

    def moving_counts(self, diff: np.ndarray, threshold: int) -> tuple[int, np.ndarray]:
        changed = diff > threshold
        if not self.diff.keep.all():
            changed &= self.diff.keep
        return self.moving.measure(changed)

    def add(self, time: float, frame: np.ndarray):
        previous = self.history[-1] if self.history else None
        oldest = self.history[0] if len(self.history) == self.history.maxlen else None
        self.times.append(time)
        diff = None if previous is None else self.diff.absdiff(previous, frame)
        minimum = self.params.min_changed_pixels
        if self.moving is not None:
            self.add_moving(frame, diff, oldest, minimum)
        else:
            count = fine = lag = 0
            if diff is not None:
                count, fine = self.diff.count(diff, self.params.pixel_threshold), self.diff.count(diff, 0)
            if oldest is not None and fine >= minimum and count < minimum:
                lag = self.diff.count(self.diff.absdiff(oldest, frame), self.params.pixel_threshold)
            self.counts.append(count)
            self.fine.append(fine)
            self.lag.append(lag)
        self.add_checks(frame, diff)

    def add_moving(self, frame: np.ndarray, diff: np.ndarray | None, oldest, minimum: int):
        empty = np.zeros(len(self.moving.sets), dtype=np.int64)
        count, inside_count, fine, inside_fine, lag, inside_lag = 0, empty, 0, empty, 0, empty
        if diff is not None:
            count, inside_count = self.moving_counts(diff, self.params.pixel_threshold)
            fine, inside_fine = self.moving_counts(diff, 0)
            if oldest is not None and fine >= minimum and int((count - inside_count).min()) < minimum:
                lag, inside_lag = self.moving_counts(self.diff.absdiff(oldest, frame), self.params.pixel_threshold)
        self.counts.append(count)
        self.fine.append(fine)
        self.lag.append(lag)
        self.inside["counts"].append(inside_count)
        self.inside["fine"].append(inside_fine)
        self.inside["lag"].append(inside_lag)

    def add_checks(self, frame: np.ndarray, diff: np.ndarray | None):
        for name, reference in self.references.items():
            threshold = self.reference_thresholds.get(name, self.params.reference_pixel_threshold)
            self.ref_distances[name].append(self.diff.reference_distance(frame, reference, threshold)
                                            if reference.shape == frame.shape else 1.0)
        for name, region in self.regions.items():
            changed = 0 if diff is None else int(np.count_nonzero(region.rect.crop(diff) > self.params.pixel_threshold))
            self.region_changes[name].append(changed)
            if name in self.region_distances:
                self.region_distances[name].append(region.distance(frame))
        self.history.append(frame)

    def series(self, times: np.ndarray | None = None, to_video=None) -> ChangeSeries:
        """`to_video` maps the driver's clock onto the video's (needed with `moving`)."""
        as_float = lambda values: np.asarray(values, dtype=np.float32)
        times = np.asarray(self.times if times is None else times, dtype=np.float64)
        counts = np.asarray(self.counts, dtype=np.int64)
        fine = np.asarray(self.fine, dtype=np.int64)
        lag = np.asarray(self.lag, dtype=np.int64)
        if self.moving is not None:
            inside = {name: np.asarray(values, dtype=np.int64).reshape(len(values), len(self.moving.sets))
                      for name, values in self.inside.items()}
            index = self.moving.schedule(times, counts, inside["counts"], to_video, self.params.min_changed_pixels)
            frames = np.arange(len(index))
            counts = counts - inside["counts"][frames, index]
            fine = fine - inside["fine"][frames, index]
            lag = lag - inside["lag"][frames, index]
            self.schedule_summary = self.moving.summary(times, index)
        return ChangeSeries(times, counts,
                            {k: as_float(v) for k, v in self.ref_distances.items()},
                            fine, lag,
                            {k: np.asarray(v, dtype=np.int64) for k, v in self.region_changes.items()},
                            {k: as_float(v) for k, v in self.region_distances.items()})


@dataclass
class SettleResult:
    status: str
    start_time: float
    end_index: int | None = None
    end_time: float | None = None
    first_change_time: float | None = None
    rejected_candidates: int = 0
    late_changes: int = 0
    last_late_change_time: float | None = None
    end_uncertainty_s: float | None = None

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
            "late_changes": self.late_changes,
            "last_late_change_time": self.last_late_change_time,
            "end_uncertainty_s": self.end_uncertainty_s,
        }


class SettleDetector:
    """Finds the end of a step: the last significant change before a quiet period (that the `accept` check takes)."""

    def __init__(self, params: SettleParams, regions: Iterable[str] = ()):
        self.params = params
        self.regions = list(regions)

    def find_end(self, series: ChangeSeries, start_time: float, window_end: float | None = None,
                 accept: Callable[[int], bool] | None = None, late_margin_s: float = 0.0) -> SettleResult:
        """late_margin_s: changes this close to the window's end belong to the next action (a frame can show
        content grabbed just after its timestamp), not to the step."""
        times = series.times
        if window_end is None:
            window_end = float(times[-1]) if len(times) else start_time
        window_end = min(window_end, float(times[-1])) if len(times) else window_end
        first = int(np.searchsorted(times, start_time, side="right"))
        last = int(np.searchsorted(times, window_end, side="right"))
        mask = series.significant(self.params, self.regions)
        significant = [i for i in range(first, last) if mask[i]]

        if not significant:
            if self.params.expect_change:
                return SettleResult("no-change", start_time)
            if window_end - start_time < self.params.quiet_s:
                return SettleResult("unsettled", start_time)
            index = max(first - 1, 0)
            if accept is not None and not accept(index):
                return SettleResult("reference-mismatch", start_time, rejected_candidates=1)
            return SettleResult("settled", start_time, index, start_time)

        rejected = 0
        for k, index in enumerate(significant):
            next_time = float(times[significant[k + 1]]) if k + 1 < len(significant) else window_end
            if next_time - float(times[index]) < self.params.quiet_s:
                continue
            if accept is not None and not accept(index):
                rejected += 1
                continue
            late = [i for i in significant[k + 1:] if float(times[i]) < window_end - late_margin_s]
            uncertainty = float(times[index] - times[index - 1]) if index > 0 else None
            return SettleResult("settled", start_time, index, float(times[index]), float(times[significant[0]]),
                                rejected, len(late), float(times[late[-1]]) if late else None, uncertainty)
        status = "reference-mismatch" if rejected else "unsettled"
        return SettleResult(status, start_time, None, None, float(times[significant[0]]), rejected)

    def first_match(self, series: ChangeSeries, start_time: float, end_time: float,
                    accept: Callable[[int], bool]) -> float | None:
        """Time of the first frame in [start_time, end_time] that the check accepts."""
        times = series.times
        first = int(np.searchsorted(times, start_time, side="right"))
        last = int(np.searchsorted(times, end_time, side="right"))
        for i in range(first, last):
            if accept(i):
                return float(times[i])
        return None


class CompletionGate:
    """Accepts a candidate end (a significant change followed by a quiet period) only if the app's completeness
    confirmation (`gate`, video time) falls into that quiet period: the screen showed the final state then. The
    state the probe read reaches the recording a few frames later (paint, capture), hence `latency_s`."""

    def __init__(self, series: ChangeSeries, params: SettleParams, regions: Iterable[str], gate: float,
                 latency_s: float = 0.1):
        self.times = series.times
        self.frames = np.flatnonzero(series.significant(params, regions))
        self.gate = gate + latency_s

    def accept(self, index: int) -> bool:
        following = self.frames[np.searchsorted(self.frames, index, side="right"):]
        next_change = float(self.times[following[0]]) if len(following) else float("inf")
        return float(self.times[index]) <= self.gate < next_change


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
