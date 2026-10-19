#!/usr/bin/env python3
"""End-to-end test of the whole pipeline under Xvfb with the synthetic app (tests/fakeapp.py).

Starts its own Xvfb and records 1 warm-up + N measured runs per app and task with the production capture settings
(pointer not recorded, parked outside the capture after each click; keys only after the focus check):
- TF1: spinner, then progressive rendering.
- TF2 (shaped like T1): a click and typing (not timed), a static "Loading…" longer than the quiet period, then a list
  whose rows are final early while a small counter keeps counting (the completion check region must find the real
  end), "first messages visible", the End verify check, a recorded tail.
- TF3: the right app doesn't finish within the task's time limit (censored runs, status 2).
It checks every measured step against the fake app's own log (±1 frame at 60 fps), the median-run choice, the
statuses, composes the short-video layout from a v2 narration (hook, "Go!", race budget, timer race for a pane
marked as a Microsoft app, time-limit race, neutral card, footnote, held times), a footage time-lapse, the
publication gate, and encodes and verifies WebM, MP4 and the YouTube master.

Usage: e2e_fake.py --work <dir> [--display :93] [--runs 5] [--tools <dir>]
"""

import argparse
import copy
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from benchlib.config import Config  # noqa: E402
from benchlib.driver import EventLog  # noqa: E402
from benchlib.encode import EncodeError  # noqa: E402
from benchlib.settle import ChangeSeries, SettleDetector, SettleParams  # noqa: E402
from benchlib.stages import Calibrator, Pipeline  # noqa: E402
from benchlib.video import VideoFile  # noqa: E402

FRAME = 1 / 60

APPS = {
    "fake-left": {"title": "Fake Mail L", "steps": [
        {"key": "Return", "delay_s": 0.45, "feedback": "spinner", "progressive": 3},
        {"key": "F5", "delay_s": 1.6, "feedback": "loading", "progressive": 1},
        {"key": "F7", "delay_s": 0.4, "feedback": "none", "progressive": 4, "counter_s": 1.2},
        {"key": "F6", "delay_s": 0.5, "feedback": "spinner", "progressive": 2}]},
    "fake-right": {"title": "Fake Mail R", "background": [250, 244, 240], "steps": [
        {"key": "Return", "delay_s": 1.35, "feedback": "spinner", "progressive": 3},
        {"key": "F5", "delay_s": 2.3, "feedback": "loading", "progressive": 1},
        {"key": "F7", "delay_s": 0.7, "feedback": "none", "progressive": 4, "counter_s": 2.0},
        {"key": "F6", "delay_s": 30, "feedback": "spinner", "progressive": 1}]},
}

REGIONS = {"list.count": {"x": 198, "y": 454, "width": 52, "height": 12},
           "list.top": {"x": 198, "y": 118, "width": 400, "height": 24},
           "list.bottom": {"x": 198, "y": 418, "width": 400, "height": 28}}

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
title: {en: "New account", de: "Neues Konto"}
description: "Click and typing (not timed), a static Loading state, then a list loaded in the background"
apps:
  fake-left: &app
    prepare: [launch, {wait_settled: {quiet_s: 0.8, timeout_s: 20}}]
    tail_s: 2
    steps:
      - name: search
        actions: [{click: field.search}, {type: "${account.password}"}, {key: F5}]
      - name: open
        actions: [{key: F7}]
        regions: [{region: list.count}]
        first_visible: {region: list.top}
        verify: {actions: [{key: End}], regions: [{region: list.bottom}], within_s: 2}
        after_end: fail
  fake-right: *app
""",
    "TF3": """
id: TF3
title: {en: "Time limit", de: "Zeitlimit"}
description: "The right app doesn't finish within the time limit"
timeout_s: 3
apps:
  fake-left: &app
    prepare: [launch, {wait_settled: {quiet_s: 0.8, timeout_s: 20}}]
    steps:
      - name: wait
        actions: [{key: F6}]
        expect: none
  fake-right: *app
""",
}

FOOTNOTE = ["Recorded one after another, same computer · synchronized at the start · median of {{runs}} runs",
            "Timer: waiting time only, typing not counted · test by the Parula team"]


def race(task: str, before: str, after: str, when: str | None = None) -> dict:
    segment = {"id": f"cf-{task.lower()}", "kind": "race", "comparison": "CF", "task": task, "voice_before": before,
               "voice_after": after, "visual": "", "audio": "", "footnote": FOOTNOTE,
               "supers": [f"Task {task}", "Actions: {{actions.CF.left." + task + "}} · {{actions.CF.right." + task + "}}",
                          "{{env.CF.os}} · {{env.CF.date}} · results for this setup only"]}
    if when:
        segment["when"] = when
    return segment


NARRATION = {
    "version": 1, "language": "en", "words_per_minute": 160,
    "segments": [
        {"id": "open", "kind": "fixed", "duration_s": 2.0, "voice": "Two fake apps.", "visual": "",
         "supers": ["Pipeline test", "{{env.messages}} messages in the corpus"], "audio": ""},
        race("TF1", "Who's first?", "No valid measurement.", "missing(t.CF.left.TF1) or missing(t.CF.right.TF1)"),
        race("TF1", "Who's first?", "Left {{time.CF.left.TF1}}, right {{time.CF.right.TF1}}."),
        race("TF2", "New account.", "Left {{time.CF.left.TF2}}, right {{time.CF.right.TF2}}."),
        race("TF3", "Time limit.", "Left {{time.CF.left.TF3}}. Right: not done in time.",
             "status.CF.right.TF3 == 2"),
        race("TF3", "Time limit.", "Both done."),
        {"id": "end", "kind": "fixed", "duration_s": 2.0, "voice": "The end.", "visual": "",
         "supers": ["parula.app", "How we tested: below the video"], "audio": ""},
    ]}

VARIANTS = {"cf": ["open", "cf-tf1", "cf-tf2", "cf-tf3", "end"], "cf-gated": ["cf-tf1", "end"],
            "cf-neutral": ["cf-tf1"]}

COMPOSE = {"short": {"countdown_s": 0.8, "countdown_text": {"en": "Go!"},
                     "countdown_voice": "voice/<lang>/countdown-go.wav"},
           "race_budget_s": {"CF": 2.5}, "video_length_s": [3.0, 90.0],
           "publish_when": {"cf-gated": "env.CF.cloud_sync_confirmed == 1"}, "publish_instead": {"cf-gated": "cf"}}


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
        print(("  ok   " if condition else "  FAIL ") + message, flush=True)
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

    def tone(self, path: Path, seconds: float):
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=440:sample_rate=48000:duration={seconds}", "-af", "volume=-12dB", str(path)],
                       check=True, env=self.env())

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
        apps["fake-right"]["microsoft_ui"] = True
        calibration = self.work / "work" / "calibration" / "default"
        calibration.mkdir(parents=True, exist_ok=True)
        for app_id in APPS:
            (calibration / f"{app_id}.yaml").write_text(yaml.safe_dump(
                {"points": {"field.search": {"x": 300, "y": 80}}, "regions": REGIONS}))
        voice_dir = self.work / "voice" / "en"
        for name, seconds in (("open", 1.0), ("cf-tf1.before", 0.8), ("cf-tf1.after", 1.6), ("countdown-go", 0.4),
                              ("end", 0.8)):
            self.tone(voice_dir / f"{name}.wav", seconds)
        voiceover = self.work / "voiceover"
        (voiceover / "variants").mkdir(parents=True, exist_ok=True)
        (voiceover / "narration.en.json").write_text(json.dumps(NARRATION, indent=2))
        (voiceover / "variants" / "variants.json").write_text(json.dumps(VARIANTS, indent=2))
        (voiceover / "variants" / "compose.json").write_text(json.dumps(COMPOSE, indent=2))
        cpus = str((os.cpu_count() or 2) - 1)
        config = {
            "workdir": str(self.work / "work"), "scenario_dir": str(self.work / "scenarios"),
            "display": {"platform": "linux", "display": self.display,
                        "app_region": {"x": 0, "y": 0, "width": 640, "height": 480},
                        "marker": {"cell": 10, "position": "below", "gap": 4}},
            "capture": {"fps": 60, "cpus": cpus, "draw_mouse": False, "live_scale": 4},
            "settle": {"pixel_threshold": 8, "min_changed_pixels": 120, "quiet_s": 1.0, "step_timeout_s": 30,
                       "reference_quiet_s": 2.6, "reference_tolerance": 0.02, "no_reaction_s": 10,
                       "roi_grace_s": 6},
            "runs": {"measured": self.runs, "warmup": 1, "retries": 1, "analyze_after_each": True},
            "server": {"name": "none", "version": "n/a (fake app test)", "snapshot": {"method": "none"}},
            "account": {"password_env": "E2E_SECRET"},
            "corpus": {"profile": "multi-folder", "folders": [{"name": "Inbox", "count": 10, "role": "inbox"}],
                       "planted": []},
            "driver": {"type_delay_ms": 30},
            "apps": apps,
            "comparisons": {"CF": {"os": "Linux", "left": "fake-left", "right": "fake-right",
                                   "tasks": ["TF1", "TF2", "TF3"]}},
            "deviations": ["Test only: synthetic apps"],
            "compose": {"voice_dir": str(self.work / "voice"), "min_hold_s": 1.5},
            "encode": {"youtube_height": 1320, "threads": 4},
        }
        path = self.work / "config.yaml"
        path.write_text(yaml.safe_dump(config, sort_keys=False))
        return path

    def truth(self, run_dir: Path, app_id: str) -> dict:
        """Ground truth per measured step: the fake app's final (and first) draw minus the driver's input event."""
        events = EventLog.read(run_dir / "driver.jsonl")
        starts = [e for e in events if e["type"] == "step_start"]
        t_open = next(e["t"] for e in events if e["type"] == "restored")
        t_close = next(e["t"] for e in events if e["type"] == "closed")
        truth_log = self.work / "work" / f"truth-{app_id}.jsonl"
        app_events = [json.loads(line) for line in truth_log.read_text().splitlines()]
        app_events = [e for e in app_events if t_open <= e["t"] <= t_close]
        result = {}
        for start in starts:
            final = next((e for e in app_events if e["event"] == "final_drawn" and e["t"] > start["t"]), None)
            first = next((e for e in app_events if e["event"] == "first_drawn" and e["t"] > start["t"]), None)
            result[start["step"]] = {"final": final["t"] - start["t"] if final else None,
                                     "first": first["t"] - start["t"] if first else None}
        return result

    def run(self):
        if self.work.exists():
            shutil.rmtree(self.work)
        self.work.mkdir(parents=True)
        if self.tools:
            os.environ["PATH"] = f"{self.tools}{os.pathsep}{os.environ['PATH']}"
        os.environ["E2E_SECRET"] = "kumquat-secret"
        self.start_xvfb()
        os.environ["DISPLAY"] = self.display
        try:
            config = Config.load(self.write_files())
            pipeline = Pipeline(config)
            self.pipeline = pipeline
            started = time.monotonic()
            print("calibrate references (long quiet period)", flush=True)
            saved = Calibrator(pipeline).references_for("CF")
            self.check(len(saved) == 2 + 2 * 5,
                       f"{len(saved)} reference images saved (full frames, regions, first rows, verify state)")
            print(f"run 1 warm-up + {self.runs} measured runs per app and task, interleaved", flush=True)
            pipeline.run("CF", None, True, self.runs, 1)
            record_s = time.monotonic() - started
            print("analyze", flush=True)
            results = pipeline.analyze("CF")
            self.verify_measurements(config, results)
            self.verify_secret(config)
            print("compose", flush=True)
            narration = str(self.work / "voiceover")
            composed = pipeline.compose(["CF"], "en", narration, "cf", "e2e")
            self.verify_compose(config, composed)
            print("encode", flush=True)
            pipeline.encode("e2e", "en", None)
            verified = pipeline.verify("e2e", "en")
            for kind, report in verified.items():
                if isinstance(report, dict):
                    bad = {k: v for k, v in report["checks"].items() if not v["ok"]}
                    self.check(report["ok"], f"{kind}: " + (", ".join(f"{k}={v['actual']}" for k, v in
                                                                     report["checks"].items()) if not bad else
                                                          f"failed {bad}"))
            self.verify_gate(pipeline, narration)
            self.verify_neutral(config, pipeline, narration)
            self.verify_footage_timelapse(config, pipeline, narration)
            self.report["recording_s"] = round(record_s, 1)
        finally:
            self.stop_xvfb()
        (self.work / "e2e-report.json").write_text(json.dumps(self.report, indent=2))
        print(json.dumps(self.report, indent=2))
        print("PASSED" if not self.failures else f"FAILED: {len(self.failures)} checks")
        return not self.failures

    def verify_measurements(self, config, results: dict):
        comparison = results["comparisons"]["CF"]
        errors, first_errors = [], []
        per_step = {}
        for task_id, task in comparison["tasks"].items():
            for side in ("left", "right"):
                s = task[side]
                timeout_side = task_id == "TF3" and side == "right"
                if timeout_side:
                    self.check(s["status"] == 2 and s["timed_out_runs"] == self.runs,
                               f"TF3 right: status {s['status']} (2 = time limit), {s['timed_out_runs']} timeouts")
                    self.check(s["timeout_run"] is not None, f"TF3 right: run shown at the limit {s['timeout_run']}")
                    continue
                self.check(s["status"] == 0, f"{task_id} {side}: status {s['status']} {s.get('status_reason') or ''}")
                self.check(s["measured_runs"] == self.runs, f"{task_id} {side}: {s['measured_runs']} measured runs")
                self.check(s["warmups_discarded"] == ["warmup-1"], f"{task_id} {side}: warm-up discarded")
                totals = sorted(r["total_s"] for r in s["runs"])
                median_total = next(r["total_s"] for r in s["runs"] if r["run"] == s["median_run"])
                self.check(abs(median_total - statistics.median(totals)) < 1e-9,
                           f"{task_id} {side}: median run {s['median_run']} has the median total {median_total:.3f} s")
                for r in s["runs"]:
                    run_dir = self.pipeline.results_folder().run_dir(s["app"], task_id, r["run"])
                    truth = self.truth(run_dir, s["app"])
                    analysis = json.loads((run_dir / "analysis.json").read_text())
                    for step in analysis["steps"]:
                        err = step["duration_s"] - truth[step["name"]]["final"]
                        errors.append(err)
                        per_step.setdefault(f"{task_id}/{side}/{step['name']}", []).append(
                            (round(step["duration_s"], 4), round(truth[step["name"]]["final"], 4), round(err * 1000, 1)))
                        if step.get("first_visible_time") is not None:
                            first_errors.append(step["first_visible_time"] - step["start_time"]
                                                - truth[step["name"]]["first"])
                        if task_id == "TF2" and step["name"] == "open":
                            self.check_without_region(run_dir, step, truth[step["name"]]["final"], config)
                            live = [e for e in EventLog.read(run_dir / "driver.jsonl")
                                    if e["type"] == "step_live_settled" and e["step"] == "open"]
                            self.check(bool(live) and live[0].get("live_matched") is True,
                                       f"TF2 {side} {r['run']}: the live gate saw the completion region match")
                            self.check(step.get("verify_matched_after_s") is not None,
                                       f"TF2 {side} {r['run']}: verify check matched after "
                                       f"{step.get('verify_matched_after_s')} s")
                    self.check(analysis["clock_fit"]["max_abs_residual_s"] <= 1.5 * FRAME,
                               f"{task_id} {s['app']} {r['run']}: clock fit residual "
                               f"{analysis['clock_fit']['max_abs_residual_s'] * 1000:.1f} ms")
                    if task_id == "TF2":
                        self.check(analysis["tail"]["recorded_s"] > 1.5,
                                   f"TF2 {side} {r['run']}: tail of {analysis['tail']['recorded_s']} s recorded")
        worst = max(abs(e) for e in errors)
        self.check(worst <= FRAME + 0.002, f"all {len(errors)} measured steps within ±1 frame of the truth "
                                           f"(worst {worst * 1000:.1f} ms, mean {np.mean(errors) * 1000:+.1f} ms)")
        worst_first = max(abs(e) for e in first_errors) if first_errors else None
        self.check(bool(first_errors) and worst_first <= FRAME + 0.002,
                   f"'first messages visible' within ±1 frame in {len(first_errors)} runs "
                   f"(worst {(worst_first or 0) * 1000:.1f} ms)")
        self.report["steps"] = {k: {"measured_s": [v[0] for v in vals], "truth_s": [v[1] for v in vals],
                                    "error_ms": [v[2] for v in vals]} for k, vals in per_step.items()}
        self.report["error_ms"] = {"worst_abs": round(worst * 1000, 2), "mean": round(float(np.mean(errors)) * 1000, 2),
                                   "stdev": round(float(np.std(errors)) * 1000, 2), "n": len(errors),
                                   "first_visible_worst_abs": round((worst_first or 0) * 1000, 2)}
        self.report["medians_s"] = {f"{t}/{side}": comparison["tasks"][t][side]["median_s"]
                                    for t in comparison["tasks"] for side in ("left", "right")}

    def check_without_region(self, run_dir: Path, step: dict, truth_s: float, config):
        series = ChangeSeries.load(run_dir / "changes.npz")
        params = SettleParams.from_dict(config.get("settle"))
        plain = SettleDetector(params).find_end(series, step["start_time"], step["window_end"])
        early = truth_s - (plain.duration or 0)
        self.report.setdefault("without_region_early_s", []).append(round(early, 3))
        self.check(early > 0.5, f"{run_dir.parent.name} {run_dir.name}: without the completion region the step would "
                                f"end {early:.2f} s too early")

    def verify_secret(self, config):
        secret = os.environ["E2E_SECRET"].encode()
        leaked = [str(p) for p in config.workdir.rglob("*") if p.is_file() and p.suffix in (".json", ".jsonl", ".txt",
                                                                                              ".md", ".log")
                  and secret in p.read_bytes()]
        self.check(not leaked, f"the typed secret is in no log or report file {leaked[:3]}")

    def verify_compose(self, config, composed: dict):
        out_dir = config.workdir / "compose" / "e2e-en"
        timeline = json.loads((out_dir / "timeline.json").read_text())
        kinds = [s["kind"] for s in timeline["segments"]]
        self.check(kinds == ["fixed", "race", "race", "race", "fixed"], f"segments {kinds}")
        races = {s["task"]: s for s in timeline["segments"] if s["kind"] == "race"}
        tf1, tf2, tf3 = races["TF1"], races["TF2"], races["TF3"]
        after = next(v for v in tf1["voice"] if v["part"] == "voice_after")
        self.check(after["text"].startswith("Left ") and "second" in after["text"], f"time.* in the voice: "
                                                                                   f"“{after['text']}”")
        self.check(after["file"] is not None, "recorded voice file used for voice_after")
        self.check(any(v["part"] == "countdown" for v in tf1["voice"]), "countdown-go.wav under 'Go!'")
        self.check(not tf1["timer_race"] and tf1["timelapse"]["factor"] == 1, "TF1 within the race budget: real time")
        self.check(tf2["timer_race"] and tf2["timelapse"]["factor"] > 1,
                   f"TF2 beyond the budget with a Microsoft pane: timer race ×{tf2['timelapse']['factor']}")
        self.check(tf3["panes"]["right"]["timed_out"] and tf3["timer_race"], "TF3: race to the time limit")
        for name, segment in races.items():
            panes = segment["panes"]
            by_screen = sorted(panes, key=lambda s: panes[s]["done_at_output_s"])
            by_timer = sorted(panes, key=lambda s: panes[s]["waiting_s"])
            self.check(by_screen == by_timer, f"{name}: panes finish on screen in the order their timers stop "
                                              f"({segment['mode']} mode)")
        self.check(timeline["publication"]["allowed"], "variant cf may be published")
        self.check(all(Path(p).exists() for p in (out_dir / "subtitles.vtt", out_dir / "subtitles.srt",
                                                  out_dir / "audio.wav")), "subtitles and audio written")
        video = VideoFile(Path(composed["master"]), "ffmpeg", "ffprobe")
        width, height = video.size
        self.check((width, height) == (1280, 480 + 250), f"master is {width}x{height}")
        scale = 0.5
        header, label = int(round(140 * scale)), int(round(70 * scale))
        timer_box = (header, header + label, 640 - 140, 640)
        pane = tf1["panes"]["left"]
        t_done = tf1["start_s"] + pane["done_at_output_s"]
        t_running = tf1["start_s"] + tf1["pre_s"] + 0.05
        times = video.frame_times()
        wanted = {"hook": tf1["start_s"] + 0.3, "running_a": t_running, "running_b": t_running + 0.2,
                  "done_a": t_done + 0.2, "done_b": t_done + 0.6}
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
        self.report["compose"] = {"duration_s": timeline["duration_s"], "segments": kinds,
                                  "timelapse": {k: v["timelapse"] for k, v in races.items()}}

    def verify_gate(self, pipeline, narration: str):
        pipeline.compose(["CF"], "en", narration, "cf-gated", "gated")
        try:
            pipeline.encode("gated", "en", ["mp4"])
            self.check(False, "encode refuses a variant whose publication condition is false")
        except EncodeError as ex:
            self.check("cf" in str(ex), "encode refuses the gated variant and names the one to publish instead")
        outputs = pipeline.encode("gated", "en", ["mp4"], internal_preview=True)
        self.check(Path(outputs["mp4"]).exists(), "internal preview encoded with its 'not for publication' mark")

    def verify_neutral(self, config, pipeline, narration: str):
        results_path = pipeline.results_path()
        changed = json.loads(results_path.read_text())
        right = changed["comparisons"]["CF"]["tasks"]["TF1"]["right"]
        right.update({"status": 3, "status_reason": "test", "median_s": None, "min_s": None, "max_s": None,
                      "median_run": None})
        other = results_path.with_name("results-neutral.json")
        other.write_text(json.dumps(changed))
        composed = pipeline.compose(["CF"], "en", narration, "cf-neutral", "neutral", [str(other)])
        timeline = json.loads((config.workdir / "compose" / "neutral-en" / "timeline.json").read_text())
        segment = timeline["segments"][0]
        self.check(segment.get("neutral") is True and composed["duration_s"] > 1,
                   "a differing result shows the neutral card instead of race footage")
        self.check(any("No valid" in v["text"] for v in segment["voice"]), "and the narration's fallback line")

    def verify_footage_timelapse(self, config, pipeline, narration: str):
        settings = json.loads((self.work / "voiceover" / "variants" / "compose.json").read_text())
        lapse = copy.deepcopy(settings)
        lapse["short"]["microsoft_timelapse"] = True
        (self.work / "voiceover" / "variants" / "compose.json").write_text(json.dumps(lapse))
        try:
            pipeline.compose(["CF"], "en", narration, "cf", "lapse")
        finally:
            (self.work / "voiceover" / "variants" / "compose.json").write_text(json.dumps(settings))
        timeline = json.loads((config.workdir / "compose" / "lapse-en" / "timeline.json").read_text())
        tf2 = next(s for s in timeline["segments"] if s.get("task") == "TF2")
        self.check(not tf2["timer_race"] and tf2["timelapse"]["factor"] > 1,
                   f"with microsoft_timelapse: footage time-lapse ×{tf2['timelapse']['factor']}")
        clip = VideoFile(Path(tf2["clip"]), "ffmpeg", "ffprobe")
        frames = len(clip.frame_times())
        self.check(abs(frames / 60 - (tf2["end_s"] - tf2["start_s"])) < 0.1,
                   f"time-lapse clip has {frames} frames at 60 fps for {tf2['end_s'] - tf2['start_s']:.2f} s")
        budget = settings["race_budget_s"]["CF"]
        on_screen = tf2["timelapse"]["end"] - tf2["pre_s"]
        self.check(on_screen <= budget + 1e-6, f"race on screen {on_screen:.2f} s within the budget {budget} s")


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
