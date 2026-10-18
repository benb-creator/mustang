import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path


class OutputVerifier:
    expected = {
        "webm": {"video": "vp9", "audio": "opus"},
        "mp4": {"video": "h264", "audio": "aac"},
        "youtube": {"video": "h264", "audio": "aac"},
    }

    def __init__(self, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe", fps: int = 60, loudness: float = -14,
                 true_peak: float = -1):
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.fps = fps
        self.loudness = loudness
        self.true_peak = true_peak

    def probe(self, path: Path) -> dict:
        out = subprocess.run([self.ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format",
                              str(path)], capture_output=True, text=True, check=True).stdout
        return json.loads(out)

    def faststart(self, path: Path) -> bool:
        with open(path, "rb") as f:
            while True:
                header = f.read(8)
                if len(header) < 8:
                    return False
                size = int.from_bytes(header[:4], "big")
                kind = header[4:8]
                if kind == b"moov":
                    return True
                if kind == b"mdat":
                    return False
                if size == 1:
                    size = int.from_bytes(f.read(8), "big")
                    f.seek(size - 16, 1)
                else:
                    f.seek(size - 8, 1)

    def loudness_of(self, path: Path) -> dict:
        log = subprocess.run([self.ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a",
                              "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
        summary = log[log.rfind("Summary:"):]
        integrated = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
        peak = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
        return {"integrated_lufs": float(integrated.group(1)) if integrated else None,
                "true_peak_dbtp": float(peak.group(1)) if peak and peak.group(1) != "-inf" else None}

    def check(self, kind: str, path: Path, reference_duration: float | None, expect_audio: bool,
              expected_height: int | None = None) -> dict:
        info = self.probe(path)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        checks = {
            "video_codec": (video["codec_name"], self.expected[kind]["video"]),
            "pix_fmt": (video.get("pix_fmt"), "yuv420p"),
            "fps": (float(Fraction(video["avg_frame_rate"])), float(self.fps)),
            "color_space": (video.get("color_space"), "bt709"),
            "color_transfer": (video.get("color_transfer"), "bt709"),
            "color_primaries": (video.get("color_primaries"), "bt709"),
            "color_range": (video.get("color_range"), "tv"),
        }
        if expected_height:
            checks["height"] = (int(video["height"]), expected_height)
        if expect_audio:
            checks["audio_codec"] = (audio["codec_name"] if audio else None, self.expected[kind]["audio"])
        report = {"file": str(path), "size_bytes": Path(path).stat().st_size, "checks": {}, "ok": True}
        for name, (actual, wanted) in checks.items():
            ok = abs(actual - wanted) < 0.01 if isinstance(wanted, float) else actual == wanted
            report["checks"][name] = {"actual": actual, "expected": wanted, "ok": ok}
        duration = float(info["format"]["duration"])
        if reference_duration is not None:
            ok = abs(duration - reference_duration) <= 0.1
            report["checks"]["duration"] = {"actual": duration, "expected": reference_duration, "ok": ok}
        if kind in ("mp4", "youtube"):
            report["checks"]["faststart"] = {"actual": self.faststart(path), "expected": True,
                                             "ok": self.faststart(path)}
        if expect_audio and audio:
            loud = self.loudness_of(path)
            report["checks"]["loudness"] = {"actual": loud["integrated_lufs"], "expected": self.loudness,
                                            "ok": loud["integrated_lufs"] is not None and
                                            abs(loud["integrated_lufs"] - self.loudness) <= 1.0}
            report["checks"]["true_peak"] = {"actual": loud["true_peak_dbtp"], "expected": f"<= {self.true_peak + 0.5}",
                                             "ok": loud["true_peak_dbtp"] is None or
                                             loud["true_peak_dbtp"] <= self.true_peak + 0.5}
        report["ok"] = all(c["ok"] for c in report["checks"].values())
        return report
