"""Content that changes by itself (Parula's setup video): the probe's rectangles, the driver's polling, the live
gate's mask and the offline schedule of masks."""

import io
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchlib.capture import LiveMonitor  # noqa: E402
from benchlib.driver import MovingAreaWatcher  # noqa: E402
from benchlib.probe import Bands, ParulaProbe  # noqa: E402
from benchlib.settle import FrameAnalyzer, MovingMasks, Rect, SettleParams  # noqa: E402


class FixedPage(ParulaProbe):
    def __init__(self, answers: list, app=None):
        super().__init__(0)
        self.answers = answers
        self.app = app

    def evaluate(self, expression: str):
        return self.answers.pop(0)


def video_page(box, d=1.0, sx=0, sy=0):
    return {"video": {"x": 0, "y": 0, "w": 100, "h": 80}, "box": box,
            "viewport": {"x": 0, "y": 0, "w": 100, "h": 80}, "view": {"d": d, "sx": sx, "sy": sy}}


def test_bands_around_a_hole_cover_the_rest():
    outer = {"x": 0, "y": 0, "w": 100, "h": 80}
    bands = Bands.around(outer, {"x": 42, "y": 32, "w": 16, "h": 6})
    assert bands == [{"x": 0, "y": 0, "w": 100, "h": 32}, {"x": 0, "y": 38, "w": 100, "h": 42},
                     {"x": 0, "y": 32, "w": 42, "h": 6}, {"x": 58, "y": 32, "w": 42, "h": 6}]
    assert sum(b["w"] * b["h"] for b in bands) == 100 * 80 - 16 * 6
    assert Bands.around(outer, None) == [outer]
    assert Bands.around(outer, {"x": 200, "y": 0, "w": 10, "h": 10}) == [outer]


def test_parula_video_area_is_the_video_minus_the_dialog():
    probe = FixedPage([video_page({"x": 30, "y": 20, "w": 40, "h": 30}), video_page(None), None, video_page(None)])
    first = probe.moving_areas()
    assert first[0] == {"x": 0, "y": 0, "w": 100, "h": 32} and len(first) == 4
    assert probe.moving_areas() == first
    assert probe.moving_areas() is None
    assert probe.moving_areas() == [{"x": 0, "y": 0, "w": 100, "h": 80}]


def test_parula_rectangles_use_the_window_systems_client_origin_when_it_has_one():
    class WindowsApp:
        @staticmethod
        def client_origin():
            return 1000, 500

    probe = FixedPage([video_page(None, d=1.25, sx=7, sy=9)], WindowsApp())
    assert probe.moving_areas() == [{"x": 1000, "y": 500, "w": 125, "h": 100}]
    linux = FixedPage([video_page(None, d=1.0, sx=7, sy=9)])
    assert linux.moving_areas() == [{"x": 7, "y": 9, "w": 100, "h": 80}]


class MemoryLog:
    def __init__(self):
        self.lines = []

    def write(self, type, t=None, **fields):
        t = time.perf_counter() if t is None else t
        self.lines.append({"type": type, "t": t, **fields})
        return t


def test_watcher_logs_each_change_with_the_poll_before_and_stops_when_the_video_is_gone():
    first = [{"x": 0, "y": 0, "w": 10, "h": 10}]
    second = [{"x": 0, "y": 0, "w": 20, "h": 10}]

    class Probe:
        shows_moving_content = True
        answers = [first, first, second, second, None, first]

        def moving_areas(self):
            return self.answers.pop(0) if self.answers else None

    class Live:
        masks = []

        def set_masks(self, rects):
            self.masks.append(rects)

    log = MemoryLog()
    live = Live()
    watcher = MovingAreaWatcher(Probe(), log, hz=200).start()
    watcher.show_to(live)
    watcher.thread.join(5)
    masks = [line for line in log.lines if line["type"] == "mask"]
    assert [m["rects"] for m in masks] == [first, second, []]
    assert masks[0]["since_t"] is None and masks[1]["since_t"] < masks[1]["t"]
    assert log.lines[-1]["type"] == "mask_end"
    assert live.masks[-1] == []


def test_live_gate_mask_leaves_out_every_low_resolution_pixel_a_rectangle_touches():
    monitor = LiveMonitor(io.BytesIO(b""), 16, 12, 6, 2, origin=(100, 50), scale=4)
    monitor.set_masks([{"x": 101, "y": 50, "w": 5, "h": 8}])
    assert not monitor.keep[0:2, 0:2].any() and monitor.keep[:, 2:].all() and monitor.keep[2:, :].all()
    monitor.set_masks([])
    assert monitor.keep is None


def frames_with_a_shrinking_dialog(count=60, switch=30, size=(64, 48)):
    """Noise everywhere outside the dialog; the dialog shrinks at frame `switch` (the area it frees shows noise)."""
    rng = np.random.default_rng(7)
    width, height = size
    big, small = (20, 10, 44, 38), (26, 16, 38, 32)
    frames = []
    for i in range(count):
        frame = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)
        x0, y0, x1, y1 = big if i < switch else small
        frame[y0:y1, x0:x1] = 200 if i < switch else 90
        frames.append(frame)
    return frames, big, small


def bands(box, size=(64, 48)):
    x0, y0, x1, y1 = box
    return [Rect(r["x"], r["y"], r["w"], r["h"]) for r in Bands.around(
        {"x": 0, "y": 0, "w": size[0], "h": size[1]}, {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0})]


def series_for(changes, frames):
    params = SettleParams(min_changed_pixels=10)
    analyzer = FrameAnalyzer(64, 48, params, moving=MovingMasks(changes, 64, 48))
    for frame in frames:
        analyzer.add(0.0, frame)
    times = np.arange(len(frames)) / 60
    return analyzer, analyzer.series(times, lambda t: t)


def test_the_old_mask_stays_until_the_layout_change_and_the_new_one_from_the_frame_after():
    frames, big, small = frames_with_a_shrinking_dialog()
    changes = [{"t": -1.0, "since_t": None, "rects": bands(big)},
               {"t": 33 / 60, "since_t": 27 / 60, "rects": bands(small)}]
    analyzer, series = series_for(changes, frames)
    assert not series.counts[1:30].any()
    assert series.counts[30] > 10
    assert not series.counts[31:].any()
    assert [a["set"] for a in analyzer.schedule_summary["applied"]] == [1, 2]
    assert analyzer.schedule_summary["applied"][1]["time"] == 31 / 60


def test_without_a_change_under_the_old_mask_the_new_one_applies_shortly_after_the_poll_saw_it():
    frames, big, small = frames_with_a_shrinking_dialog(switch=1000)
    changes = [{"t": -1.0, "since_t": None, "rects": bands(big)},
               {"t": 33 / 60, "since_t": 27 / 60, "rects": bands(small)}]
    analyzer, series = series_for(changes, frames)
    first_new = analyzer.schedule_summary["applied"][1]["time"]
    assert 33 / 60 + 0.1 < first_new <= 33 / 60 + 0.1 + 1 / 60
    assert series.counts[:int(first_new * 60)].max() == 0


def test_without_masks_the_noise_counts():
    frames, _, _ = frames_with_a_shrinking_dialog()
    params = SettleParams(min_changed_pixels=10)
    analyzer = FrameAnalyzer(64, 48, params)
    for frame in frames:
        analyzer.add(0.0, frame)
    assert (analyzer.series(np.arange(len(frames)) / 60).counts[1:] > 10).all()
