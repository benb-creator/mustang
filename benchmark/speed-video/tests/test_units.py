"""Unit tests for the pure parts of the pipeline. Run: python -m pytest tests/test_units.py"""

import io
import os
import random
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchlib.analyze import Aggregator  # noqa: E402
from benchlib.attachments import SyntheticFiles  # noqa: E402
from benchlib.compose import RacePlan, SubtitleWriter, VoicePart  # noqa: E402
from benchlib.corpus import CorpusGenerator, CorpusSpec  # noqa: E402
from benchlib.marker import ClockFit, ClockFitError, MarkerCode, MarkerTrack  # noqa: E402
from benchlib.narration import Condition, Narration, NarrationValues  # noqa: E402
from benchlib.runner import RunPlan  # noqa: E402
from benchlib.scenario import Action, Scenario  # noqa: E402
from benchlib.settle import ChangeSeries, FrameDiff, LiveSettleState, Rect, SettleDetector, SettleParams  # noqa: E402

FPS = 60.0


# --- settle detection on synthetic frame sequences -------------------------------------------------------------

class SyntheticScreen:
    """Generates RGB frames of a fake app: a spinner, a blinking caret, progressive rendering, a static 'Loading'."""

    def __init__(self, width=320, height=240):
        self.width, self.height = width, height

    def frame(self, t: float, events: dict) -> np.ndarray:
        img = np.full((self.height, self.width, 3), 240, dtype=np.uint8)
        # caret blinks every 0.53 s: 2x16 px, must be ignored
        if int(t / 0.53) % 2 == 0:
            img[20:36, 10:12] = 0
        spinner_until = events.get("spinner_until")
        if spinner_until and events["start"] <= t < spinner_until:
            phase = int(t * 30) % 8
            img[100:132, 140 + phase * 2:172 + phase * 2] = 60
        loading = events.get("loading")
        if loading and loading[0] <= t < loading[1]:
            img[150:170, 100:220] = 30
        content_at = events.get("content_at")
        if content_at is not None:
            rows = events.get("progressive", 1)
            for r in range(rows):
                if t >= content_at - (rows - 1 - r) * 0.05:
                    img[40 + r * 20:56 + r * 20, 40:280] = 90
        return img


def series_for(events: dict, duration: float, params: SettleParams, masks=(), reference=None):
    screen = SyntheticScreen()
    diff = FrameDiff(screen.width, screen.height, params.pixel_threshold, masks)
    times = np.arange(int(duration * FPS)) / FPS
    counts = np.zeros(len(times), dtype=np.int64)
    distances = np.ones(len(times), dtype=np.float32)
    previous = None
    for i, t in enumerate(times):
        frame = screen.frame(t, events)
        if previous is not None:
            counts[i] = diff.changed_pixels(previous, frame)
        if reference is not None:
            distances[i] = diff.reference_distance(frame, reference, params.reference_pixel_threshold)
        previous = frame
    return ChangeSeries(times, counts, {"ref": distances}), screen


def test_settle_spinner_then_progressive_content():
    params = SettleParams(min_changed_pixels=100, quiet_s=1.0)
    events = {"start": 1.0, "spinner_until": 2.4, "content_at": 2.5, "progressive": 4}
    series, _ = series_for(events, 6.0, params)
    result = SettleDetector(params).find_end(series, 1.0)
    assert result.status == "settled"
    assert abs(result.end_time - 2.5) <= 1 / FPS + 1e-9
    assert abs(result.duration - 1.5) <= 1 / FPS + 1e-9


def test_caret_alone_never_counts():
    params = SettleParams(min_changed_pixels=100, quiet_s=1.0, expect_change=True)
    series, _ = series_for({"start": 1.0}, 4.0, params)
    assert max(series.counts) > 0
    assert SettleDetector(params).find_end(series, 1.0).status == "no-change"


def test_masked_region_is_ignored():
    params = SettleParams(min_changed_pixels=100, quiet_s=1.0)
    events = {"start": 1.0, "spinner_until": 5.0, "content_at": 1.8}
    mask = [Rect(130, 90, 70, 50)]
    series, _ = series_for(events, 7.0, params, mask)
    result = SettleDetector(params).find_end(series, 1.0)
    assert abs(result.end_time - 1.8) <= 1 / FPS + 1e-9


def test_static_loading_needs_reference():
    params = SettleParams(min_changed_pixels=100, quiet_s=1.0)
    events = {"start": 1.0, "loading": (1.1, 2.7), "content_at": 2.7}
    screen = SyntheticScreen()
    reference = screen.frame(6.0, events)
    series, _ = series_for(events, 6.0, params, reference=reference)
    without = SettleDetector(params).find_end(series, 1.0)
    assert abs(without.end_time - 1.1) <= 1 / FPS + 1e-9, "without a reference the Loading state looks done"
    accept = lambda i: series.reference_distances["ref"][i] <= params.reference_tolerance
    with_ref = SettleDetector(params).find_end(series, 1.0, accept=accept)
    assert with_ref.status == "settled"
    assert with_ref.rejected_candidates == 1
    assert abs(with_ref.end_time - 2.7) <= 1 / FPS + 1e-9


def test_unsettled_when_recording_ends_too_early():
    params = SettleParams(min_changed_pixels=100, quiet_s=1.0)
    events = {"start": 1.0, "spinner_until": 3.5}
    series, _ = series_for(events, 4.0, params)
    assert SettleDetector(params).find_end(series, 1.0).status == "unsettled"


def test_window_end_limits_search():
    params = SettleParams(min_changed_pixels=100, quiet_s=1.0)
    events = {"start": 1.0, "content_at": 1.5}
    series, _ = series_for(events, 6.0, params)
    assert SettleDetector(params).find_end(series, 1.0, window_end=2.2).status == "unsettled"
    assert SettleDetector(params).find_end(series, 1.0, window_end=2.6).status == "settled"


def test_live_settle_state():
    live = LiveSettleState(min_changed_pixels=5, quiet_s=1.0)
    live.reset(10.0)
    live.add(10.2, 50)
    assert not live.is_settled(10.9)
    assert live.is_settled(11.25)
    live.reset(20.0)
    assert not live.is_settled(25.0), "expects a change first"


# --- sync marker and clock alignment -----------------------------------------------------------------------------

def test_marker_round_trip_and_rejects_partial():
    code = MarkerCode(12)
    for value in (0, 1, 5, 1234, 4095):
        assert code.decode(code.render(value)) == value
    image = code.render(1234).astype(np.float32)
    image[:, 5 * 12:6 * 12] = 128
    assert code.decode(image.astype(np.uint8)) is None
    flipped = code.render(1234)
    flipped[:, 3 * 12:4 * 12] = 255 - flipped[:, 3 * 12:4 * 12]
    assert code.decode(flipped) is None, "parity catches a single wrong cell"


def test_clock_fit_recovers_offset_and_rate():
    rng = random.Random(7)
    driver = {c: 100.0 + c * 0.3 for c in range(1, 12)}
    video = {}
    for c, t in driver.items():
        exact = 1.00002 * t - 97.5
        video[c] = (int(exact * FPS) + 1) / FPS + rng.uniform(0, 0.002)
    fit = ClockFit.fit(driver, video, 1 / FPS)
    for c, t in driver.items():
        assert abs(fit.to_video(t) - video[c]) <= 1 / FPS
    assert abs(fit.slope - 1.00002) < 0.001


def test_clock_fit_rejects_outlier_and_fails_without_markers():
    driver = {c: 10.0 + c * 0.2 for c in range(1, 9)}
    video = {c: t - 5.0 for c, t in driver.items()}
    video[4] += 0.5
    fit = ClockFit.fit(driver, video, 1 / FPS)
    assert fit.rejected_codes == [4]
    with pytest.raises(ClockFitError):
        ClockFit.fit(driver, {1: 5.2, 2: 5.4}, 1 / FPS)


def test_marker_track_keeps_first_frame():
    track = MarkerTrack()
    for t, c in [(0.0, None), (0.1, 3), (0.12, 3), (0.2, None), (0.3, 4), (0.4, 3)]:
        track.add(t, c)
    assert track.first_seen == {3: 0.1, 4: 0.3}


# --- run plan and median selection -------------------------------------------------------------------------------

def test_interleaved_plan():
    plan = RunPlan.interleaved(["a", "b"], 2, 1)
    assert plan == [("a", "warmup-1", True), ("b", "warmup-1", True), ("a", "run-1", False), ("b", "run-1", False),
                    ("a", "run-2", False), ("b", "run-2", False)]


def test_median_run_is_a_real_run():
    runs = [{"run": f"run-{i}", "order": i, "total_s": t} for i, t in enumerate([3.1, 2.0, 9.9, 2.8, 3.0], 1)]
    assert Aggregator.median_run(runs)["run"] == "run-5"
    four = runs[:4]
    chosen = Aggregator.median_run(four)
    assert chosen["run"] in ("run-1", "run-4")


# --- narration: placeholders and conditions ----------------------------------------------------------------------

def values(language="en"):
    v = NarrationValues(language)
    v.set_seconds("t.C2.left.T3", 0.84)
    v.set_seconds("t.C2.right.T3", 12.345)
    v.set_ratio("ratio.C2.T3", 12.345 / 0.84)
    v.set_count("actions.C2.left.T3", 1)
    v.set_count("env.messages", 30000)
    v.set_count("runs", 5)
    v.set_text("app.C2.left", "Parula 0.9.39")
    v.set_seconds("t.C2.left.T5", None)
    return v


def test_conditions():
    v = values()
    assert Condition("ratio.C2.T3 >= 2").evaluate(v.raw)
    assert Condition("t.C2.left.T3 < 0.5 or ratio.C2.T3 > 10 and not (actions.C2.left.T3 == 2)").evaluate(v.raw)
    assert Condition("missing(t.C2.left.T5)").evaluate(v.raw)
    assert not Condition("t.C2.left.T5 < 100").evaluate(v.raw), "comparisons with a missing value are false"
    assert not Condition("missing(t.C2.left.T3)").evaluate(v.raw)
    with pytest.raises(Exception):
        Condition("ratio.C2.T3 >=")


def test_placeholders_and_language_formats():
    en, de = values("en"), values("de")
    assert en.substitute("{{t.C2.left.T3}} vs {{t.C2.right.T3}}, {{env.messages}} mails, {{runs}} runs") == \
        "0.84 vs 12, 30,000 mails, 5 runs"
    assert de.substitute("{{t.C2.left.T3}} / {{ratio.C2.T3}} / {{env.messages}}") == "0,84 / 14,7 / 30.000"
    assert en.substitute("{{t.C2.left.T5}}") == "–"


def test_alternatives_first_match_wins():
    doc = Narration({"language": "en", "words_per_minute": 150, "segments": [
        {"id": "a", "kind": "fixed", "duration_s": 3, "voice": "Intro"},
        {"id": "r", "kind": "race", "comparison": "C2", "task": "T3", "when": "missing(t.C2.left.T3)",
         "voice_after": "missing"},
        {"id": "r", "kind": "race", "comparison": "C2", "task": "T3", "when": "ratio.C2.T3 >= 2",
         "voice_after": "Factor {{ratio.C2.T3}}"},
        {"id": "r", "kind": "race", "comparison": "C2", "task": "T3", "voice_after": "fallback"},
    ]})
    chosen = doc.resolve(values())
    assert [s["id"] for s in chosen] == ["a", "r"]
    assert chosen[1]["voice_after"] == "Factor 14.7"
    assert doc.resolve(values(), ["r"])[0]["id"] == "r"


def test_narration_file_resolves():
    """Set BENCH_NARRATION=<path to narration.<lang>.json> to check a real narration file."""
    path = Path(os.environ.get("BENCH_NARRATION", ""))
    if not path.is_file():
        pytest.skip("BENCH_NARRATION not set")
    doc = Narration.load(path)
    chosen = doc.resolve(values())
    assert len(chosen) == len({s["id"] for s in doc.segments})


# --- scenario parsing --------------------------------------------------------------------------------------------

def test_action_parsing_and_counts(tmp_path):
    (tmp_path / "TX.yaml").write_text("""
id: TX
title: {en: Test}
apps:
  a:
    prepare: [launch, {wait_settled: {timeout_s: 5}}]
    steps:
      - name: one
        actions: [{type: "${account.email}"}, {key: Tab}, {type: "${account.password}"}, {key: Return}]
      - name: two
        actions: [{click: button.continue}, {key: Down, repeat: 3}, {sleep: 0.2}, {key: Return}]
""")
    s = Scenario.load(tmp_path / "TX.yaml").for_app("a")
    assert s.user_action_count == 4 + 1 + 3 + 1
    assert s.steps[1].trigger_index == 3
    assert s.point_names == {"button.continue"}
    assert "type the password" in s.action_list
    assert Action.parse({"key": "End"}).describe() == "key End"


def test_config_expands_keys_and_values(tmp_path):
    from benchlib.config import Config
    config = Config({"workdir": str(tmp_path / "w"), "apps": {"a": {"profile": {"files": {"{profile}/x.js": "{workdir}"}}}}},
                    tmp_path)
    files = config.expand(config.app("a"), "a")["profile"]["files"]
    assert files == {str(tmp_path / "w" / "profiles" / "a" / "x.js"): str(tmp_path / "w")}


# --- corpus determinism and validity -----------------------------------------------------------------------------

SMALL = {"profile": "multi-folder", "seed": 99, "folders": [
    {"name": "Inbox", "count": 60, "role": "inbox", "days_back_from": 90, "days_back_to": 0, "seen_ratio": 0.7},
    {"name": "Archive", "count": 120, "role": "archive", "days_back_from": 3650, "days_back_to": 90},
    {"name": "Sent", "count": 40, "role": "sent"},
    {"name": "Projects/Move-me", "count": 30}],
    "attachment_max": 300000, "large_from": 200000,
    "planted": [{"term": "kumquat", "count": 11}, {"term": "Zanzibar", "count": 4, "field": "subject"}]}


def test_corpus_is_deterministic():
    a = CorpusGenerator(CorpusSpec.from_dict(SMALL)).manifest()
    b = CorpusGenerator(CorpusSpec.from_dict(SMALL)).manifest()
    assert a["digest"] == b["digest"]
    other_seed = CorpusGenerator(CorpusSpec.from_dict({**SMALL, "seed": 100})).manifest()
    assert other_seed["digest"] != a["digest"]
    one = CorpusGenerator(CorpusSpec.from_dict(SMALL)).generate("Archive", 77).raw
    assert one == CorpusGenerator(CorpusSpec.from_dict(SMALL)).generate("Archive", 77).raw


def test_corpus_counts_planted_terms_and_threads():
    from email import message_from_bytes, policy
    generator = CorpusGenerator(CorpusSpec.from_dict(SMALL))
    found = {"kumquat": 0, "Zanzibar": 0}
    replies = 0
    ids = set()
    dates = {}
    for msg in generator.messages():
        parsed = message_from_bytes(msg.raw, policy=policy.default)
        assert parsed["Message-ID"] == msg.message_id
        ids.add(msg.message_id)
        dates.setdefault(msg.folder, []).append(msg.received_at)
        if parsed["In-Reply-To"]:
            replies += 1
        if "Zanzibar" in str(parsed["Subject"]):
            found["Zanzibar"] += 1
        body = parsed.get_body(("plain",)).get_content()
        if "kumquat" in body:
            found["kumquat"] += 1
        assert b"\r\n" in msg.raw and b"\n" not in msg.raw.replace(b"\r\n", b"")
    assert found == {"kumquat": 11, "Zanzibar": 4}
    assert len(ids) == 250
    assert replies > 30
    for folder, folder_dates in dates.items():
        assert folder_dates == sorted(folder_dates), f"{folder} is in date order"


def test_synthetic_files_are_valid():
    files = SyntheticFiles(random.Random(3))
    for kind in ("jpeg", "png"):
        a = files.make(kind, 120_000, "x")
        image = Image.open(io.BytesIO(a.data))
        image.load()
        assert abs(len(a.data) - 120_000) < 20_000
    pdf = files.make("pdf", 50_000, "x").data
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    xref = int(pdf[pdf.rindex(b"startxref") + 10:].split()[0])
    assert pdf[xref:xref + 4] == b"xref"
    for kind in ("docx", "xlsx"):
        data = files.make(kind, 80_000, "x").data
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert z.testzip() is None
            assert "[Content_Types].xml" in z.namelist()


# --- compose helpers ---------------------------------------------------------------------------------------------

def test_race_plan_follows_the_budget_rule():
    factors = [2, 3, 4, 5, 8, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500,
               2000, 3000, 5000]
    within = RacePlan.for_budget(2.0, 0.8, 3.0, 8.0, 8.5, factors, 1.0, 0.5, 4.0)
    assert not within.lapsed and within.total == 2.0 + 0.8 + 8.0 + 4.0
    plan = RacePlan.for_budget(2.0, 0.8, 3.0, 60.0, 8.5, factors, 1.0, 0.5, 4.0)
    assert plan.a == 3.5, "real time until just after the faster app (3 s + 0.5 s <= budget / 2)"
    assert plan.factor == 15, "the smallest listed factor with a + (s - a) / F <= budget"
    assert plan.a + (plan.s - plan.a) / plan.factor <= 8.5
    assert abs(plan.out(60.0) - (2.8 + 3.5 + 56.5 / 15)) < 1e-9
    assert plan.out(1.0) == 3.8
    slow_fast = RacePlan.for_budget(2.0, 0.8, 6.0, 1800.0, 2.5, factors, 1.0, 0.5, 4.0)
    assert slow_fast.a == 1.0, "faster app later than budget / 2: real time for the first second only"
    assert slow_fast.factor == 1500 and slow_fast.a + (slow_fast.s - 1.0) / 1500 <= 2.5
    timer_race = RacePlan.for_budget(2.0, 0.8, 3.0, 60.0, 8.5, factors, 1.0, 0.5, 4.0, timer_race=True)
    assert timer_race.a == 1.0 and timer_race.timer_race


def test_subtitles(tmp_path):
    parts = [VoicePart("a", "voice", "One two three four five six seven eight nine ten. " * 3, 1.0, 6.0)]
    SubtitleWriter(parts, max_chars=60).write(tmp_path / "s.vtt", tmp_path / "s.srt")
    vtt = (tmp_path / "s.vtt").read_text()
    assert vtt.startswith("WEBVTT") and "00:00:01.000 -->" in vtt
    assert (tmp_path / "s.srt").read_text().startswith("1\n00:00:01,000 -->")
