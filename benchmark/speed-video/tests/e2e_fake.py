#!/usr/bin/env python3
"""End-to-end test of the whole pipeline under Xvfb with the synthetic app (tests/fakeapp.py).

Starts its own Xvfb, records 1 warm-up + 5 measured runs per app and task, analyzes them, checks every measured
step against the fake app's own log of when it drew its final state (±1 frame at 60 fps), checks the median-run
selection, composes a side-by-side clip with a small narration (with `when` alternatives and test-tone voice
files), encodes WebM, MP4 and the YouTube master, and verifies them with ffprobe.

Usage: e2e_fake.py --work <dir> [--display :93] [--runs 5] [--keep]
Needs ffmpeg, ffprobe, Xvfb, xdotool on PATH (or --tools <dir>), and numpy, Pillow, PyYAML, python-xlib.
"""

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from benchlib.config import Config  # noqa: E402
from benchlib.driver import EventLog  # noqa: E402
from benchlib.stages import Calibrator, Pipeline  # noqa: E402
from benchlib.video import VideoFile  # noqa: E402

FRAME = 1 / 60

APPS = {
    "fake-left": {"title": "Fake Mail L", "steps": [
        {"key": "Return", "delay_s": 0.45, "feedback": "spinner", "progressive": 3},
        {"key": "F5", "delay_s": 1.6, "feedback": "loading", "progressive": 1},
        {"key": "End", "delay_s": 0.30, "feedback": "none", "progressive": 5}]},
    "fake-right": {"title": "Fake Mail R", "background": [250, 244, 240], "steps": [
        {"key": "Return", "delay_s": 1.35, "feedback": "spinner", "progressive": 3},
        {"key": "F5", "delay_s": 2.3, "feedback": "loading", "progressive": 1},
        {"key": "End", "delay_s": 0.85, "feedback": "none", "progressive": 5}]},
}

SCENARIOS = {
    "TF1": """
id: TF1
title: {en: "Open a folder", de: "Ordner öffnen"}
description: "Spinner, then progressive rendering"
apps:
  fake-left: &app
    prepare: [launch, {wait_settled: {quiet_s: 0.8, timeout_s: 20}}]
    steps:
      - name: open
        actions: [{key: Return}]
  fake-right: *app
""",
    "TF2": """
id: TF2
title: {en: "Search, then jump to the end", de: "Suchen, dann ans Ende springen"}
description: "Typing (not timed), a static Loading state longer than the quiet period, then progressive rendering"
apps:
  fake-left: &app
    prepare: [launch, {wait_settled: {quiet_s: 0.8, timeout_s: 20}}]
    steps:
      - name: search
        actions: [{type: "kumquat"}, {key: F5}]
      - name: jump
        actions: [{key: End}]
  fake-right: *app
""",
}

NARRATION = {
    "version": 1, "language": "en", "words_per_minute": 150,
    "segments": [
        {"id": "intro", "kind": "fixed", "duration_s": 2.5, "voice": "Two fake apps. {{runs}} runs each.",
         "visual": "", "supers": ["Pipeline test", "{{env.messages}} messages in the test corpus"], "audio": ""},
        {"id": "cf-tf1", "kind": "race", "comparison": "CF", "task": "TF1", "when": "missing(t.CF.left.TF1)",
         "voice_before": "Missing.", "voice_after": "No measurement.", "visual": "", "supers": ["Open a folder"],
         "audio": ""},
        {"id": "cf-tf1", "kind": "race", "comparison": "CF", "task": "TF1", "when": "ratio.CF.TF1 >= 2",
         "voice_before": "Open a folder.", "voice_during": "Go.",
         "voice_after": "Left {{t.CF.left.TF1}} seconds, right {{t.CF.right.TF1}}. Factor {{ratio.CF.TF1}}.",
         "visual": "", "supers": ["Open a folder", "Actions: {{actions.CF.left.TF1}} / {{actions.CF.right.TF1}}"],
         "audio": ""},
        {"id": "cf-tf1", "kind": "race", "comparison": "CF", "task": "TF1", "voice_before": "Open a folder.",
         "voice_after": "Close: {{t.CF.left.TF1}} and {{t.CF.right.TF1}}.", "visual": "", "supers": ["Open a folder"],
         "audio": ""},
        {"id": "cf-tf2", "kind": "race", "comparison": "CF", "task": "TF2", "voice_before": "Search, then jump.",
         "voice_after": "{{t.CF.left.TF2}} versus {{t.CF.right.TF2}} seconds.", "visual": "",
         "supers": ["Search, then jump to the end"], "audio": ""},
        {"id": "result", "kind": "card", "card": "result", "comparison": "CF", "duration_s": 3.0,
         "voice": "All tasks on one card.", "visual": "", "supers": ["Fake comparison · {{env.CF.os}}"], "audio": ""},
    ]}


class E2E:
    def __init__(self, work: Path, display: str, runs: int, tools: Path | None):
        self.work = work
        self.display = display
        self.runs = runs
        self.tools = tools
        self.xvfb = None
        self.failures: list[str] = []
        self.report: dict = {}

    def check(self, condition: bool, message: str):
        print(("  ok   " if condition else "  FAIL ") + message)
        if not condition:
            self.failures.append(message)

    def env(self) -> dict:
        env = dict(os.environ)
        if self.tools:
            env["PATH"] = f"{self.tools}{os.pathsep}{env['PATH']}"
        env["DISPLAY"] = self.display
        return env

    def start_xvfb(self):
        number = self.display.lstrip(":")
        lock = Path(f"/tmp/.X{number}-lock")
        if lock.exists():
            raise SystemExit(f"Display {self.display} is in use ({lock}); pick another with --display")
        self.xvfb = subprocess.Popen(["Xvfb", self.display, "-screen", "0", "1024x640x24", "-nolisten", "tcp"],
                                     env=self.env(), stdout=subprocess.DEVNULL, stderr=open(self.work / "xvfb.log", "w"))
        for _ in range(50):
            if Path(f"/tmp/.X11-unix/X{number}").exists():
                return
            time.sleep(0.1)
        raise SystemExit("Xvfb didn't start")

    def stop_xvfb(self):
        if self.xvfb:
            self.xvfb.terminate()
            self.xvfb.wait(10)

    def write_files(self) -> Path:
        (self.work / "scenarios").mkdir(parents=True, exist_ok=True)
        for task, text in SCENARIOS.items():
            (self.work / "scenarios" / f"{task}.yaml").write_text(text)
        python = sys.executable
        apps = {}
        for app_id, app_config in APPS.items():
            path = self.work / f"{app_id}.json"
            path.write_text(json.dumps(app_config))
            apps[app_id] = {
                "name": "Fake L" if app_id == "fake-left" else "Fake R", "version": "1.0",
                "protocol": "JMAP" if app_id == "fake-left" else "IMAP", "os": "Linux",
                "launch": [python, str(HERE / "fakeapp.py"), "--config", str(path),
                           "--log", "{workdir}/truth-" + app_id + ".jsonl", "--geometry", "640x480+0+0"],
                "window": {"class": "FakeMail", "timeout_s": 20},
                "close": {"key": "ctrl+q", "timeout_s": 10},
            }
        voice_dir = self.work / "voice" / "en"
        voice_dir.mkdir(parents=True, exist_ok=True)
        for name, seconds in (("intro", 1.6), ("cf-tf1.before", 1.2), ("cf-tf1.after", 2.0), ("result", 1.0)):
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                            f"sine=frequency=440:sample_rate=48000:duration={seconds}", "-af", "volume=-12dB",
                            str(voice_dir / f"{name}.wav")], check=True, env=self.env())
        (self.work / "narration.en.json").write_text(json.dumps(NARRATION, indent=2))
        cpus = str((os.cpu_count() or 2) - 1)
        config = {
            "workdir": str(self.work / "work"), "scenario_dir": str(self.work / "scenarios"),
            "display": {"platform": "linux", "display": self.display,
                        "app_region": {"x": 0, "y": 0, "width": 640, "height": 480},
                        "marker": {"cell": 10, "position": "below", "gap": 4}},
            "capture": {"fps": 60, "cpus": cpus, "draw_mouse": False, "live_scale": 4},
            "settle": {"pixel_threshold": 8, "min_changed_pixels": 120, "quiet_s": 1.0, "live_quiet_s": 1.3,
                       "step_timeout_s": 30, "reference_quiet_s": 2.6, "reference_tolerance": 0.02},
            "runs": {"measured": self.runs, "warmup": 1, "retries": 1},
            "server": {"name": "none", "version": "n/a (fake app test)", "snapshot": {"method": "none"}},
            "corpus": {"folders": [{"name": "Inbox", "count": 10, "role": "inbox"}], "planted": []},
            "driver": {"type_delay_ms": 30},
            "apps": apps,
            "comparisons": {"CF": {"os": "Linux", "left": "fake-left", "right": "fake-right",
                                   "tasks": ["TF1", "TF2"]}},
            "deviations": ["Test only: synthetic apps"],
            "compose": {"voice_dir": str(self.work / "voice"), "countdown_s": 1.5, "min_hold_s": 1.5},
            "encode": {"youtube_height": 1320, "threads": 4},
        }
        path = self.work / "config.yaml"
        import yaml
        path.write_text(yaml.safe_dump(config, sort_keys=False))
        return path

    def truth(self, run_dir: Path, app_id: str) -> dict:
        """Ground truth per measured step: fake app's final draw time minus the driver's input event time."""
        events = EventLog.read(run_dir / "log.jsonl")
        starts = [e for e in events if e["type"] == "step_start"]
        t_open = next(e["t"] for e in events if e["type"] == "restored")
        t_close = next(e["t"] for e in events if e["type"] == "closed")
        truth_log = self.work / "work" / f"truth-{app_id}.jsonl"
        app_events = [json.loads(line) for line in truth_log.read_text().splitlines()]
        app_events = [e for e in app_events if t_open <= e["t"] <= t_close]
        finals = [e for e in app_events if e["event"] == "final_drawn"]
        result = {}
        for start in starts:
            final = next(e for e in finals if e["t"] > start["t"])
            result[start["step"]] = final["t"] - start["t"]
        return result

    def run(self):
        if self.work.exists():
            shutil.rmtree(self.work)
        self.work.mkdir(parents=True)
        if self.tools:
            os.environ["PATH"] = f"{self.tools}{os.pathsep}{os.environ['PATH']}"
        self.start_xvfb()
        try:
            config = Config.load(self.write_files())
            pipeline = Pipeline(config)
            started = time.monotonic()
            print("calibrate references (long quiet period)")
            saved = Calibrator(pipeline).references("CF")
            self.check(len(saved) == 6, f"{len(saved)} reference images saved (6 expected)")
            print(f"run 1 warm-up + {self.runs} measured runs per app and task, interleaved")
            pipeline.run("CF", None, True, self.runs, 1)
            record_s = time.monotonic() - started
            print("analyze")
            results = pipeline.analyze("CF")
            self.verify_measurements(config, results)
            print("compose")
            composed = pipeline.compose(["CF"], "en", str(self.work / "narration.en.json"), None, "e2e")
            self.verify_compose(config, composed)
            print("encode")
            pipeline.encode("e2e", "en", None)
            verified = pipeline.verify("e2e", "en")
            for kind, report in verified.items():
                if isinstance(report, dict):
                    bad = {k: v for k, v in report["checks"].items() if not v["ok"]}
                    self.check(report["ok"], f"{kind}: " + (", ".join(f"{k}={v['actual']}" for k, v in
                                                                     report["checks"].items()) if not bad else
                                                          f"failed {bad}"))
            self.verify_timelapse(config, pipeline)
            self.report["recording_s"] = round(record_s, 1)
        finally:
            self.stop_xvfb()
        (self.work / "e2e-report.json").write_text(json.dumps(self.report, indent=2))
        print(json.dumps(self.report, indent=2))
        print("PASSED" if not self.failures else f"FAILED: {len(self.failures)} checks")
        return not self.failures

    def verify_measurements(self, config, results: dict):
        comparison = results["comparisons"]["CF"]
        errors = []
        per_step = {}
        for task_id, task in comparison["tasks"].items():
            for side in ("left", "right"):
                s = task[side]
                self.check(s["measured_runs"] == self.runs, f"{task_id} {side}: {s['measured_runs']} measured runs")
                self.check(s["warmups_discarded"] == ["warmup-1"], f"{task_id} {side}: warm-up discarded")
                totals = sorted(r["total_s"] for r in s["runs"])
                median_total = next(r["total_s"] for r in s["runs"] if r["run"] == s["median_run"])
                self.check(abs(median_total - statistics.median(totals)) < 1e-9,
                           f"{task_id} {side}: median run {s['median_run']} has the median total {median_total:.3f} s")
                for r in s["runs"]:
                    run_dir = config.workdir / "runs" / "CF" / task_id / s["app"] / r["run"]
                    truth = self.truth(run_dir, s["app"])
                    analysis = json.loads((run_dir / "analysis.json").read_text())
                    for step in analysis["steps"]:
                        err = step["duration_s"] - truth[step["name"]]
                        errors.append(err)
                        per_step.setdefault(f"{task_id}/{side}/{step['name']}", []).append(
                            (round(step["duration_s"], 4), round(truth[step["name"]], 4), round(err * 1000, 1)))
                    self.check(analysis["clock_fit"]["max_abs_residual_s"] <= 1.5 * FRAME,
                               f"{task_id} {s['app']} {r['run']}: clock fit residual "
                               f"{analysis['clock_fit']['max_abs_residual_s'] * 1000:.1f} ms, "
                               f"{analysis['clock_fit']['points']} markers")
        worst = max(abs(e) for e in errors)
        self.check(worst <= FRAME + 0.002, f"all {len(errors)} measured steps within ±1 frame of the truth "
                                           f"(worst {worst * 1000:.1f} ms, mean {np.mean(errors) * 1000:+.1f} ms)")
        self.report["steps"] = {k: {"measured_s": [v[0] for v in vals], "truth_s": [v[1] for v in vals],
                                    "error_ms": [v[2] for v in vals]} for k, vals in per_step.items()}
        self.report["error_ms"] = {"worst_abs": round(worst * 1000, 2), "mean": round(float(np.mean(errors)) * 1000, 2),
                                   "stdev": round(float(np.std(errors)) * 1000, 2), "n": len(errors)}
        self.report["medians_s"] = {f"{t}/{side}": comparison["tasks"][t][side]["median_s"]
                                    for t in comparison["tasks"] for side in ("left", "right")}

    def verify_timelapse(self, config, pipeline):
        print("compose with a time-lapse (thresholds lowered for the short test races)")
        config.data["compose"].update({"timelapse_threshold_s": 1.5, "timelapse_keep_s": 0.5,
                                       "timelapse_max_compressed_s": 0.3})
        pipeline.compose(["CF"], "en", None, None, "lapse")
        timeline = json.loads((config.workdir / "compose" / "lapse-en" / "timeline.json").read_text())
        races = [s for s in timeline["segments"] if s["kind"] == "race"]
        lapsed = [r for r in races if r["timelapse"]["factor"] > 1]
        self.check(bool(lapsed), "time-lapse planned for the longer race(s): " + ", ".join(
            f"{r['task']} ×{r['timelapse']['factor']}" for r in lapsed))
        for race in lapsed:
            real = race["pre_s"] + max(p["relative_end_s"] for p in race["panes"].values())
            shown = race["panes"]["right"]["done_at_output_s"] if race["panes"]["right"]["relative_end_s"] >= \
                race["panes"]["left"]["relative_end_s"] else race["panes"]["left"]["done_at_output_s"]
            self.check(shown < real, f"{race['task']}: slower pane done at {shown:.2f} s in the video "
                                     f"instead of {real:.2f} s real time")
            clip = VideoFile(Path(race["clip"]), "ffmpeg", "ffprobe")
            frames = len(clip.frame_times())
            self.check(abs(frames / 60 - (race["end_s"] - race["start_s"])) < 0.1,
                       f"{race['task']}: time-lapse clip has {frames} frames at 60 fps")

    def verify_compose(self, config, composed: dict):
        out_dir = config.workdir / "compose" / "e2e-en"
        timeline = json.loads((out_dir / "timeline.json").read_text())
        kinds = [s["kind"] for s in timeline["segments"]]
        self.check(kinds == ["fixed", "title", "race", "title", "race", "card"], f"segments {kinds}")
        race = next(s for s in timeline["segments"] if s["kind"] == "race" and s["task"] == "TF1")
        after = next(v for v in race["voice"] if v["part"] == "voice_after")
        self.check(after["text"].startswith("Left ") and "Factor" in after["text"],
                   f"`when` alternative chosen: “{after['text']}”")
        self.check(after["file"] is not None, "recorded voice file used for voice_after")
        self.check(all(Path(p).exists() for p in (out_dir / "subtitles.vtt", out_dir / "subtitles.srt",
                                                  out_dir / "audio.wav")), "subtitles and audio written")
        video = VideoFile(Path(composed["master"]), "ffmpeg", "ffprobe")
        width, height = video.size
        self.check((width, height) == (1280, 660), f"master is {width}x{height}")
        # timer of the faster (left) pane: it must change while running and be frozen after its done time
        layout_scale = 0.5
        header, label = int(round(140 * layout_scale)), int(round(110 * layout_scale))
        timer_box = (header, header + label, 640 - 200, 640)
        pane = race["panes"]["left"]
        t_done = race["start_s"] + pane["done_at_output_s"]
        t_running = race["start_s"] + race["pre_s"] + 0.05
        times = video.frame_times()
        wanted = {"running_a": t_running, "running_b": t_running + 0.2, "done_a": t_done + 0.2, "done_b": t_done + 0.6}
        indexes = {k: int(np.searchsorted(times, v)) for k, v in wanted.items()}
        crops = {}
        for i, frame in enumerate(video.frames()):
            for k, idx in indexes.items():
                if i == idx:
                    crops[k] = frame[timer_box[0]:timer_box[1], timer_box[2]:timer_box[3]].astype(np.int16)
            if len(crops) == len(indexes):
                break
        self.check(np.abs(crops["running_a"] - crops["running_b"]).max() > 50, "left timer runs during the race")
        self.check(np.abs(crops["done_a"] - crops["done_b"]).max() == 0, "left timer is frozen after it's done")
        self.report["compose"] = {"duration_s": timeline["duration_s"], "segments": kinds}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True)
    parser.add_argument("--display", default=":93")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--tools", help="directory with ffmpeg, ffprobe, Xvfb, xdotool")
    args = parser.parse_args()
    ok = E2E(Path(args.work).resolve(), args.display, args.runs, Path(args.tools) if args.tools else None).run()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
