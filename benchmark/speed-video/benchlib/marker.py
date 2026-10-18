from dataclasses import dataclass

import numpy as np


class MarkerCode:
    """Sync marker strip: a white and a black guard cell, 12 data bits (MSB first), one even-parity cell."""

    data_bits = 12
    cell_count = 2 + data_bits + 1

    def __init__(self, cell_px: int):
        self.cell_px = cell_px

    @property
    def width(self) -> int:
        return self.cell_px * self.cell_count

    @property
    def height(self) -> int:
        return self.cell_px

    def cells(self, code: int) -> list[bool]:
        if not 0 <= code < 2 ** self.data_bits:
            raise ValueError(f"Marker code {code} out of range")
        bits = [bool(code >> (self.data_bits - 1 - i) & 1) for i in range(self.data_bits)]
        return [True, False] + bits + [sum(bits) % 2 == 1]

    def decode(self, strip: np.ndarray) -> int | None:
        """`strip` is the gray (H, W) or RGB (H, W, 3) image of the marker area; returns None unless clean."""
        if strip.ndim == 3:
            strip = strip.mean(axis=2)
        inset = max(1, self.cell_px // 4)
        values = []
        for i in range(self.cell_count):
            x0 = i * self.cell_px + inset
            cell = strip[inset:self.cell_px - inset, x0:x0 + self.cell_px - 2 * inset]
            if cell.size == 0:
                return None
            values.append(float(cell.mean()))
        low, high = 60, 195
        if values[0] < high or values[1] > low:
            return None
        if any(low < v < high for v in values):
            return None
        bits = [v >= high for v in values[2:2 + self.data_bits]]
        if (sum(bits) % 2 == 1) != (values[-1] >= high):
            return None
        code = 0
        for bit in bits:
            code = code << 1 | int(bit)
        return code

    def render(self, code: int) -> np.ndarray:
        image = np.zeros((self.cell_px, self.width), dtype=np.uint8)
        for i, white in enumerate(self.cells(code)):
            if white:
                image[:, i * self.cell_px:(i + 1) * self.cell_px] = 255
        return image


class MarkerTrack:
    """First video frame time at which each marker code appears."""

    def __init__(self):
        self.first_seen: dict[int, float] = {}
        self.current: int | None = None

    def add(self, time: float, code: int | None):
        if code is None or code == self.current:
            return
        self.current = code
        self.first_seen.setdefault(code, time)


class ClockFitError(Exception):
    pass


@dataclass
class ClockFit:
    """video_time = slope * driver_time + offset."""
    slope: float
    offset: float
    residuals: list
    points: int
    rejected_codes: list

    def to_video(self, driver_time: float) -> float:
        return self.slope * driver_time + self.offset

    def to_driver(self, video_time: float) -> float:
        return (video_time - self.offset) / self.slope

    @property
    def max_abs_residual(self) -> float:
        return max((abs(r) for r in self.residuals), default=0.0)

    def to_dict(self) -> dict:
        return {
            "slope": self.slope,
            "offset": self.offset,
            "points": self.points,
            "max_abs_residual_s": self.max_abs_residual,
            "residuals_s": self.residuals,
            "rejected_codes": self.rejected_codes,
        }

    @classmethod
    def fit(cls, driver_times: dict[int, float], video_times: dict[int, float],
            frame_interval: float, min_points: int = 4, max_residual_frames: float = 1.5,
            max_slope_error: float = 0.005) -> "ClockFit":
        codes = sorted(set(driver_times) & set(video_times))
        rejected = sorted(set(driver_times) - set(video_times))
        if len(codes) < min_points:
            raise ClockFitError(f"Only {len(codes)} sync markers found in the video (need {min_points}); "
                                f"missing codes {rejected}")
        while True:
            x = np.array([driver_times[c] for c in codes], dtype=np.float64)
            y = np.array([video_times[c] for c in codes], dtype=np.float64)
            x0 = x.mean()
            slope, offset0 = np.polyfit(x - x0, y, 1)
            offset = offset0 - slope * x0
            residuals = y - (slope * x + offset)
            worst = int(np.argmax(np.abs(residuals)))
            if abs(residuals[worst]) <= max_residual_frames * frame_interval:
                if abs(slope - 1.0) > max_slope_error:
                    raise ClockFitError(f"Sync markers give a clock rate of {slope:.6f}, expected 1")
                return cls(float(slope), float(offset), [float(r) for r in residuals], len(codes), rejected)
            if len(codes) - 1 < min_points:
                raise ClockFitError(f"Sync markers don't fit a line: worst residual "
                                    f"{residuals[worst] * 1000:.1f} ms at code {codes[worst]}")
            rejected.append(codes.pop(worst))
