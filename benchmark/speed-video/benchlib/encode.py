import json
import re
import subprocess
from pathlib import Path


class EncodeError(Exception):
    pass


class Encoder:
    color_tags = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]

    def __init__(self, config, master: Path, audio: Path | None, out_dir: Path, name: str, progress=print,
                 watermark: str | None = None):
        self.config = config
        self.master = Path(master)
        self.audio = Path(audio) if audio else None
        self.out_dir = Path(out_dir)
        self.name = name
        self.progress = progress
        self.ffmpeg = config.tool("ffmpeg")
        encode = config.get("encode") or {}
        self.loudness = float(encode.get("loudness_lufs", -14))
        self.true_peak = float(encode.get("true_peak_db", -1))
        self.webm_crf = int(encode.get("webm_crf", 30))
        self.mp4_crf = int(encode.get("mp4_crf", 18))
        self.youtube_crf = int(encode.get("youtube_crf", 12))
        self.youtube_height = int(encode.get("youtube_height", 2160))
        self.threads = encode.get("threads")
        self.watermark = watermark
        compose = config.get("compose") or {}
        self.font = compose.get("font_bold")

    def run(self, args: list[str]) -> str:
        result = subprocess.run([self.ffmpeg, "-hide_banner", "-y", *args], capture_output=True, text=True)
        if result.returncode != 0:
            raise EncodeError(f"ffmpeg failed: {result.stderr[-2500:]}")
        return result.stderr

    def video_filter(self, height: int | None = None) -> str:
        scale = f"scale=-2:{height}:flags=lanczos+accurate_rnd+full_chroma_int," if height else ""
        if self.watermark:
            from .cards import Fonts
            font = (self.font or Fonts.default(True)).replace("\\", "/").replace(":", "\\:")
            text = self.watermark.replace("'", "").replace(":", "\\:")
            scale = (f"drawtext=fontfile='{font}':text='{text}':fontsize=h/18:fontcolor=white@0.85:box=1:"
                     f"boxcolor=0xB00020@0.8:boxborderw=20:x=(w-tw)/2:y=(h-th)/2,") + scale
        return (f"{scale}scale=in_range=pc:out_range=tv:out_color_matrix=bt709:"
                f"flags=accurate_rnd+full_chroma_int,format=yuv420p,setparams=range=tv:colorspace=bt709:"
                f"color_primaries=bt709:color_trc=bt709")

    def thread_args(self) -> list[str]:
        return ["-threads", str(self.threads)] if self.threads else []

    def normalized_audio(self) -> Path | None:
        if not self.audio:
            return None
        target = f"I={self.loudness}:TP={self.true_peak}:LRA=11"
        log = self.run(["-i", str(self.audio), "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"])
        m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", log, re.S)
        if not m:
            raise EncodeError("loudnorm measurement failed")
        measured = json.loads(m.group(0))
        if float(measured["input_i"]) < -70:
            return None
        second = (f"loudnorm={target}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
                  f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
                  f"offset={measured['target_offset']}:linear=true")
        out = self.out_dir / f"{self.name}-audio-normalized.wav"
        self.run(["-i", str(self.audio), "-af", f"{second},aresample=48000", "-c:a", "pcm_s24le", str(out)])
        return out

    def inputs(self, audio: Path | None, audio_codec: list[str]) -> tuple[list[str], list[str]]:
        if not audio:
            return ["-i", str(self.master)], ["-map", "0:v", "-an"]
        return ["-i", str(self.master), "-i", str(audio)], ["-map", "0:v", "-map", "1:a", *audio_codec, "-shortest"]

    def webm(self, audio: Path | None) -> Path:
        out = self.out_dir / f"{self.name}.webm"
        passlog = self.out_dir / f"{self.name}-vp9"
        video = ["-vf", self.video_filter(), "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str(self.webm_crf),
                 "-row-mt", "1", "-tile-columns", "2", "-deadline", "good", "-tune-content", "screen", "-g", "240",
                 *self.color_tags, *self.thread_args(), "-passlogfile", str(passlog)]
        self.run(["-i", str(self.master), *video, "-cpu-used", "4", "-pass", "1", "-an", "-f", "null", "-"])
        inputs, maps = self.inputs(audio, ["-c:a", "libopus", "-b:a", "160k"])
        self.run([*inputs, *maps, *video, "-cpu-used", "2", "-pass", "2", str(out)])
        for leftover in self.out_dir.glob(f"{self.name}-vp9*.log"):
            leftover.unlink()
        return out

    def mp4(self, audio: Path | None) -> Path:
        out = self.out_dir / f"{self.name}.mp4"
        inputs, maps = self.inputs(audio, ["-c:a", "aac", "-b:a", "192k"])
        self.run([*inputs, *maps, "-vf", self.video_filter(), "-c:v", "libx264", "-preset", "slow",
                  "-crf", str(self.mp4_crf), "-profile:v", "high", "-g", "120", *self.color_tags,
                  *self.thread_args(), "-movflags", "+faststart", str(out)])
        return out

    def youtube(self, audio: Path | None) -> Path:
        out = self.out_dir / f"{self.name}-youtube-master.mp4"
        inputs, maps = self.inputs(audio, ["-c:a", "aac", "-b:a", "384k"])
        source_height = int(subprocess.run(
            [self.config.tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height",
             "-of", "csv=p=0", str(self.master)], capture_output=True, text=True, check=True).stdout.strip())
        height = self.youtube_height if self.youtube_height > source_height else None
        self.run([*inputs, *maps, "-vf", self.video_filter(height), "-c:v", "libx264", "-preset", "slow",
                  "-crf", str(self.youtube_crf), "-profile:v", "high", "-bf", "2", "-g", "30", *self.color_tags,
                  *self.thread_args(), "-movflags", "+faststart", str(out)])
        return out

    def encode_all(self, formats: list[str] | None = None) -> dict:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        audio = self.normalized_audio()
        outputs = {}
        for fmt in formats or ["webm", "mp4", "youtube"]:
            self.progress(f"  encoding {fmt}")
            outputs[fmt] = str(getattr(self, fmt)(audio))
        if audio:
            audio.unlink()
        return outputs
