import json
import shutil
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .cards import CardRenderer, Fonts
from .facts import PersonFacts
from .narration import Condition, Narration, NarrationValues, SpokenDuration
from .settle import ChangeSeries, Rect


class ComposeError(Exception):
    pass


@dataclass
class ComposeLayout:
    """Bands around the two panes: header (title, time-lapse label), label bars (app, timer, badge), the panes,
    the hold band (both times, supers, "Go!") and the footer (2-line footnote). Nothing is drawn over a pane."""
    pane_w: int
    pane_h: int
    scale: float
    header_h: int
    label_h: int
    hold_h: int
    footer_h: int

    @classmethod
    def for_pane(cls, pane_w: int, pane_h: int) -> "ComposeLayout":
        scale = pane_w / 1280
        header, label, hold, footer = (int(round(v * scale)) for v in (140, 70, 190, 100))
        footer += (pane_h + header + label + hold + footer) % 2
        return cls(pane_w, pane_h, scale, header, label, hold, footer)

    @property
    def width(self) -> int:
        return 2 * self.pane_w

    @property
    def label_top(self) -> int:
        return self.header_h

    @property
    def pane_top(self) -> int:
        return self.header_h + self.label_h

    @property
    def hold_top(self) -> int:
        return self.pane_top + self.pane_h

    @property
    def footer_top(self) -> int:
        return self.hold_top + self.hold_h

    @property
    def height(self) -> int:
        return self.footer_top + self.footer_h


class ShortSettings:
    """The voice-over's `variants/compose.json` (short-video settings), with defaults for older narrations."""

    defaults = {
        "countdown_s": 0.8, "countdown_text": {"en": "Go!", "de": "Los!"}, "countdown_voice": None,
        "hook_pad_s": 0.4, "hold_pad_s": 0.6, "min_hold_s": 2.0, "realtime_start_s": 1.0,
        "realtime_after_fast_s": 0.5, "microsoft_timelapse": False,
        "timelapse_factors": [2, 3, 4, 5, 8, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 250, 300, 400, 500,
                              750, 1000, 1500, 2000, 3000, 5000],
        "labels": {"en": {"timelapse": "Time-lapse {factor}× · timers in real time",
                          "timer_race": "Time-lapse {factor}× · recording not shown · timers in real time",
                          "timelapse_after": "Shown at {factor}× · timers in real time",
                          "timer_race_after": "Shown at {factor}× · recording not shown · timers in real time",
                          "opening_screen": "Opening screen not shown, timer running",
                          "time_limit": "Time limit reached",
                          "step_sync": ["synchronized at the start", "synchronized at each step"]},
                   "de": {"timelapse": "Zeitraffer {factor}× · Uhren in Echtzeit",
                          "timer_race": "Zeitraffer {factor}× · Aufnahme nicht gezeigt · Uhren in Echtzeit",
                          "timelapse_after": "Gezeigt mit {factor}× · Uhren in Echtzeit",
                          "timer_race_after": "Gezeigt mit {factor}× · Aufnahme nicht gezeigt · Uhren in Echtzeit",
                          "opening_screen": "Startbildschirm nicht gezeigt, Uhr läuft",
                          "time_limit": "Zeitlimit erreicht",
                          "step_sync": ["synchron gestartet", "bei jedem Schritt synchronisiert"]}},
    }

    def __init__(self, data: dict | None, config_compose: dict, path: Path | None = None):
        data = data or {}
        self.path = path
        short = {**self.defaults, **(data.get("short") or {})}
        self.short = short
        self.race_budget_s = dict(data.get("race_budget_s") or {})
        self.default_budget_s = float(config_compose.get("race_budget_s", 30))
        self.video_length_s = data.get("video_length_s")
        self.combined_length_s = data.get("combined_length_s")
        self.publish_when = dict(data.get("publish_when") or {})
        self.publish_instead = dict(data.get("publish_instead") or {})
        self.footage_when = {k.split("_")[0].upper(): v for k, v in data.items()
                             if k.endswith("_microsoft_footage_when")}
        self.voice_direction = dict(data.get("voice_direction") or {})
        self.person_set_facts = data.get("person_set_facts") or PersonFacts.default_allowed
        self.pane_protocol = dict(data.get("pane_protocol") or {})
        self.pane_names = dict(data.get("pane_names") or {})

    @classmethod
    def find(cls, root: Path | None, config_compose: dict) -> "ShortSettings":
        if root:
            for candidate in (Path(root) / "variants" / "compose.json", Path(root) / "compose.json"):
                if candidate.exists():
                    return cls(json.loads(candidate.read_text()), config_compose, candidate)
        return cls(None, config_compose)

    def budget(self, comparison: str) -> float:
        return float(self.race_budget_s.get(comparison, self.default_budget_s))

    def label(self, language: str, key: str, **kwargs):
        labels = self.short["labels"].get(language) or self.short["labels"]["en"]
        defaults = self.defaults["labels"].get(language) or self.defaults["labels"]["en"]
        value = labels.get(key) or defaults[key]
        return value.format(**kwargs) if isinstance(value, str) else value

    def instead(self, variant: str) -> list[str]:
        value = self.publish_instead.get(variant)
        return [value] if isinstance(value, str) else list(value or [])


class PaneLabels:
    """What names an app on screen and in the method texts (spec v6): the narration's `pane_names` for the
    language (left = Parula, right per comparison) and `pane_protocol` per side, both from compose.json. The protocol
    is part of the narration's contract: an app whose own protocol (its config's, e.g. "IMAP (via Microsoft cloud)"
    in older Windows results) doesn't name that protocol first is refused. Without compose.json the config's name
    and protocol."""

    def __init__(self, settings: ShortSettings, language: str):
        self.protocols = settings.pane_protocol
        self.names = settings.pane_names.get(language) or settings.pane_names.get("en") or {}

    def name(self, comparison_id: str, side_name: str, side: dict) -> str:
        return self.names.get("left" if side_name == "left" else comparison_id) or side["name"]

    def protocol(self, comparison_id: str, side_name: str, side: dict) -> str | None:
        wanted = self.protocols.get(side_name)
        if not wanted:
            return side.get("protocol")
        recorded = str(side.get("protocol") or "").split()
        if not recorded or recorded[0].upper() != str(wanted).upper():
            raise ComposeError(f"{comparison_id} {side_name}: {side['name']} has the protocol "
                               f"'{side.get('protocol')}', but the narration labels this side '{wanted}' "
                               f"(compose.json pane_protocol)")
        return str(wanted)

    def named(self, comparison_id: str, side_name: str, side: dict) -> str:
        """Name and protocol, e.g. "new Outlook (IMAP)"."""
        protocol = self.protocol(comparison_id, side_name, side)
        name = self.name(comparison_id, side_name, side)
        return f"{name} ({protocol})" if protocol else name

    def bar(self, comparison_id: str, side_name: str, side: dict, with_os: bool = True) -> str:
        """The label bar: name and version · protocol · OS."""
        name = f"{self.name(comparison_id, side_name, side)} {side.get('version') or ''}".strip()
        parts = (name, self.protocol(comparison_id, side_name, side), side.get("os") if with_os else None)
        return " · ".join(str(x) for x in parts if x)


@dataclass
class PaneRun:
    """The run a pane shows (the median run, or the run at the median position of a series that hit the time
    limit), as pieces of the recording: `steps` are (video start, waiting seconds) of each measured step."""
    side: str
    app_id: str
    capture: Path
    crop: Rect
    steps: list
    timed_out: bool
    recording_end: float
    label: str
    name: str
    microsoft: bool
    times: np.ndarray
    opening: list = field(default_factory=list)

    @classmethod
    def load(cls, config, comparison: str, task: str, side_name: str, side: dict, run_id: str,
             result_folder: str | None, labels: PaneLabels) -> "PaneRun":
        entry = next((r for r in side.get("runs", []) if r["run"] == run_id), {})
        if result_folder and entry.get("dir"):
            run_dir = Path(result_folder) / entry["dir"]
        elif entry.get("dir") and Path(entry["dir"]).is_absolute():
            run_dir = Path(entry["dir"])
        else:
            run_dir = config.workdir / "runs" / config.run_group(comparison) / task / side["app"] / run_id
        meta = json.loads((run_dir / "meta.json").read_text())
        analysis = json.loads((run_dir / "analysis.json").read_text())
        series = ChangeSeries.load(run_dir / "changes.npz")
        steps = []
        for s in analysis["steps"]:
            steps.append((s["start_time"], s["duration_s"] if s.get("duration_s") is not None else s["limit_s"]))
        label = labels.bar(comparison, side_name, side)
        microsoft = side.get("microsoft_ui")
        if microsoft is None:
            microsoft = config.app(side["app"]).get("microsoft_ui")
        return cls(side_name, side["app"], run_dir / "capture.mkv", Rect.from_dict(meta["layout"]["app_in_capture"]),
                   steps, analysis["status"] == "timeout", float(series.times[-1]), label,
                   labels.name(comparison, side_name, side), bool(microsoft), series.times,
                   analysis.get("opening_ranges") or [])

    @property
    def first(self) -> float:
        return self.steps[0][0]

    @property
    def waiting(self) -> float:
        return sum(d for _, d in self.steps)

    @property
    def wall_end(self) -> float:
        start, duration = self.steps[-1]
        return start + duration - self.first

    def length(self, mode: str) -> float:
        return self.waiting if mode == "cut" else self.wall_end

    def pieces(self, mode: str, play_until: float) -> list[tuple[float, float]]:
        """Source intervals (video time) that make up the pane's timeline up to `play_until` (pane seconds)."""
        if mode != "cut":
            return [(self.first, min(self.first + play_until, self.recording_end))]
        pieces, used = [], 0.0
        for i, (start, duration) in enumerate(self.steps):
            take = duration if i + 1 < len(self.steps) else max(duration, play_until - used)
            take = min(take, play_until - used, self.recording_end - start)
            if take > 0:
                pieces.append((start, start + take))
                used += take
        return pieces

    def timer_expression(self, real: str, mode: str) -> str:
        if mode == "cut":
            return f"clip({real},0,{self.waiting:.4f})"
        parts = [f"clip({real}-{start - self.first:.4f},0,{duration:.4f})" for start, duration in self.steps]
        return "+".join(parts) or "0"


@dataclass
class RacePlan:
    """Output timeline of a race: hook, "Go!", real time until `a`, one time-lapse factor until `s`, then the hold.
    Pane seconds `r` map to output time `out(r)`."""
    hook: float
    countdown: float
    a: float
    s: float
    factor: int
    hold: float
    timer_race: bool = False

    @classmethod
    def for_budget(cls, hook: float, countdown: float, fast: float, slow: float, budget: float,
                   factors: list[int], realtime_start_s: float, realtime_after_fast_s: float, hold: float,
                   timer_race: bool = False) -> "RacePlan":
        if slow <= budget:
            return cls(hook, countdown, slow, slow, 1, hold)
        a = realtime_start_s if timer_race else (fast + realtime_after_fast_s if fast + realtime_after_fast_s <= budget / 2
                                                 else realtime_start_s)
        factor = next((f for f in sorted(factors) if a + (slow - a) / f <= budget), max(factors))
        return cls(hook, countdown, a, slow, int(factor), hold, timer_race)

    @property
    def go(self) -> float:
        return self.hook

    @property
    def t0(self) -> float:
        return self.hook + self.countdown

    @property
    def t1(self) -> float:
        return self.t0 + self.a

    @property
    def t2(self) -> float:
        return self.t1 + (self.s - self.a) / self.factor

    @property
    def hold_start(self) -> float:
        return self.t2

    @property
    def total(self) -> float:
        return self.t2 + self.hold

    @property
    def lapsed(self) -> bool:
        return self.factor > 1 and self.s > self.a

    def out(self, r: float) -> float:
        if r <= self.a:
            return self.t0 + r
        return self.t1 + (min(r, self.s) - self.a) / self.factor

    def real_expression(self) -> str:
        return (f"if(lt(t,{self.t0:.4f}),0,if(lt(t,{self.t1:.4f}),t-{self.t0:.4f},"
                f"if(lt(t,{self.t2:.4f}),{self.a:.4f}+(t-{self.t1:.4f})*{self.factor},{self.s:.4f})))")


class FilterInputs:
    """ffmpeg input arguments, with the index each input gets in the filter graph."""

    def __init__(self):
        self.args: list[str] = []
        self.count = 0

    def add(self, *args: str) -> int:
        self.args += list(args)
        self.count += 1
        return self.count - 1


@dataclass
class VoicePart:
    segment: str
    part: str
    text: str
    start: float
    duration: float
    file: Path | None = None
    subtitled: bool = True


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
        "en": {"footnote": ["Recorded one after another, same computer · synchronized at the start · "
                            "median of {runs} runs",
                            "Timer: waiting time only, typing not counted · test by the Parula team"],
               "typing_cut": "typing cut out",
               "done": "✓ Done", "task": "Task", "ratio": "right ÷ left", "actions": "Actions", "results": "Results",
               "seconds": "s", "not_done": "not done in {limit}", "no_measurement": "No valid measurement",
               "median_of": "Median of {runs} runs", "how_tested": "How we tested: below the video",
               "self_test": "Test by the Parula team", "preview": "INTERNAL PREVIEW – not for publication"},
        "de": {"footnote": ["Nacheinander aufgenommen, derselbe Rechner · synchron gestartet · Median aus {runs} Läufen",
                            "Uhr: nur Wartezeit, Tippen nicht gezählt · Test: das Parula-Team"],
               "typing_cut": "Tippen herausgeschnitten",
               "done": "✓ Fertig", "task": "Aufgabe", "ratio": "rechts ÷ links", "actions": "Aktionen",
               "results": "Ergebnisse", "seconds": "s", "not_done": "nicht fertig in {limit}",
               "no_measurement": "Keine gültige Messung", "median_of": "Median aus {runs} Läufen",
               "how_tested": "So haben wir getestet: unter dem Video", "self_test": "Test: das Parula-Team",
               "preview": "INTERNE VORSCHAU – nicht zur Veröffentlichung"},
    }

    def __init__(self, config, results: dict, out_dir: Path, language: str = "en", narration: Narration | None = None,
                 only: list[str] | None = None, comparisons: list[str] | None = None, progress=print,
                 settings: ShortSettings | None = None, facts: dict | None = None, variant: str | None = None):
        self.config = config
        self.results = results
        self.out_dir = Path(out_dir)
        self.language = language
        self.narration = narration
        self.only = only
        self.variant = variant
        self.comparisons = comparisons or list(results["comparisons"])
        self.progress = progress
        self.fps = int(config.get("capture.fps", 60))
        self.ffmpeg = config.tool("ffmpeg")
        self.ffprobe = config.tool("ffprobe")
        compose = config.get("compose") or {}
        self.compose_config = compose
        self.settings = settings or ShortSettings(None, compose)
        self.labels = PaneLabels(self.settings, language)
        self.facts = facts or {}
        self.fonts = Fonts(compose.get("font_regular"), compose.get("font_bold"))
        self.voice_dir = config.path(compose["voice_dir"]) if compose.get("voice_dir") else None
        self.music = config.path(compose["music"]) if compose.get("music") else None
        self.layout = ComposeLayout.for_pane(*self.pane_size())
        self.cards = CardRenderer(self.layout.width, self.layout.height, self.layout.scale, self.fonts)
        self.values = ValuesBuilder(config, results, language, self.facts, self.settings.person_set_facts).build()
        self.work = self.out_dir / "segments"

    def t(self, key: str, **kwargs):
        overrides = ((self.config.get("compose") or {}).get("texts") or {}).get(self.language) or {}
        text = overrides.get(key) or self.texts.get(self.language, self.texts["en"])[key]
        if isinstance(text, list):
            return [line.format(**kwargs) for line in text]
        return text.format(**kwargs)

    def pane_size(self) -> tuple[int, int]:
        region = self.config.get("display.app_region")
        return int(region["width"]), int(region["height"])

    def voice_length(self, path: Path) -> float:
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()

    def voice_file(self, segment_id: str, part: str) -> Path | None:
        if not self.voice_dir:
            return None
        name = f"{segment_id}.wav" if part == "voice" else f"{segment_id}.{part.replace('voice_', '')}.wav"
        file = self.voice_dir / self.language / name
        return file if file.exists() else None

    def voice_part(self, segment: dict, part: str, start: float) -> VoicePart | None:
        text = segment.get(part)
        if not text:
            return None
        missing = (segment.get("missing") or {}).get(part)
        if missing:
            raise ComposeError(f"Segment {segment['id']} {part}: no value for {', '.join(missing)}; the chosen "
                               f"alternative would speak a placeholder")
        file = self.voice_file(segment["id"], part)
        if file is not None:
            duration = self.voice_length(file)
        else:
            duration = self.narration.speech_seconds(text) if self.narration else len(text.split()) / 2.5
        return VoicePart(segment["id"], part, text, start, duration, file)

    def countdown_part(self, start: float) -> VoicePart | None:
        name = self.settings.short.get("countdown_voice")
        if not name:
            return None
        file = self.voice_dir / self.language / Path(name).name if self.voice_dir else None
        if file is None or not file.exists():
            return None
        return VoicePart("countdown", "countdown", self.settings.short["countdown_text"].get(self.language, "Go!"),
                         start, self.voice_length(file), file, subtitled=False)

    def sfx_part(self, key: str, start: float) -> VoicePart | None:
        path = self.compose_config.get(key)
        if not path:
            return None
        file = self.config.path(path)
        return VoicePart(key, key, "", start, self.voice_length(file), file, subtitled=False)

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
            parts += ["box=1", f"boxcolor={box}", f"boxborderw={int(round(12 * self.layout.scale))}"]
        if enable:
            parts.append(f"enable='{enable}'")
        return "drawtext=" + ":".join(parts)

    def timer_drawtexts(self, value: str, x: str, y: str, size: int) -> list[str]:
        """Seconds with two decimals below 60 s, minutes:seconds from 60 s on."""
        separator = "," if self.language == "de" else "."
        short = (f"%{{eif\\:floor({value})\\:d}}{separator}%{{eif\\:mod(floor(({value})*100),100)\\:d\\:2}} "
                 f"{self.t('seconds')}")
        long = f"%{{eif\\:floor(({value})/60)\\:d}}\\:%{{eif\\:mod(floor({value}),60)\\:d\\:2}}"
        return [self.drawtext(text=short, size=size, bold=True, x=x, y=y, enable=f"lt({value},60)"),
                self.drawtext(text=long, size=size, bold=True, x=x, y=y, enable=f"gte({value},60)")]

    def scenario_title(self, task: dict) -> str:
        title = task.get("title") or {}
        return title.get(self.language) or title.get("en") or ""

    def condition(self, source: str | None) -> bool:
        return True if not source else Condition(source).evaluate(self.values.raw)

    def footage_allowed(self, comparison_id: str) -> bool:
        """`c4_microsoft_footage_when` applies to compositions with C4's data-path card (c4, combined)."""
        rule = self.settings.footage_when.get(comparison_id)
        if not rule or not any(segment_id.endswith("-path") for segment_id in (self.only or [])):
            return True
        return self.condition(rule)

    def footnote(self, segment: dict, mode: str) -> list[str]:
        lines = list(segment.get("footnote") or self.t("footnote", runs=self.results["runs"]["measured"]))
        if mode == "cut":
            start_label = self.settings.label(self.language, "step_sync")[0]
            lines = [line.replace(start_label, f"{start_label} · {self.t('typing_cut')}") for line in lines]
        return [self.values.substitute(line) for line in lines]

    def race_mode(self, panes: list[PaneRun]) -> str:
        """Start-synchronized unless the panes would finish on screen in another order than their timers stop."""
        by_timer = sorted(panes, key=lambda p: p.waiting)
        by_screen = sorted(panes, key=lambda p: p.wall_end)
        if [p.side for p in by_timer] == [p.side for p in by_screen] or abs(panes[0].waiting - panes[1].waiting) < 1e-6:
            return "start"
        return "cut"

    def race(self, segment: dict, index: int) -> SegmentPlan:
        comparison_id, task_id = segment["comparison"], segment["task"]
        task = self.results["comparisons"].get(comparison_id, {}).get("tasks", {}).get(task_id)
        if not task:
            raise ComposeError(f"Race {segment['id']}: no results for {comparison_id} {task_id}")
        sides = [task["left"], task["right"]]
        if any(s["status"] in (1, 3) for s in sides) or any(s["status"] == 0 and not s.get("median_run")
                                                              for s in sides):
            return self.neutral_race(segment, index, task)
        folder = self.results["comparisons"][comparison_id].get("result_folder")
        panes = [PaneRun.load(self.config, comparison_id, task_id, name, s,
                              s["median_run"] if s["status"] == 0 else s["timeout_run"], folder, self.labels)
                 for name, s in zip(("left", "right"), sides)]
        footage_allowed = self.footage_allowed(comparison_id)
        mode = self.race_mode(panes)
        L = self.layout
        voice_before = self.voice_part(segment, "voice_before", 0.2)
        voice_after = self.voice_part(segment, "voice_after", 0)
        hook = max(1.0, (voice_before.duration + self.settings.short["hook_pad_s"] + 0.2) if voice_before else 1.0)
        hold = max(float(self.settings.short["min_hold_s"]),
                   (voice_after.duration + self.settings.short["hold_pad_s"] + 0.2) if voice_after else 0)
        lengths = [p.length(mode) for p in panes]
        budget = self.settings.budget(comparison_id)
        microsoft = any(p.microsoft for p in panes)
        timer_race = (not footage_allowed) or (microsoft and max(lengths) > budget and
                                               not self.settings.short.get("microsoft_timelapse"))
        plan = RacePlan.for_budget(hook, float(self.settings.short["countdown_s"]), min(lengths), max(lengths), budget,
                                   list(self.settings.short["timelapse_factors"]),
                                   float(self.settings.short["realtime_start_s"]),
                                   float(self.settings.short["realtime_after_fast_s"]), hold, timer_race)
        title = (segment.get("supers") or [None])[0] or self.scenario_title(task)
        background = self.cards.race_background(self.work / f"{index:03d}-bg.png", L, title, panes[0].label,
                                                panes[1].label, self.footnote(segment, mode))
        inputs = FilterInputs()
        bg = inputs.add("-loop", "1", "-framerate", str(self.fps), "-t", f"{plan.total + 1:.3f}", "-i", str(background))
        chains = [f"[{bg}:v]fps={self.fps},trim=duration={plan.total:.4f},setpts=PTS-STARTPTS[bg]"]
        card_lines = lambda p: [p.name, p.label.split(" · ", 1)[-1]]
        for n, pane in enumerate(panes):
            source = inputs.add("-i", str(pane.capture))
            hide_footage = (pane.microsoft and not footage_allowed)
            chains += self.pane_chain(n, source, pane, mode, plan, hide_footage, inputs, card_lines(pane))
        chains.append(f"[bg][p0]overlay=x=0:y={L.pane_top}:shortest=1[c0]")
        chains.append(f"[c0][p1]overlay=x={L.pane_w}:y={L.pane_top}:shortest=1[c1]")
        draw = self.race_overlays(segment, index, panes, plan, mode, title)
        chains.append(f"[c1]{','.join(draw)}[out]")
        script = self.work / f"{index:03d}-race.txt"
        script.write_text(";\n".join(chains), encoding="utf-8")
        out = self.work / f"{index:03d}-{segment['id']}.mkv"
        self.run_ffmpeg([*inputs.args, "-/filter_complex", str(script), "-map", "[out]", *self.lossless, str(out)])
        voice = [v for v in (voice_before,) if v]
        countdown = self.countdown_part(plan.go)
        if countdown:
            voice.append(countdown)
        start_sfx = self.sfx_part("sfx_start", plan.go)
        if start_sfx:
            voice.append(start_sfx)
        for pane in panes:
            finish_sfx = None if pane.timed_out else self.sfx_part("sfx_finish", plan.out(pane.length(mode)))
            if finish_sfx:
                voice.append(finish_sfx)
        during = self.voice_part(segment, "voice_during", plan.t0)
        if during and during.duration <= min(lengths):
            voice.append(during)
        if voice_after:
            voice_after.start = plan.hold_start + 0.2
            voice.append(voice_after)
        info = {"comparison": comparison_id, "task": task_id, "mode": mode, "timer_race": plan.timer_race,
                "pre_s": plan.t0, "hook_s": plan.hook, "timelapse": {"start": plan.t1, "end": plan.t2,
                                                                    "factor": plan.factor, "real_start": plan.a},
                "budget_s": budget, "hold_start_s": plan.hold_start,
                "panes": {p.side: {"run": str(p.capture.parent), "relative_end_s": p.length(mode),
                                   "waiting_s": p.waiting, "timed_out": p.timed_out,
                                   "done_at_output_s": plan.out(p.length(mode)), "microsoft": p.microsoft}
                          for p in panes}}
        self.check_order(info)
        return SegmentPlan(segment["id"], "race", plan.total, out, voice, info)

    @staticmethod
    def check_order(info: dict):
        panes = list(info["panes"].values())
        finished = [p for p in panes if not p["timed_out"]]
        by_screen = sorted(finished, key=lambda p: p["done_at_output_s"])
        by_timer = sorted(finished, key=lambda p: p["waiting_s"])
        if len(finished) == 2 and by_screen != by_timer and abs(by_timer[0]["waiting_s"] - by_timer[1]["waiting_s"]) > 1e-6:
            raise ComposeError(f"Race {info['comparison']} {info['task']}: the panes finish on screen in another order "
                               f"than their timers stop")

    def pane_chain(self, n: int, source: int, pane: PaneRun, mode: str, plan: RacePlan, hide_footage: bool,
                   inputs: FilterInputs, card: list[str]) -> list[str]:
        L = self.layout
        c = pane.crop
        length = pane.length(mode)
        crop = f"crop={c.width}:{c.height}:{c.x}:{c.y}"
        chains = []
        if plan.timer_race or hide_footage:
            card_png = self.cards.pane_card(self.work / f"pane-{n}-{source}.png", L.pane_w, L.pane_h, card)
            card_input = inputs.add("-loop", "1", "-framerate", str(self.fps), "-t", f"{plan.total + 1:.3f}", "-i",
                                    str(card_png))
            visible = 0.0 if hide_footage else min(plan.a, length)
            card_until = plan.hold_start if not hide_footage else plan.total
            pieces = []
            if visible > 0:
                chains.append(f"[{source}:v]trim=start={pane.first:.4f}:end={pane.first + visible:.4f},"
                              f"setpts=PTS-STARTPTS,{crop},fps={self.fps},"
                              f"tpad=start_mode=clone:start_duration={plan.t0:.4f}[p{n}a]")
                pieces.append(f"[p{n}a]")
            card_start = plan.t0 + visible if visible > 0 else 0.0
            chains.append(f"[{card_input}:v]fps={self.fps},trim=duration={card_until - card_start:.4f},"
                          f"setpts=PTS-STARTPTS[p{n}b]")
            pieces.append(f"[p{n}b]")
            if not hide_footage:
                end = min(pane.steps[-1][0] + pane.steps[-1][1], pane.recording_end)
                chains.append(f"[{source}:v]trim=start={max(end - 2.0 / self.fps, 0):.4f}:end={end:.4f},"
                              f"setpts=PTS-STARTPTS,{crop},fps={self.fps},"
                              f"tpad=stop_mode=clone:stop_duration={plan.hold + 1:.4f},"
                              f"trim=duration={plan.hold:.4f}[p{n}c]")
                pieces.append(f"[p{n}c]")
            chains.append(f"{''.join(pieces)}concat=n={len(pieces)}:v=1:a=0,trim=duration={plan.total:.4f},"
                          f"setpts=PTS-STARTPTS[p{n}]")
            return chains
        play = length
        if pane.microsoft and not plan.lapsed:
            play = max(length, plan.s)
        pieces = pane.pieces(mode, play)
        labels = []
        for k, (start, end) in enumerate(pieces):
            chains.append(f"[{source}:v]trim=start={start:.4f}:end={end + 0.5 / self.fps:.4f},setpts=PTS-STARTPTS,"
                          f"{crop},fps={self.fps}[p{n}w{k}]")
            labels.append(f"[p{n}w{k}]")
        whole = f"p{n}w"
        chains.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0[{whole}]" if len(labels) > 1 else
                      f"{labels[0]}null[{whole}]")
        if plan.lapsed:
            chains.append(f"[{whole}]split=2[{whole}0][{whole}1]")
            chains.append(f"[{whole}0]trim=end={plan.a:.4f},setpts=PTS-STARTPTS[{whole}a]")
            chains.append(f"[{whole}1]trim=start={plan.a:.4f},setpts=(PTS-STARTPTS)/{plan.factor},fps={self.fps}"
                          f"[{whole}b]")
            chains.append(f"[{whole}a][{whole}b]concat=n=2:v=1:a=0[{whole}t]")
            whole = f"{whole}t"
        chains.append(f"[{whole}]tpad=start_mode=clone:start_duration={plan.t0:.4f}:stop_mode=clone:"
                      f"stop_duration={plan.total:.4f},trim=duration={plan.total:.4f},setpts=PTS-STARTPTS[p{n}]")
        return chains

    def race_overlays(self, segment: dict, index: int, panes: list[PaneRun], plan: RacePlan, mode: str,
                      title: str) -> list[str]:
        L, scale = self.layout, self.layout.scale
        draw = []
        real = plan.real_expression()
        timer_size, badge_size = int(round(48 * scale)), int(round(30 * scale))
        done_file = self.text_file(f"{index:03d}-done", self.t("done"))
        limit_file = self.text_file(f"{index:03d}-limit", self.settings.label(self.language, "time_limit"))
        label_y = f"{L.label_top}+({L.label_h}-th)/2"
        for n, pane in enumerate(panes):
            x_right = n * L.pane_w + L.pane_w - int(24 * scale)
            value = pane.timer_expression(real, mode)
            draw += self.timer_drawtexts(value, f"{x_right}-tw", label_y, timer_size)
            done_at = plan.out(pane.length(mode))
            badge_file = limit_file if pane.timed_out else done_file
            color = "0xB9770E" if pane.timed_out else "0x27AE60"
            draw.append(self.drawtext(textfile=badge_file, size=badge_size, bold=True, box=color,
                                      x=f"{x_right - int(250 * scale)}-tw", y=label_y,
                                      enable=f"gte(t,{done_at:.4f})"))
            side = self.results["comparisons"][segment["comparison"]]["tasks"][segment["task"]][pane.side]
            final = (self.t("not_done", limit=SpokenDuration.text(side["timeout_s"], self.language))
                     if side["status"] == 2 else SpokenDuration.text(side["median_s"], self.language))
            final_file = self.text_file(f"{index:03d}-final-{n}", final)
            draw.append(self.drawtext(textfile=final_file, size=int(round(52 * scale)), bold=True,
                                      x=f"{n * L.pane_w}+({L.pane_w}-tw)/2", y=f"{L.hold_top + int(10 * scale)}",
                                      enable=f"gte(t,{plan.hold_start:.4f})"))
            for k, (start, end) in enumerate(pane.opening if pane.microsoft else []):
                text_file = self.text_file(f"{index:03d}-opening-{n}-{k}",
                                           self.settings.label(self.language, "opening_screen"))
                a, b = plan.out(start - pane.first), plan.out(end - pane.first)
                draw.append(f"drawbox=x={n * L.pane_w}:y={L.pane_top}:w={L.pane_w}:h={L.pane_h}:color=0x181E2C:t=fill:"
                            f"enable='between(t,{a:.4f},{b:.4f})'")
                draw.append(self.drawtext(textfile=text_file, size=int(round(40 * scale)),
                                          x=f"{n * L.pane_w}+({L.pane_w}-tw)/2", y=f"{L.pane_top}+{L.pane_h}/2",
                                          enable=f"between(t,{a:.4f},{b:.4f})"))
        countdown = self.settings.short["countdown_text"].get(self.language, "Go!")
        go_file = self.text_file(f"{index:03d}-go", countdown)
        draw.append(self.drawtext(textfile=go_file, size=int(round(110 * scale)), bold=True,
                                  x="(w-tw)/2", y=f"{L.hold_top}+({L.hold_h}-th)/2",
                                  enable=f"between(t,{plan.go:.4f},{plan.t0:.4f})"))
        if plan.lapsed:
            kind = "timer_race" if plan.timer_race else "timelapse"
            for key, enable in ((kind, f"between(t,{plan.t1:.4f},{plan.t2:.4f})"),
                                (f"{kind}_after", f"gt(t,{plan.t2:.4f})")):
                label = self.settings.label(self.language, key, factor=plan.factor)
                lapse_file = self.text_file(f"{index:03d}-{key}", label)
                draw.append(self.drawtext(textfile=lapse_file, size=int(round(40 * scale)), bold=True,
                                          box="0xE67E22" if key == kind else "0x5D6D7E",
                                          x="(w-tw)/2", y=f"{int(88 * scale)}", enable=enable))
        for k, line in enumerate((segment.get("supers") or [])[1:4]):
            line_file = self.text_file(f"{index:03d}-super-{k}", line)
            draw.append(self.drawtext(textfile=line_file, size=int(round((38 if k == 0 else 32) * scale)),
                                      x="(w-tw)/2", y=f"{L.hold_top + int((78 + 38 * k) * scale)}",
                                      enable=f"gte(t,{plan.hold_start:.4f})"))
        return draw

    def neutral_race(self, segment: dict, index: int, task: dict) -> SegmentPlan:
        """Failed or differing results: no race footage, a neutral card with the title and the spoken line."""
        L = self.layout
        voice_before = self.voice_part(segment, "voice_before", 0.2)
        voice_after = self.voice_part(segment, "voice_after", 0)
        title = (segment.get("supers") or [None])[0] or self.scenario_title(task)
        hook = (voice_before.duration + 0.6) if voice_before else 1.0
        hold = max(float(self.settings.short["min_hold_s"]),
                   (voice_after.duration + self.settings.short["hold_pad_s"] + 0.2) if voice_after else 0)
        labels = [self.labels.bar(segment["comparison"], name, task[name], with_os=False) for name in ("left", "right")]
        background = self.cards.race_background(self.work / f"{index:03d}-bg.png", L, title, labels[0], labels[1],
                                                self.footnote(segment, "start"))
        card = self.cards.pane_card(self.work / f"{index:03d}-neutral.png", L.width, L.pane_h,
                                    [title, segment.get("voice_after") or self.t("no_measurement")])
        duration = hook + hold
        out = self.work / f"{index:03d}-{segment['id']}.mkv"
        self.run_ffmpeg(["-loop", "1", "-framerate", str(self.fps), "-t", f"{duration:.3f}", "-i", str(background),
                         "-loop", "1", "-framerate", str(self.fps), "-t", f"{duration:.3f}", "-i", str(card),
                         "-filter_complex", f"[0:v][1:v]overlay=x=0:y={L.pane_top}[out]", "-map", "[out]",
                         *self.lossless, str(out)])
        voice = [v for v in (voice_before,) if v]
        if voice_after:
            voice_after.start = hook
            voice.append(voice_after)
        return SegmentPlan(segment["id"], "race", duration, out, voice,
                           {"comparison": segment["comparison"], "task": segment["task"], "neutral": True})

    def text_segment(self, segment: dict, index: int) -> SegmentPlan:
        voice = self.voice_part(segment, "voice", 0.2)
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
        corpus = self.results.get("corpus") or {}
        footer = list(segment.get("supers") or [])
        footer.append(" · ".join(str(x) for x in (
            self.t("median_of", runs=self.results["runs"]["measured"]),
            f"{values.text.get('env.messages', '–')} emails" if corpus else None,
            env.get("os"), env.get("cpu"), env.get("ram"), (env.get("display") or {}).get("resolution"),
            f"RTT {values.text.get(f'env.{comparison_id}.rtt_ms', '–')} ms",
            (env.get("server") or {}).get("name"), (env.get("server") or {}).get("version"), env.get("date")) if x))
        footer.append(f"{self.t('self_test')} · {self.t('how_tested')}")
        left_name = self.labels.named(comparison_id, "left", any_task["left"])
        right_name = self.labels.named(comparison_id, "right", any_task["right"])
        image = self.cards.result_card(self.work / f"{index:03d}-result.png", self.t("results"), left_name, right_name,
                                       rows, footer, {"task": self.t("task"), "ratio": self.t("ratio"),
                                                      "actions": self.t("actions")})
        voice = self.voice_part(segment, "voice", 0.2)
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

    def length_limits(self) -> list | None:
        if not self.variant:
            return None
        if self.variant.startswith("combined"):
            return self.settings.combined_length_s
        return self.settings.video_length_s

    def publication(self) -> dict:
        """May this variant be published? If not, the first variant of its `publish_instead` chain whose own
        condition holds (or none). With publication gates in compose.json, a variant without its own gate is never
        published."""
        condition = self.settings.publish_when.get(self.variant) if self.variant else None
        ungated = bool(self.variant and self.settings.publish_when and condition is None)
        allowed = not ungated and self.condition(condition)
        chain = self.settings.instead(self.variant) if self.variant and not allowed else []
        gates = self.settings.publish_when
        instead = next((v for v in chain if (v in gates or not gates) and self.condition(gates.get(v))), None)
        return {"variant": self.variant, "publish_when": condition, "allowed": allowed, "chain": chain,
                "instead": [instead] if instead else [], "ungated": ungated}

    def compose(self) -> dict:
        if self.work.exists():
            shutil.rmtree(self.work)
        self.work.mkdir(parents=True)
        plans: list[SegmentPlan] = []
        for index, segment in enumerate(self.segments()):
            self.progress(f"  segment {segment['id']} ({segment['kind']})")
            if segment["kind"] == "race":
                plans.append(self.race(segment, index))
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
        limits = self.length_limits()
        if limits and not float(limits[0]) - 0.05 <= total <= float(limits[1]) + 0.05:
            raise ComposeError(f"Variant {self.variant}: {total:.1f} s, outside {limits[0]}–{limits[1]} s "
                               f"(compose.json)")
        audio = self.mix_audio(voice_parts, total)
        (self.out_dir / "timeline.json").write_text(json.dumps(
            {"language": self.language, "duration_s": total, "width": self.layout.width,
             "height": self.layout.height, "fps": self.fps, "segments": timeline,
             "audio": str(audio) if audio else None, "publication": self.publication(),
             "facts": {"files": list(self.results.get("facts_files") or []),
                       "person_set_facts": self.settings.person_set_facts},
             "music": self.music_record()}, indent=2, ensure_ascii=False), encoding="utf-8")
        SubtitleWriter([p for p in voice_parts if p.subtitled]).write(self.out_dir / "subtitles.vtt",
                                                                      self.out_dir / "subtitles.srt")
        self.write_voice_script(voice_parts)
        return {"master": str(master), "audio": str(audio) if audio else None, "duration_s": total,
                "segments": len(plans), "publication": self.publication()}

    def clip_duration(self, path: Path) -> float:
        out = subprocess.run([self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                              str(path)], capture_output=True, text=True, check=True).stdout
        return float(out.strip())

    def music_record(self) -> dict | None:
        if not self.music:
            return None
        license_info = dict(self.compose_config.get("music_license") or {})
        missing = [k for k in ("title", "author", "license", "url", "content_id") if not license_info.get(k)]
        if missing:
            raise ComposeError(f"compose.music is set but compose.music_license lacks {', '.join(missing)} "
                               f"(title, author, license, url, content_id: who registered the track in Content ID)")
        return {"file": str(self.music), **license_info}

    def mix_audio(self, parts: list[VoicePart], total: float) -> Path | None:
        recorded = [p for p in parts if p.file]
        if not recorded and not self.music:
            return None
        self.music_record()
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
            compose = self.compose_config
            volume = float(compose.get("music_volume_db", -16))
            fade = min(float(compose.get("music_fade_out_s", 1.5)), total / 2)
            chains.append(f"[{base + 1}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},"
                          f"volume={volume}dB,afade=t=out:st={total - fade:.3f}:d={fade:.3f}[music]")
            chains.append("[voice]asplit=2[vk][vm]")
            chains.append("[music][vk]sidechaincompress=threshold=0.03:ratio=8:attack=50:release=300[ducked]")
            chains.append("[ducked][vm]amix=inputs=2:normalize=0:duration=first[mix]")
            final = "[mix]"
        else:
            final = "[voice]"
        self.run_ffmpeg([*inputs, "-filter_complex", ";".join(chains), "-map", final, "-t", f"{total:.3f}",
                         "-c:a", "pcm_s24le", str(out)])
        return out

    def write_voice_script(self, parts: list[VoicePart]):
        spoken = [p for p in parts if p.subtitled]
        direction = self.settings.voice_direction
        entries = [{"file": f"{p.segment}.wav" if p.part == "voice" else f"{p.segment}.{p.part.replace('voice_', '')}.wav",
                    "segment": p.segment, "part": p.part, "text": p.text, "start_s": round(p.start, 3),
                    "estimated_s": round(p.duration, 2), "recorded": bool(p.file),
                    **({"direction": direction[p.segment]} if p.segment in direction else {})} for p in spoken]
        countdown = self.settings.short.get("countdown_voice")
        if countdown:
            entries.append({"file": Path(countdown).name, "segment": "countdown", "part": "countdown",
                            "text": self.settings.short["countdown_text"].get(self.language, "Go!"),
                            "recorded": bool(self.voice_dir and (self.voice_dir / self.language /
                                                                 Path(countdown).name).exists())})
        (self.out_dir / "voice-script.json").write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                                                         encoding="utf-8")
        lines = [f"# Voice script ({self.language})", "",
                 "`bench.py voice` synthesizes each line into `voice/<lang>/<file>` (or record them); compose again "
                 "afterwards: the composer then uses the real lengths.", ""]
        lines += [f"- `{e['file']}`" + (f" at {e['start_s']:.1f} s (≈ {e['estimated_s']:.1f} s)" if "start_s" in e else "")
                  + f": {e['text']}" for e in entries]
        (self.out_dir / "voice-script.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


class ValuesBuilder:
    """All placeholder values of the narration and the method texts, from results.json, the environment records,
    the corpus, the server-log evidence and the person-set facts file."""

    def __init__(self, config, results: dict, language: str, facts: dict, allowed_facts: dict | None = None):
        self.config = config
        self.results = results
        self.language = language
        self.facts = PersonFacts(facts, allowed_facts, ", ".join(results.get("facts_files") or []) or "facts.json")

    def build(self) -> NarrationValues:
        facts = self.facts.check().env()
        values = NarrationValues(self.language)
        values.set_count("runs", int(self.results["runs"]["measured"]))
        for key, value in (self.results.get("corpus") or {}).items():
            if isinstance(value, (int, float)) or value is None:
                values.set_count(f"env.{key}", value)
        limits = set()
        for comparison_id, comparison in self.results["comparisons"].items():
            env = (self.results.get("environment") or {}).get(comparison_id, {})
            for key in ("date", "os", "cpu", "ram", "display", "server", "rtt_ms"):
                value = env.get(key)
                if key == "server" and isinstance(value, dict):
                    value = value.get("version")
                elif isinstance(value, dict):
                    value = value.get("resolution") or value.get("version") or next(iter(value.values()), None)
                if value is not None:
                    values.set_text(f"env.{comparison_id}.{key}", str(value), value)
            evidence = (comparison.get("evidence") or {}).get("values") or {}
            for key, value in evidence.items():
                self.set_fact(values, f"env.{comparison_id}.{key}", value)
            for task_id, task in comparison["tasks"].items():
                for side in ("left", "right"):
                    s = task[side]
                    values.set_seconds(f"t.{comparison_id}.{side}.{task_id}", s.get("median_s"))
                    values.set_duration(f"time.{comparison_id}.{side}.{task_id}", s.get("median_s"))
                    values.set_seconds(f"tmin.{comparison_id}.{side}.{task_id}", s.get("min_s"))
                    values.set_seconds(f"tmax.{comparison_id}.{side}.{task_id}", s.get("max_s"))
                    values.set_count(f"status.{comparison_id}.{side}.{task_id}", s.get("status"))
                    values.set_count(f"actions.{comparison_id}.{side}.{task_id}", s.get("actions"))
                    first = (s.get("first_s") or {}).get("median_s")
                    values.set_seconds(f"tfirst.{comparison_id}.{side}.{task_id}", first)
                    values.set_text(f"note.{comparison_id}.{side}.{task_id}", self.note(s))
                    values.set_text(f"app.{comparison_id}.{side}", f"{s['name']} {s.get('version') or ''}".strip())
                    if s.get("timeout_s"):
                        limits.add(float(s["timeout_s"]))
                values.set_ratio(f"ratio.{comparison_id}.{task_id}", task.get("ratio"))
        if len(limits) == 1:
            limit = limits.pop()
            values.set_count("env.timeout_s", int(limit))
            values.set_duration("time.limit", limit)
        for name, value in facts.items():
            self.set_fact(values, f"env.{name}", value)
        return values

    def set_fact(self, values: NarrationValues, name: str, value):
        if value is None:
            return
        if isinstance(value, bool):
            value = int(value)
        if isinstance(value, int):
            values.set_count(name, value)
        elif isinstance(value, float):
            values.set_text(name, values.number(value, 1 if name.endswith(".cpu_pressure") else 2), value)
        else:
            values.set_text(name, str(value), str(value))

    def note(self, side: dict) -> str:
        de = self.language == "de"
        if side.get("timed_out_runs") and side.get("status") == 0:
            limit = SpokenDuration.text(side["timeout_s"], self.language)
            return (f"; {side['timed_out_runs']} von {len(side['runs'])} Läufen nicht fertig in {limit}" if de else
                    f"; {side['timed_out_runs']} of {len(side['runs'])} runs not done in {limit}")
        return ""


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
