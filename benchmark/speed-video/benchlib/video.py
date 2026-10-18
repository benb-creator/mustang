import json
import subprocess
from pathlib import Path
from typing import Iterator

import numpy as np

from .settle import Rect


class VideoError(Exception):
    pass


class VideoFile:
    def __init__(self, path: Path, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe"):
        self.path = Path(path)
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self._probe = None

    def probe(self) -> dict:
        if self._probe is None:
            out = subprocess.run(
                [self.ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(self.path)],
                check=True, capture_output=True, text=True).stdout
            self._probe = json.loads(out)
        return self._probe

    @property
    def video_stream(self) -> dict:
        for stream in self.probe()["streams"]:
            if stream.get("codec_type") == "video":
                return stream
        raise VideoError(f"No video stream in {self.path}")

    @property
    def size(self) -> tuple[int, int]:
        s = self.video_stream
        return int(s["width"]), int(s["height"])

    def frame_times(self) -> np.ndarray:
        out = subprocess.run(
            [self.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time",
             "-of", "csv=p=0", str(self.path)],
            check=True, capture_output=True, text=True).stdout
        times = np.array(sorted(float(line.split(",")[0]) for line in out.split() if line.strip()), dtype=np.float64)
        if len(times) == 0:
            raise VideoError(f"No frames in {self.path}")
        return times

    def frames(self, crop: Rect | None = None, pix_fmt: str = "rgb24") -> Iterator[np.ndarray]:
        width, height = self.size
        filters = []
        if crop:
            filters.append(f"crop={crop.width}:{crop.height}:{crop.x}:{crop.y}")
            width, height = crop.width, crop.height
        channels = {"rgb24": 3, "gray": 1}[pix_fmt]
        cmd = [self.ffmpeg, "-v", "error", "-i", str(self.path)]
        if filters:
            cmd += ["-vf", ",".join(filters)]
        cmd += ["-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", pix_fmt, "-"]
        frame_bytes = width * height * channels
        shape = (height, width, channels) if channels > 1 else (height, width)
        exhausted = False
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            try:
                while True:
                    buf = proc.stdout.read(frame_bytes)
                    if len(buf) < frame_bytes:
                        exhausted = True
                        break
                    yield np.frombuffer(buf, dtype=np.uint8).reshape(shape)
            finally:
                if not exhausted:
                    proc.kill()
                proc.stdout.close()
                errors = proc.stderr.read().decode(errors="replace")
                proc.wait()
        if exhausted and proc.returncode != 0:
            raise VideoError(f"ffmpeg failed reading {self.path} (exit {proc.returncode}): {errors[-500:]}")

    def frame_at_index(self, index: int, crop: Rect | None = None) -> np.ndarray:
        for i, frame in enumerate(self.frames(crop)):
            if i == index:
                return frame.copy()
        raise VideoError(f"Frame {index} not found in {self.path}")
