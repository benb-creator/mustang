import json
import shutil
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .cards import CardRenderer, Fonts
from .driver import EventLog
from .marker import ClockFit
from .narration import Narration, NarrationValues
from .settle import ChangeSeries, Rect


class ComposeError(Exception):
    pass


@dataclass
class ComposeLayout:
    pane_w: int
    pane_h: int
    scale: float
    header_h: int
    label_h: int
    footer_h: int

    @classmethod
    def for_pane(cls, pane_w: int, pane_h: int) -> "ComposeLayout":
        scale = pane_w / 1280
        header = int(round(140 * scale))
        label = int(round(110 * scale))
        footer = int(round(110 * scale))
        total = pane_h + header + label + footer
        footer += total % 2
        return cls(pane_w, pane_h, scale, header, label, footer)

    @property
    def width(self) -> int:
        return 2 * self.pane_w

    @property
    def height(self) -> int:
        return self.header_h + self.label_h + self.pane_h + self.footer_h

    @property
    def pane_top(self) -> int:
        return self.header_h + self.label_h


@dataclass
class PaneClip:
    side: str
    capture: Path
    crop: Rect
    first_frame_time: float
    steps: list
    end_time: float
    label: str
    name: str
    median_s: float
    actions: int

    @classmethod
    def load(cls, config, comparison: str, task: str, side_name: str, side: dict) -> "PaneClip":
        run_dir = config.workdir / "runs" / comparison / task / side["app"] / side["median_run"]
        meta = json.loads((run_dir / "meta.json").read_text())
        analysis = json.loads((run_dir / "analysis.json").read_text())
        events = EventLog.read(run_dir / "log.jsonl")
        f = analysis["clock_fit"]
        fit = ClockFit(f["slope"], f["offset"], f["residuals_s"], f["points"], f["rejected_codes"])
        first_input = next(e for e in events if e["type"] == "input" and e.get("phase") == "step")
        start = fit.to_video(first_input.get("t_before", first_input["t"]))
        series = ChangeSeries.load(run_dir / "changes.npz")
        index = int(np.searchsorted(series.times, start, side="left"))
        first_frame_time = float(series.times[min(index, len(series.times) - 1)])
        steps = [(s["start_time"], s["duration_s"]) for s in analysis["steps"]]
        end = max(s["end_time"] for s in analysis["steps"])
        label = " · ".join(str(x) for x in (f"{side['name']} {side.get('version') or ''}".strip(), side.get("protocol"),
                                            side.get("os")) if x)
        return cls(side_name, run_dir / "capture.mkv", Rect.from_dict(meta["layout"]["app_in_capture"]),
                   first_frame_time, steps, end, label, side["name"], side["median_s"], side["actions"])

    @property
    def relative_end(self) -> float:
        return self.end_time - self.first_frame_time

    def timer_expression(self, pre: float) -> str:
        parts = [f"clip(t-{pre + start - self.first_frame_time:.4f},0,{duration:.4f})" for start, duration in self.steps]
        return "+".join(parts) or "0"


@dataclass
class TimeLapse:
    start: float = 0.0
    end: float = 0.0
    factor: int = 1

    @property
    def active(self) -> bool:
        return self.factor > 1 and self.end > self.start

    def output_time(self, t: float) -> float:
        if not self.active or t <= self.start:
            return t
        if t <= self.end:
            return self.start + (t - self.start) / self.factor
        return t - (self.end - self.start) * (1 - 1 / self.factor)

    @classmethod
    def plan(cls, pre: float, fast_end: float, slow_end: float, threshold_s: float, max_compressed_s: float,
             keep_s: float = 5.0):
        if slow_end <= threshold_s:
            return cls()
        start = pre + max(keep_s, fast_end + 0.3 * keep_s)
        end = pre + slow_end - 0.4 * keep_s
        if end - start < 0.8 * keep_s:
            return cls()
        factor = next((f for f in (2, 4, 8, 16, 32, 64, 128) if (end - start) / f <= max_compressed_s), 128)
        return cls(start, end, factor)


@dataclass
class VoicePart:
    segment: str
    part: str
    text: str
    start: float
    duration: float
    file: Path | None = None


@dataclass
class SegmentPlan:
    id: str
    kind: str
    duration: float
    clip: Path | None = None
    voice: list = field(default_factory=list)
    info: dict = field(default_factory=dict)


class Composer:
    texts = {
        "en": {"footnote": "Recorded one after another on the same computer, synchronized at the start of each task. "
                           "Median of {runs} runs.",
               "done": "✓ Done", "speed": "{factor}× speed", "task": "Task", "ratio": "right ÷ left",
               "actions": "Actions", "results": "Results", "versus": "vs", "seconds": "s"},
        "de": {"footnote": "Nacheinander auf demselben Rechner aufgenommen, zum Start jeder Aufgabe synchronisiert. "
                           "Median aus {runs} Läufen.",
               "done": "✓ Fertig", "speed": "{factor}× Tempo", "task": "Aufgabe", "ratio": "rechts ÷ links",
               "actions": "Aktionen", "results": "Ergebnisse", "versus": "vs.", "seconds": "s"},
    }

    def __init__(self, config, results: dict, out_dir: Path, language: str = "en", narration: Narration | None = None,
                 only: list[str] | None = None, comparisons: list[str] | None = None, progress=print):
        self.config = config
        self.results = results
        self.out_dir = Path(out_dir)
        self.language = language
        self.narration = narration
        self.only = only
        self.comparisons = comparisons or list(results["comparisons"])
        self.progress = progress
        self.fps = int(config.get("capture.fps", 60))
        self.ffmpeg = config.tool("ffmpeg")
        self.ffprobe = config.tool("ffprobe")
        compose = config.get("compose") or {}
        self.fonts = Fonts(compose.get("font_regular"), compose.get("font_bold"))
        self.countdown_s = float(compose.get("countdown_s", 2.4))
        self.min_hold_s = float(compose.get("min_hold_s", 2.0))
        self.min_title_s = float(compose.get("min_title_s", 2.5))
        self.timelapse_threshold_s = float(compose.get("timelapse_threshold_s", 25))
        self.timelapse_max_s = float(compose.get("timelapse_max_compressed_s", 8))
        self.timelapse_keep_s = float(compose.get("timelapse_keep_s", 5))
        self.voice_dir = config.path(compose["voice_dir"]) if compose.get("voice_dir") else None
        self.music = config.path(compose["music"]) if compose.get("music") else None
        pane = self.pane_size()
        self.layout = ComposeLayout.for_pane(*pane)
        self.cards = CardRenderer(self.layout.width, self.layout.height, self.layout.scale, self.fonts)
        self.values = self.narration_values()
        self.work = self.out_dir / "segments"

    def t(self, key: str, **kwargs) -> str:
        overrides = ((self.config.get("compose") or {}).get("texts") or {}).get(self.language) or {}
        text = overrides.get(key) or self.texts.get(self.language, self.texts["en"])[key]
        return text.format(**kwargs)

    def pane_size(self) -> tuple[int, int]:
        region = self.config.get("display.app_region")
        return int(region["width"]), int(region["height"])

    def narration_values(self) -> NarrationValues:
        values = NarrationValues(self.language)
        values.set_count("runs", int(self.results["runs"]["measured"]))
        for key, value in (self.results.get("corpus") or {}).items():
            values.set_count(f"env.{key}", value)
        for comparison_id, comparison in self.results["comparisons"].items():
            env = (self.results.get("environment") or {}).get(comparison_id, {})
            for key in ("date", "os", "cpu", "ram", "display", "server", "rtt_ms", "cloud_sync_confirmed"):
                value = env.get(key)
                if isinstance(value, dict):
                    value = value.get("resolution") or value.get("version") or next(iter(value.values()), None)
                if value is not None:
                    values.set_text(f"env.{comparison_id}.{key}", str(value), value)
            for task_id, task in comparison["tasks"].items():
                for side in ("left", "right"):
                    s = task[side]
                    values.set_seconds(f"t.{comparison_id}.{side}.{task_id}", s.get("median_s"))
                    values.set_count(f"actions.{comparison_id}.{side}.{task_id}", s.get("actions"))
                    values.set_text(f"app.{comparison_id}.{side}",
                                    f"{s['name']} {s.get('version') or ''}".strip())
                values.set_ratio(f"ratio.{comparison_id}.{task_id}", task.get("ratio"))
        return values

    def voice_length(self, path: Path) -> float:
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()

    def voice_part(self, segment_id: str, part: str, text: str | None, start: float) -> VoicePart | None:
        if not text:
            return None
        name = f"{segment_id}.wav" if part == "voice" else f"{segment_id}.{part.replace('voice_', '')}.wav"
        file = self.voice_dir / self.language / name if self.voice_dir else None
        if file is not None and file.exists():
            duration = self.voice_length(file)
        else:
            file = None
            duration = self.narration.speech_seconds(text) if self.narration else len(text.split()) / 2.5
        return VoicePart(segment_id, part, text, start, duration, file)

    def run_ffmpeg(self, args: list[str]):
        result = subprocess.run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise ComposeError(f"ffmpeg failed: {result.stderr[-2000:]}")

    @property
    def lossless(self) -> list[str]:
        return ["-c:v", "libx264rgb", "-preset", "ultrafast", "-qp", "0", "-pix_fmt", "bgr0", "-r", str(self.fps)]

    def still_clip(self, image: Path, duration: float, out: Path) -> Path:
        self.run_ffmpeg(["-loop", "1", "-framerate", str(self.fps), "-t", f"{duration:.3f}", "-i", str(image),
                         *self.lossless, str(out)])
        return out

    @staticmethod
    def ffpath(path: Path) -> str:
        return "'" + str(path).replace("\\", "/").replace(":", "\\:").replace("'", "") + "'"

    def text_file(self, name: str, text: str) -> Path:
        path = self.work / f"{name}.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def drawtext(self, textfile: Path | None = None, text: str | None = None, size: int = 40, color: str = "white",
                 x: str = "0", y: str = "0", bold: bool = False, box: str | None = None, enable: str | None = None) -> str:
        font = self.fonts.bold if bold else self.fonts.regular
        parts = [f"fontfile={self.ffpath(Path(font))}", f"fontsize={size}", f"fontcolor={color}", f"x={x}", f"y={y}"]
        if textfile is not None:
            parts += [f"textfile={self.ffpath(textfile)}", "expansion=none"]
        else:
            parts.append(f"text='{text}'")
        if box:
            parts += ["box=1", f"boxcolor={box}", f"boxborderw={int(round(14 * self.layout.scale))}"]
        if enable:
            parts.append(f"enable='{enable}'")
        return "drawtext=" + ":".join(parts)

    def timer_text(self, expression: str) -> str:
        separator = "," if self.language == "de" else "."
        return (f"%{{eif\\:floor({expression})\\:d}}{separator}"
                f"%{{eif\\:mod(floor(({expression})*100),100)\\:d\\:2}} {self.t('seconds')}")

    def race(self, segment: dict, index: int) -> SegmentPlan | None:
        comparison_id, task_id = segment["comparison"], segment["task"]
        task = self.results["comparisons"].get(comparison_id, {}).get("tasks", {}).get(task_id)
        if not task or not task["left"].get("median_run") or not task["right"].get("median_run"):
            self.progress(f"  skipping race {segment['id']}: no measured median run for both apps")
            return None
        panes = [PaneClip.load(self.config, comparison_id, task_id, side, task[side]) for side in ("left", "right")]
        L = self.layout
        scale = L.scale
        pre = self.countdown_s
        ends = [p.relative_end for p in panes]
        voice_after = self.voice_part(segment["id"], "voice_after", segment.get("voice_after"), 0)
        hold = max(self.min_hold_s, (voice_after.duration + 0.6) if voice_after else 0)
        race_len = pre + max(ends) + hold
        lapse = TimeLapse.plan(pre, min(ends), max(ends), self.timelapse_threshold_s, self.timelapse_max_s,
                               self.timelapse_keep_s)
        title = segment.get("supers", [None])[0] if segment.get("supers") else None
        title = title or self.scenario_title(task)
        background = self.cards.race_background(self.work / f"{index:03d}-bg.png", L, title, panes[0].label,
                                                panes[1].label, self.t("footnote", runs=self.results["runs"]["measured"]))

        chains = []
        for n, pane in enumerate(panes):
            c = pane.crop
            chains.append(
                f"[{n + 1}:v]trim=start={pane.first_frame_time:.4f}:end={pane.end_time + 0.5 / self.fps:.4f},"
                f"setpts=PTS-STARTPTS,crop={c.width}:{c.height}:{c.x}:{c.y},fps={self.fps},"
                f"tpad=start_mode=clone:start_duration={pre:.4f}:stop_mode=clone:stop_duration={race_len:.4f},"
                f"trim=duration={race_len:.4f},setpts=PTS-STARTPTS[p{n}]")
        chains.append(f"[0:v]fps={self.fps},trim=duration={race_len:.4f},setpts=PTS-STARTPTS[bg]")
        chains.append(f"[bg][p0]overlay=x=0:y={L.pane_top}:shortest=1[c0]")
        chains.append(f"[c0][p1]overlay=x={L.pane_w}:y={L.pane_top}:shortest=1[c1]")
        draw = []
        timer_size = int(round(52 * scale))
        badge_size = int(round(34 * scale))
        done_file = self.text_file(f"{index:03d}-done", self.t("done"))
        for n, pane in enumerate(panes):
            x0 = n * L.pane_w
            label_y = L.header_h
            draw.append(self.drawtext(text=self.timer_text(pane.timer_expression(pre)), size=timer_size, bold=True,
                                      x=f"{x0 + L.pane_w - int(28 * scale)}-tw",
                                      y=f"{label_y}+({L.label_h}-th)/2"))
            done_at = pre + pane.relative_end
            draw.append(self.drawtext(textfile=done_file, size=badge_size, bold=True, color="white", box="0x27AE60",
                                      x=f"{x0 + L.pane_w - int(330 * scale)}-tw", y=f"{label_y}+({L.label_h}-th)/2",
                                      enable=f"gte(t,{done_at:.4f})"))
        count_size = int(round(220 * scale))
        third = pre / 3
        for k, number in enumerate(("3", "2", "1")):
            draw.append(self.drawtext(text=number, size=count_size, bold=True, box="0x000000@0.55",
                                      x="(w-tw)/2", y=f"{L.pane_top}+({L.pane_h}-th)/2",
                                      enable=f"between(t,{k * third:.4f},{(k + 1) * third - 0.001:.4f})"))
        slow_done = pre + max(ends)
        for k, line in enumerate((segment.get("supers") or [])[1:3]):
            line_file = self.text_file(f"{index:03d}-super-{k}", line)
            draw.append(self.drawtext(textfile=line_file, size=int(round(40 * scale)), box="0x000000@0.7",
                                      x="(w-tw)/2", y=f"{L.pane_top + L.pane_h - int((150 - 70 * k) * scale)}",
                                      enable=f"gte(t,{slow_done:.4f})"))
        chains.append(f"[c1]{','.join(draw)}[race]")
        if lapse.active:
            chains.append("[race]split=3[r0][r1][r2]")
            chains.append(f"[r0]trim=end={lapse.start:.4f},setpts=PTS-STARTPTS[s0]")
            chains.append(f"[r1]trim=start={lapse.start:.4f}:end={lapse.end:.4f},"
                          f"setpts=(PTS-STARTPTS)/{lapse.factor},fps={self.fps}[s1]")
            chains.append(f"[r2]trim=start={lapse.end:.4f},setpts=PTS-STARTPTS[s2]")
            speed_file = self.text_file(f"{index:03d}-speed", self.t("speed", factor=lapse.factor))
            lapse_out_end = lapse.output_time(lapse.end)
            chains.append("[s0][s1][s2]concat=n=3:v=1:a=0,"
                          + self.drawtext(textfile=speed_file, size=int(round(48 * scale)), bold=True,
                                          box="0xE67E22", x="(w-tw)/2", y=f"{L.pane_top + int(30 * scale)}",
                                          enable=f"between(t,{lapse.start:.4f},{lapse_out_end:.4f})") + "[out]")
        else:
            chains.append("[race]null[out]")
        script = self.work / f"{index:03d}-race.txt"
        script.write_text(";\n".join(chains), encoding="utf-8")
        out = self.work / f"{index:03d}-{segment['id']}.mkv"
        self.run_ffmpeg(["-loop", "1", "-framerate", str(self.fps), "-t", f"{race_len + 1:.3f}", "-i", str(background),
                         "-i", str(panes[0].capture), "-i", str(panes[1].capture),
                         "-/filter_complex", str(script), "-map", "[out]", *self.lossless, str(out)])
        duration = lapse.output_time(race_len)
        voice = []
        during = self.voice_part(segment["id"], "voice_during", segment.get("voice_during"), lapse.output_time(pre))
        if during and during.duration <= min(ends):
            voice.append(during)
        if voice_after:
            voice_after.start = lapse.output_time(slow_done) + 0.3
            voice.append(voice_after)
        info = {"comparison": comparison_id, "task": task_id, "pre_s": pre, "timelapse": vars(lapse),
                "panes": {p.side: {"run": str(p.capture.parent), "relative_end_s": p.relative_end,
                                   "done_at_output_s": lapse.output_time(pre + p.relative_end),
                                   "median_s": p.median_s} for p in panes}}
        return SegmentPlan(segment["id"], "race", duration, out, voice, info)

    def scenario_title(self, task: dict) -> str:
        title = task.get("title") or {}
        return title.get(self.language) or title.get("en") or ""

    def title_for_race(self, segment: dict, index: int) -> SegmentPlan | None:
        comparison_id, task_id = segment["comparison"], segment["task"]
        task = self.results["comparisons"].get(comparison_id, {}).get("tasks", {}).get(task_id)
        if not task or not task["left"].get("median_run") or not task["right"].get("median_run"):
            return None
        voice = self.voice_part(segment["id"], "voice_before", segment.get("voice_before"), 0.2)
        duration = max(self.min_title_s, (voice.duration + 0.5) if voice else 0)
        title = (segment.get("supers") or [None])[0] or self.scenario_title(task)
        subtitle = (f"{task['left']['name']} ({task['left']['protocol']}) {self.t('versus')} "
                    f"{task['right']['name']} ({task['right']['protocol']}) · "
                    f"{self.results['comparisons'][comparison_id].get('os') or ''}")
        image = self.cards.title_card(self.work / f"{index:03d}-title.png", title, subtitle, [])
        clip = self.still_clip(image, duration, self.work / f"{index:03d}-{segment['id']}-title.mkv")
        return SegmentPlan(f"{segment['id']}:title", "title", duration, clip, [voice] if voice else [])

    def text_segment(self, segment: dict, index: int) -> SegmentPlan:
        voice = self.voice_part(segment["id"], "voice", segment.get("voice"), 0.2)
        duration = max(float(segment.get("duration_s", 4)), (voice.duration + 0.5) if voice else 0)
        lines = segment.get("supers") or []
        image = self.cards.text_card(self.work / f"{index:03d}-card.png", lines)
        clip = self.still_clip(image, duration, self.work / f"{index:03d}-{segment['id']}.mkv")
        return SegmentPlan(segment["id"], segment["kind"], duration, clip, [voice] if voice else [])

    def result_segment(self, segment: dict, index: int) -> SegmentPlan | None:
        comparison_id = segment.get("comparison")
        comparison = self.results["comparisons"].get(comparison_id)
        if not comparison:
            return None
        values = self.values
        rows = []
        any_task = next(iter(comparison["tasks"].values()))
        for task_id, task in comparison["tasks"].items():
            left, right = task["left"], task["right"]
            fmt = lambda s: "–" if s is None else f"{values.seconds_text(s)} {self.t('seconds')}"
            rows.append({
                "task": f"{task_id} {self.scenario_title(task)}",
                "left": fmt(left.get("median_s")), "right": fmt(right.get("median_s")),
                "ratio": "–" if task.get("ratio") is None else f"{values.number(task['ratio'], 1)}×",
                "actions": f"{left.get('actions', '–')} / {right.get('actions', '–')}",
                "range_left": "" if left.get("min_s") is None else
                f"{values.seconds_text(left['min_s'])}–{values.seconds_text(left['max_s'])}",
                "range_right": "" if right.get("min_s") is None else
                f"{values.seconds_text(right['min_s'])}–{values.seconds_text(right['max_s'])}",
                "left_first": (task.get("ratio") or 0) > 1, "right_first": (task.get("ratio") or 2) < 1})
        env = (self.results.get("environment") or {}).get(comparison_id, {})
        footer = list(segment.get("supers") or [])
        footer.append(" · ".join(str(x) for x in (env.get("os"), env.get("cpu"), env.get("ram"),
                                                  (env.get("server") or {}).get("name"),
                                                  (env.get("server") or {}).get("version"), env.get("date")) if x))
        left_name = f"{any_task['left']['name']} ({any_task['left']['protocol']})"
        right_name = f"{any_task['right']['name']} ({any_task['right']['protocol']})"
        image = self.cards.result_card(self.work / f"{index:03d}-result.png", self.t("results"), left_name, right_name,
                                       rows, footer, {"task": self.t("task"), "ratio": self.t("ratio"),
                                                      "actions": self.t("actions")})
        voice = self.voice_part(segment["id"], "voice", segment.get("voice"), 0.2)
        duration = max(float(segment.get("duration_s", 8)), (voice.duration + 0.5) if voice else 0)
        clip = self.still_clip(image, duration, self.work / f"{index:03d}-{segment['id']}.mkv")
        return SegmentPlan(segment["id"], "card", duration, clip, [voice] if voice else [])

    def default_segments(self) -> list[dict]:
        segments = []
        for comparison_id in self.comparisons:
            comparison = self.results["comparisons"][comparison_id]
            for task_id in comparison["tasks"]:
                segments.append({"id": f"{comparison_id.lower()}-{task_id.lower()}", "kind": "race",
                                 "comparison": comparison_id, "task": task_id})
            segments.append({"id": f"{comparison_id.lower()}-result", "kind": "card", "card": "result",
                             "comparison": comparison_id, "duration_s": 6})
        return segments

    def segments(self) -> list[dict]:
        if not self.narration:
            return self.default_segments()
        resolved = self.narration.resolve(self.values, self.only)
        return [s for s in resolved if not s.get("comparison") or s["comparison"] in self.comparisons]

    def compose(self) -> dict:
        if self.work.exists():
            shutil.rmtree(self.work)
        self.work.mkdir(parents=True)
        plans: list[SegmentPlan] = []
        for index, segment in enumerate(self.segments()):
            self.progress(f"  segment {segment['id']} ({segment['kind']})")
            if segment["kind"] == "race":
                title = self.title_for_race(segment, index)
                race = self.race(segment, index)
                plans += [p for p in (title, race) if p]
            elif segment["kind"] == "card" and segment.get("card") == "result":
                card = self.result_segment(segment, index)
                if card:
                    plans.append(card)
            else:
                plans.append(self.text_segment(segment, index))
        if not plans:
            raise ComposeError("Nothing to compose")
        timeline, voice_parts, position = [], [], 0.0
        for plan in plans:
            for part in plan.voice:
                part.start += position
                voice_parts.append(part)
            timeline.append({"id": plan.id, "kind": plan.kind, "start_s": round(position, 4),
                             "end_s": round(position + plan.duration, 4), "clip": str(plan.clip), **plan.info,
                             "voice": [{"part": v.part, "text": v.text, "start_s": round(v.start, 3),
                                        "end_s": round(v.start + v.duration, 3),
                                        "file": str(v.file) if v.file else None} for v in plan.voice]})
            position += self.clip_duration(plan.clip)
        concat_list = self.work / "concat.txt"
        concat_list.write_text("".join(f"file '{p.clip.as_posix()}'\n" for p in plans), encoding="utf-8")
        master = self.out_dir / "master.mkv"
        self.run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(master)])
        total = self.clip_duration(master)
        audio = self.mix_audio(voice_parts, total)
        (self.out_dir / "timeline.json").write_text(json.dumps(
            {"language": self.language, "duration_s": total, "width": self.layout.width,
             "height": self.layout.height, "fps": self.fps, "segments": timeline,
             "audio": str(audio) if audio else None}, indent=2, ensure_ascii=False), encoding="utf-8")
        SubtitleWriter(voice_parts).write(self.out_dir / "subtitles.vtt", self.out_dir / "subtitles.srt")
        self.write_voice_script(voice_parts)
        return {"master": str(master), "audio": str(audio) if audio else None, "duration_s": total,
                "segments": len(plans)}

    def clip_duration(self, path: Path) -> float:
        out = subprocess.run([self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                              str(path)], capture_output=True, text=True, check=True).stdout
        return float(out.strip())

    def mix_audio(self, parts: list[VoicePart], total: float) -> Path | None:
        recorded = [p for p in parts if p.file]
        if not recorded and not self.music:
            return None
        out = self.out_dir / "audio.wav"
        inputs, chains, labels = [], [], []
        for n, part in enumerate(recorded):
            inputs += ["-i", str(part.file)]
            delay = int(round(part.start * 1000))
            chains.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay}|{delay}[v{n}]")
            labels.append(f"[v{n}]")
        base = len(recorded)
        inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        chains.append(f"[{base}:a]{''.join(labels)}amix=inputs={len(labels) + 1}:normalize=0:duration=first[voice]")
        if self.music:
            inputs += ["-stream_loop", "-1", "-i", str(self.music)]
            volume = float((self.config.get("compose") or {}).get("music_volume_db", -16))
            chains.append(f"[{base + 1}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},"
                          f"volume={volume}dB[music]")
            chains.append("[voice]asplit=2[vk][vm]")
            chains.append("[music][vk]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=500[ducked]")
            chains.append("[ducked][vm]amix=inputs=2:normalize=0:duration=first[mix]")
            final = "[mix]"
        else:
            final = "[voice]"
        self.run_ffmpeg([*inputs, "-filter_complex", ";".join(chains), "-map", final, "-t", f"{total:.3f}",
                         "-c:a", "pcm_s24le", str(out)])
        return out

    def write_voice_script(self, parts: list[VoicePart]):
        entries = [{"file": f"{p.segment}.wav" if p.part == "voice" else f"{p.segment}.{p.part.replace('voice_', '')}.wav",
                    "text": p.text, "start_s": round(p.start, 3), "estimated_s": round(p.duration, 2),
                    "recorded": bool(p.file)} for p in parts]
        (self.out_dir / "voice-script.json").write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                                                         encoding="utf-8")
        lines = [f"# Voice script ({self.language})", "",
                 "Record or synthesize each line into `voice/<lang>/<file>` and compose again; the composer then uses "
                 "the real lengths.", ""]
        lines += [f"- `{e['file']}` at {e['start_s']:.1f} s (≈ {e['estimated_s']:.1f} s): {e['text']}" for e in entries]
        (self.out_dir / "voice-script.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


class SubtitleWriter:
    def __init__(self, parts: list[VoicePart], max_chars: int = 84):
        self.parts = parts
        self.max_chars = max_chars

    def cues(self) -> list[tuple[float, float, str]]:
        cues = []
        for part in self.parts:
            words = part.text.split()
            chunks, current = [], ""
            for word in words:
                if current and len(current) + 1 + len(word) > self.max_chars:
                    chunks.append(current)
                    current = word
                else:
                    current = f"{current} {word}".strip()
            if current:
                chunks.append(current)
            total_chars = sum(len(c) for c in chunks) or 1
            t = part.start
            for chunk in chunks:
                length = part.duration * len(chunk) / total_chars
                cues.append((t, t + length, self.wrap(chunk)))
                t += length
        return cues

    def wrap(self, text: str) -> str:
        if len(text) <= self.max_chars // 2:
            return text
        middle = len(text) // 2
        split = text.rfind(" ", 0, middle + 8)
        return text if split <= 0 else text[:split] + "\n" + text[split + 1:]

    @staticmethod
    def stamp(t: float, separator: str) -> str:
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{separator}{ms % 1000:03d}"

    def write(self, vtt: Path, srt: Path):
        cues = self.cues()
        vtt.write_text("WEBVTT\n\n" + "".join(
            f"{self.stamp(a, '.')} --> {self.stamp(b, '.')}\n{text}\n\n" for a, b, text in cues), encoding="utf-8")
        srt.write_text("".join(
            f"{n}\n{self.stamp(a, ',')} --> {self.stamp(b, ',')}\n{text}\n\n" for n, (a, b, text) in enumerate(cues, 1)),
            encoding="utf-8")
