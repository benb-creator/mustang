import math
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

from .marker import MarkerCode
from .settle import Rect


class CaptureError(Exception):
    pass


class CaptureLayout:
    def __init__(self, app_region: Rect, marker: MarkerCode, position: str = "below", gap: int = 4):
        self.app_region = app_region
        self.marker = marker
        self.position = position
        self.gap = gap

    @classmethod
    def from_config(cls, config) -> "CaptureLayout":
        marker_cfg = config.get("display.marker", {}) or {}
        return cls(Rect.from_dict(config.require("display.app_region")), MarkerCode(int(marker_cfg.get("cell", 12))),
                   marker_cfg.get("position", "below"), int(marker_cfg.get("gap", 4)))

    @property
    def marker_in_capture(self) -> Rect:
        if self.position == "right":
            return Rect(self.app_region.width + self.gap, 0, self.marker.width, self.marker.height)
        return Rect(0, self.app_region.height + self.gap, self.marker.width, self.marker.height)

    @property
    def app_in_capture(self) -> Rect:
        return Rect(0, 0, self.app_region.width, self.app_region.height)

    @property
    def capture_region(self) -> Rect:
        m = self.marker_in_capture
        width = max(self.app_region.width, m.x + m.width)
        height = max(self.app_region.height, m.y + m.height)
        return Rect(self.app_region.x, self.app_region.y, width + width % 2, height + height % 2)

    @property
    def marker_screen_position(self) -> tuple[int, int]:
        m = self.marker_in_capture
        return self.app_region.x + m.x, self.app_region.y + m.y

    def to_dict(self) -> dict:
        return {"app_region": self.app_region.to_dict(), "capture_region": self.capture_region.to_dict(),
                "app_in_capture": self.app_in_capture.to_dict(), "marker_in_capture": self.marker_in_capture.to_dict(),
                "marker_cell": self.marker.cell_px}


class LiveRegion:
    """A region of the low-resolution live stream with its expected (low-resolution) content."""

    def __init__(self, rect, reference: np.ndarray | None, tolerance: float):
        self.rect = rect
        self.reference = reference
        self.tolerance = tolerance

    def crop(self, frame: np.ndarray) -> np.ndarray:
        r = self.rect
        return frame[r.y:r.y + r.height, r.x:r.x + r.width]


class LiveMonitor:
    live_pixel_threshold_match = 12

    def __init__(self, stream, width: int, height: int, pixel_threshold: int, min_changed_pixels: int):
        self.stream = stream
        self.width = width
        self.height = height
        self.pixel_threshold = pixel_threshold
        self.min_changed_pixels = min_changed_pixels
        self.arrivals: list[float] = []
        self.changes: list[int] = []
        self.latest: np.ndarray | None = None
        self.watch_regions: list[LiveRegion] = []
        self.ended = threading.Event()
        self.first_frame = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.read_loop, daemon=True)
        self.thread.start()

    def read_loop(self):
        frame_bytes = self.width * self.height
        previous = None
        try:
            while True:
                buf = self.stream.read(frame_bytes)
                if not buf or len(buf) < frame_bytes:
                    break
                now = time.perf_counter()
                frame = np.frombuffer(buf, dtype=np.uint8).reshape(self.height, self.width)
                changed = 0
                if previous is not None:
                    moved = np.abs(frame.astype(np.int16) - previous.astype(np.int16)) > self.pixel_threshold
                    changed = int(np.count_nonzero(moved))
                    with self.lock:
                        regions = list(self.watch_regions)
                    if any(region.crop(moved).any() for region in regions):
                        changed = max(changed, self.min_changed_pixels)
                with self.lock:
                    self.arrivals.append(now)
                    self.changes.append(changed)
                    self.latest = frame
                previous = frame
                self.first_frame.set()
        finally:
            self.ended.set()

    def distance(self, latest: np.ndarray, reference: np.ndarray) -> float:
        if latest.shape != reference.shape:
            return 1.0
        differing = np.count_nonzero(np.abs(latest.astype(np.int16) - reference.astype(np.int16))
                                     > self.live_pixel_threshold_match)
        return differing / max(1, latest.size)

    def matches(self, reference: np.ndarray | None, tolerance: float, regions: list[LiveRegion]) -> bool:
        with self.lock:
            latest = self.latest
        if latest is None:
            return reference is None and not regions
        if reference is not None and self.distance(latest, reference) > tolerance:
            return False
        return all(r.reference is None or self.distance(r.crop(latest), r.reference) <= r.tolerance for r in regions)

    def wait_settled(self, since: float, quiet_s: float, timeout_s: float, label: str,
                     expect_change: bool = True, reference: np.ndarray | None = None,
                     reference_tolerance: float = 0.01, regions: list[LiveRegion] | None = None,
                     no_reaction_s: float | None = None, grace_s: float | None = None,
                     complete=None, probe_interval_s: float = 1.0) -> tuple[str, dict]:
        """Returns ("settled" | "timeout" | "no-reaction", info). With a reference or regions, a quiet screen only
        counts once it matches them; after `grace_s` of stillness without a match the gate opens anyway (the
        offline analysis then decides), so a strict live match can't turn into a timeout.

        `complete` (the app probe's check) is asked only while the screen is quiet, at most every
        `probe_interval_s`; after a confirmation the screen must stay quiet for another `quiet_s`, else the
        confirmation doesn't count and the gate waits for the next quiet period."""
        regions = list(regions or [])
        confirmed_at = None
        last_probe = None
        probes = 0
        with self.lock:
            self.watch_regions = regions
        deadline = since + timeout_s
        try:
            while True:
                now = time.perf_counter()
                with self.lock:
                    start = int(np.searchsorted(np.asarray(self.arrivals), since, side="left"))
                    last_change = None
                    first_change = None
                    for t, c in zip(self.arrivals[start:], self.changes[start:]):
                        if c >= self.min_changed_pixels:
                            last_change = t
                            first_change = first_change or t
                info = {"live_end": last_change, "live_first_change": first_change, "live_quiet_s": quiet_s,
                        "live_reference": reference is not None, "live_regions": len(regions)}
                if confirmed_at is not None and (last_change is None or last_change < confirmed_at):
                    if now - confirmed_at >= quiet_s:
                        return "settled", {**info, "live_matched": True, "confirmed_at": confirmed_at,
                                           "probes": probes}
                elif confirmed_at is not None:
                    confirmed_at = None
                if complete is not None and confirmed_at is None and \
                        ((last_change is not None and now - last_change >= quiet_s) or
                         (last_change is None and not expect_change and now - since >= quiet_s)) and \
                        (last_probe is None or now - last_probe >= probe_interval_s or
                         (last_change is not None and last_probe < last_change)):
                    last_probe = time.perf_counter()
                    probes += 1
                    if complete():
                        confirmed_at = last_probe
                    continue
                if complete is None and last_change is not None and now - last_change >= quiet_s:
                    if self.matches(reference, reference_tolerance, regions):
                        return "settled", {**info, "live_matched": True}
                    if grace_s is not None and now - last_change >= grace_s:
                        return "settled", {**info, "live_matched": False}
                if complete is None and last_change is None and not expect_change and now - since >= quiet_s:
                    return "settled", {**info, "live_end": None}
                if last_change is None and expect_change and no_reaction_s is not None and now - since >= no_reaction_s:
                    return "no-reaction", info
                if self.ended.is_set():
                    raise CaptureError(f"Capture stream ended while waiting for '{label}' to settle")
                if now > deadline:
                    return "timeout", {**info, "timeout_s": timeout_s}
                time.sleep(0.02)
        finally:
            with self.lock:
                self.watch_regions = []


class FFmpegCapture:
    def __init__(self, desktop, ffmpeg: str, layout: CaptureLayout, fps: int = 60, record_path: Path | None = None,
                 live_scale: int = 4, cpus: str | None = None, draw_mouse: bool = True, log_path: Path | None = None,
                 live_pixel_threshold: int = 6, min_changed_pixels: int = 150, encoder: list[str] | None = None):
        self.desktop = desktop
        self.ffmpeg = ffmpeg
        self.layout = layout
        self.fps = fps
        self.record_path = record_path
        self.live_scale = live_scale
        self.cpus = cpus
        self.draw_mouse = draw_mouse
        self.log_path = log_path
        self.live_pixel_threshold = live_pixel_threshold
        self.live_min_changed = max(2, math.ceil(min_changed_pixels / (live_scale * live_scale)))
        self.encoder = encoder or ["-c:v", "libx264rgb", "-preset", "ultrafast", "-qp", "0"]
        self.process: subprocess.Popen | None = None
        self.live: LiveMonitor | None = None
        self.log = None

    def live_reference(self, path) -> np.ndarray | None:
        from PIL import Image
        if path is None or not path.exists():
            return None
        image = Image.open(path).convert("L")
        width, height = self.live_size
        return np.asarray(image.resize((width, height), Image.Resampling.BOX))

    def live_region(self, region) -> LiveRegion:
        """The low-resolution version of a calibrated region (`settle.Region`) and of its reference: only the live
        pixels that lie wholly inside the region, so they average exactly the pixels the reference has."""
        from PIL import Image
        s, r = self.live_scale, region.rect
        x0, y0 = -(-r.x // s), -(-r.y // s)
        x1, y1 = (r.x + r.width) // s, (r.y + r.height) // s
        if x1 <= x0 or y1 <= y0:
            x0, y0, x1, y1 = r.x // s, r.y // s, max(r.x // s + 1, x1), max(r.y // s + 1, y1)
        rect = Rect(x0, y0, x1 - x0, y1 - y0)
        reference = None
        if region.reference is not None:
            ox, oy = max(0, x0 * s - r.x), max(0, y0 * s - r.y)
            inner = region.reference[oy:oy + rect.height * s, ox:ox + rect.width * s]
            image = Image.fromarray(inner).convert("L")
            reference = np.asarray(image.resize((rect.width, rect.height), Image.Resampling.BOX))
        return LiveRegion(rect, reference, max(region.tolerance, 0.0))

    @property
    def live_size(self) -> tuple[int, int]:
        app = self.layout.app_in_capture
        return app.width // self.live_scale, app.height // self.live_scale

    def command(self) -> list[str]:
        app = self.layout.app_in_capture
        live_w, live_h = self.live_size
        prefilter = getattr(self.desktop, "capture_prefilter", lambda: "")()
        head = f"[0:v]{prefilter + ',format=bgr0,' if prefilter else ''}"
        cmd = [*self.desktop.affinity_prefix(self.cpus), self.ffmpeg, "-hide_banner", "-loglevel", "warning",
               "-nostats", *self.desktop.ffmpeg_input(self.layout.capture_region, self.fps, self.draw_mouse)]
        live_chain = (f"crop={app.width}:{app.height}:{app.x}:{app.y},scale={live_w}:{live_h}:flags=area,"
                      f"format=gray[live]")
        if self.record_path:
            cmd += ["-filter_complex", f"{head}split=2[rec][lv];[lv]{live_chain}",
                    "-map", "[rec]", *self.encoder, "-fps_mode", "passthrough", "-y", str(self.record_path)]
        else:
            cmd += ["-filter_complex", f"{head}{live_chain}"]
        cmd += ["-map", "[live]", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
        return cmd

    def start(self, first_frame_timeout_s: float = 15) -> LiveMonitor:
        self.log = open(self.log_path, "ab") if self.log_path else None
        self.process = subprocess.Popen(self.command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.log or subprocess.DEVNULL, env=getattr(self.desktop, "env", None))
        self.desktop.set_affinity(self.process, self.cpus)
        live_w, live_h = self.live_size
        self.live = LiveMonitor(self.process.stdout, live_w, live_h, self.live_pixel_threshold, self.live_min_changed)
        deadline = time.monotonic() + first_frame_timeout_s
        while not self.live.first_frame.wait(0.1):
            if self.process.poll() is not None or time.monotonic() > deadline:
                self.stop()
                log_tail = Path(self.log_path).read_text(errors="replace")[-600:] if self.log_path else ""
                raise CaptureError(f"ffmpeg delivered no frames (see {self.log_path}): {log_tail}")
        return self.live

    def stop(self, timeout_s: float = 120):
        if not self.process:
            return
        try:
            self.process.stdin.write(b"q")
            self.process.stdin.flush()
            self.process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            self.process.wait(timeout_s)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        if self.live:
            self.live.thread.join(5)
        self.process = None
        if self.log:
            self.log.close()
            self.log = None
