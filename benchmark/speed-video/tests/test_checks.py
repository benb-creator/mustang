"""Unit tests for the review fixes: completion checks, censored medians, snapshot guards, server-log evidence,
method texts, spoken durations, secrets. Run: python -m pytest tests/test_checks.py"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchlib.analyze import Aggregator  # noqa: E402
from benchlib.attachments import SyntheticFiles  # noqa: E402
from benchlib.config import Config  # noqa: E402
from benchlib.corpus import CorpusGenerator, CorpusSpec  # noqa: E402
from benchlib.driver import TextVariables  # noqa: E402
from benchlib.narration import Condition, MethodTemplate, NarrationValues, SpokenDuration  # noqa: E402
from benchlib.serverlog import EvidenceSummary, FetchKinds, LogEvent, ServerLog, StalwartIds  # noqa: E402
from benchlib.settle import FrameAnalyzer, Rect, Region, SettleDetector, SettleParams  # noqa: E402
from benchlib.snapshot import SnapshotError, StorageSnapshot  # noqa: E402

FPS = 60.0
W, H = 640, 400


def frames(duration: float, draw) -> tuple[np.ndarray, list[np.ndarray]]:
    times = np.arange(int(duration * FPS)) / FPS
    out = []
    for t in times:
        img = np.full((H, W, 3), 240, dtype=np.uint8)
        draw(img, t)
        out.append(img)
    return times, out


def analyze(times, images, params, regions=(), masks=()):
    analyzer = FrameAnalyzer(W, H, params, masks, regions=regions)
    for t, img in zip(times, images):
        analyzer.add(float(t), img)
    return analyzer.series()


def list_rows(img, t, final_at):
    rows = 25 if t >= 1.0 else 0
    for r in range(rows):
        img[20 + r * 14:30 + r * 14, 20:400] = 60


def counter(img, t, start, until):
    if t >= start:
        value = int(min(t, until) * 100)
        for digit in range(5):
            shade = 30 + (value // (10 ** digit)) % 10 * 20
            img[380:390, 500 + digit * 6:504 + digit * 6] = shade


def test_small_counter_needs_its_region():
    """B1: the visible rows are final after 1 s; a small "n of 30000" counter changes until 12 s."""
    params = SettleParams(min_changed_pixels=150, quiet_s=1.0)
    draw = lambda img, t: (list_rows(img, t, 1.0), counter(img, t, 1.0, 12.0))
    times, images = frames(14.0, draw)
    region_rect = Rect(495, 375, 40, 20)
    reference = region_rect.crop(images[-1])
    checks = [Region("inbox.count", region_rect), Region("open|end|inbox.count", region_rect, reference, 0.0)]
    series = analyze(times, images, params, checks)
    without = SettleDetector(params).find_end(series, 0.5, 14.0)
    assert abs(without.end_time - 1.0) < 2 / FPS, "without a region the counter is too small to count"
    accept = lambda i: series.region_distances["open|end|inbox.count"][i] <= 0.0
    detector = SettleDetector(params, ["inbox.count"])
    result = detector.find_end(series, 0.5, 14.0, accept)
    assert result.status == "settled"
    assert abs(result.end_time - 12.0) <= 1.5 / FPS


def test_slow_fade_is_seen():
    """m2: a 2 s fade with less than 8 levels per frame."""
    params = SettleParams(min_changed_pixels=150, quiet_s=1.0)

    def draw(img, t):
        level = int(max(0.0, min(1.0, (t - 0.3) / 2.0)) * 200)
        img[100:200, 100:300] = 240 - level
    times, images = frames(4.0, draw)
    result = SettleDetector(params).find_end(analyze(times, images, params), 0.2)
    assert result.status == "settled"
    assert abs(result.end_time - 2.3) < 3 / FPS


def test_late_changes_are_reported():
    """m1/B1: a second burst exactly quiet_s after the first ends the step at the first one; it is reported."""
    params = SettleParams(min_changed_pixels=150, quiet_s=1.0)

    def draw(img, t):
        if t >= 0.5:
            img[100:200, 100:300] = 30
        if t >= 1.5:
            img[250:300, 100:300] = 30
    times, images = frames(3.0, draw)
    result = SettleDetector(params).find_end(analyze(times, images, params), 0.1, 3.0)
    assert abs(result.end_time - 0.5) < 1 / FPS and result.late_changes == 1
    assert abs(result.last_late_change_time - 1.5) < 1 / FPS


def test_missing_frames_before_the_end_are_visible():
    """M11: frames 0.75–0.95 s are missing around the change at 0.8 s."""
    params = SettleParams(min_changed_pixels=150, quiet_s=1.0)
    times, images = frames(3.0, lambda img, t: img.__setitem__((slice(100, 200), slice(100, 300)), 30 if t >= 0.8 else 240))
    keep = [i for i, t in enumerate(times) if not 0.75 < t < 0.95]
    result = SettleDetector(params).find_end(analyze(times[keep], [images[i] for i in keep], params), 0.1, 3.0)
    assert result.end_uncertainty_s > 2 / FPS


def test_censored_median_and_status():
    assert Aggregator.censored_median([3.0, 1.0, 2.0, None, 5.0]) == (3.0, False)
    assert Aggregator.censored_median([3.0, None, None, None, 5.0]) == (None, True)
    assert Aggregator.censored_median([1.0, 2.0, None, 4.0]) == (3.0, False)
    assert Aggregator.censored_median([1.0, None, None, 4.0]) == (None, True)


def write_run(root: Path, app: str, run: str, order: int, status: str, total=None, warmup=False):
    run_dir = root / "runs" / "C9" / "T1" / app / run
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({"run": run, "order": order, "warmup": warmup, "status": "complete",
                                                   "app_version": "1.0"}))
    analysis = {"status": status, "total_s": total, "first_s": None, "steps": [], "censored_at_s":
                60.0 if status == "timeout" else None, "reason": None if status in ("ok", "timeout") else "x"}
    (run_dir / "analysis.json").write_text(json.dumps(analysis))


def aggregator(tmp_path, outcomes):
    for n, (status, total) in enumerate(outcomes, 1):
        write_run(tmp_path, "a", f"run-{n}", 2 * n, status, total)
    write_run(tmp_path, "a", "warmup-1", 0, "ok", 9.0, True)
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "scenarios" / "T1.yaml").write_text(
        "id: T1\ntimeout_s: 60\napps:\n  a:\n    steps:\n      - name: s\n        actions: [{key: Return}]\n")
    config = Config({"workdir": str(tmp_path), "scenario_dir": str(tmp_path / "scenarios"),
                     "runs": {"measured": 5}, "apps": {"a": {"name": "A"}}}, tmp_path)
    from benchlib.scenario import ScenarioLibrary
    return Aggregator(config, ScenarioLibrary(tmp_path / "scenarios")).side("C9", "T1", "a")


def test_side_with_one_timeout_keeps_a_median(tmp_path):
    side = aggregator(tmp_path, [("ok", 3.0), ("timeout", None), ("ok", 2.0), ("ok", 4.0), ("ok", 5.0)])
    assert side["status"] == 0 and side["median_s"] == 4.0 and side["max_censored"] and side["max_s"] == 60.0
    assert side["median_run"] == "run-4" and side["warmups_discarded"] == ["warmup-1"]


def test_side_with_three_timeouts_has_status_2(tmp_path):
    side = aggregator(tmp_path, [("timeout", None), ("timeout", None), ("ok", 2.0), ("timeout", None), ("ok", 5.0)])
    assert side["status"] == 2 and side["median_s"] is None and side["timeout_run"] in ("run-1", "run-2", "run-4")


def test_side_with_a_wrong_result_has_status_3(tmp_path):
    side = aggregator(tmp_path, [("ok", 3.0), ("wrong-result", None), ("ok", 2.0), ("ok", 4.0), ("ok", 5.0)])
    assert side["status"] == 3 and side["median_s"] is None


def test_side_with_too_few_valid_runs_has_status_1(tmp_path):
    side = aggregator(tmp_path, [("ok", 3.0), ("failed", None), ("ok", 2.0), ("invalid", None), ("ok", 5.0)])
    assert side["status"] == 1 and "3 of 5" in side["status_reason"]


# --- storage snapshot guards ------------------------------------------------------------------------------------

class LocalRunner:
    def run(self, script, timeout=60):
        result = subprocess.run(["sh", "-s"], input=script, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise SnapshotError(f"exit {result.returncode}: {result.stderr.strip()}")
        return result.stdout


def instance(tmp_path, stop="true", running="false"):
    root = tmp_path / "bench"
    (root / "data").mkdir(parents=True)
    (root / "data" / "db").write_text("v1")
    spec = {"instance_dir": str(root), "stop": stop, "start": "true", "running_check": running, "stop_wait_s": 1}
    return root, StorageSnapshot(spec, LocalRunner(), lambda: None)


def test_snapshot_refuses_paths_outside_the_instance(tmp_path):
    with pytest.raises(SnapshotError):
        StorageSnapshot({"instance_dir": "/opt/bench", "data_dir": "/var/lib/stalwart/data", "stop": "x", "start": "y"},
                        LocalRunner(), lambda: None)
    with pytest.raises(SnapshotError):
        StorageSnapshot({"instance_dir": "/opt/bench", "data_dir": "/opt/bench/../prod", "stop": "x", "start": "y"},
                        LocalRunner(), lambda: None)


def test_snapshot_needs_both_markers_and_a_stopped_instance(tmp_path):
    root, snapshot = instance(tmp_path)
    with pytest.raises(SnapshotError, match="BENCHMARK-INSTANCE"):
        snapshot.take("s1")
    (root / "BENCHMARK-INSTANCE").touch()
    with pytest.raises(SnapshotError, match="BENCHMARK-DATA"):
        snapshot.take("s1")
    (root / "data" / "BENCHMARK-DATA").touch()
    snapshot.take("s1")
    (root / "data" / "db").write_text("v2")
    snapshot.restore("s1")
    assert (root / "data" / "db").read_text() == "v1"
    (root / "data" / "db").write_text("v3")
    _, failing_stop = instance(tmp_path / "x", stop="false")
    (tmp_path / "x" / "bench" / "BENCHMARK-INSTANCE").touch()
    (tmp_path / "x" / "bench" / "data" / "BENCHMARK-DATA").touch()
    with pytest.raises(SnapshotError, match="exit 4"):
        failing_stop.take("s1")
    _, still_running = instance(tmp_path / "y", running="true")
    (tmp_path / "y" / "bench" / "BENCHMARK-INSTANCE").touch()
    (tmp_path / "y" / "bench" / "data" / "BENCHMARK-DATA").touch()
    with pytest.raises(SnapshotError, match="exit 5"):
        still_running.take("s1")
    assert (tmp_path / "y" / "bench" / "data" / "db").read_text() == "v1", "nothing touched while running"


def test_snapshot_refuses_a_symlinked_data_dir(tmp_path):
    root, snapshot = instance(tmp_path)
    (root / "BENCHMARK-INSTANCE").touch()
    outside = tmp_path / "production"
    outside.mkdir()
    (outside / "BENCHMARK-DATA").touch()
    (root / "data" / "db").unlink()
    (root / "data").rmdir()
    (root / "data").symlink_to(outside)
    with pytest.raises(SnapshotError, match="outside"):
        snapshot.restore("s1")
    assert outside.exists()


# --- server log evidence --------------------------------------------------------------------------------------

LINES = """2026-10-18T20:37:10Z DEBUG HTTP request URL (http.request-url) listenerId = "http", localPort = 443, remoteIp = 192.0.2.10, remotePort = 44078, url = "/jmap/session"
2026-10-18T20:37:11Z INFO Authentication successful (auth.success) listenerId = "http", localPort = 443, remoteIp = 192.0.2.10, remotePort = 44090, accountName = "bench@example.org", accountId = 2
2026-10-18T20:37:12Z DEBUG HTTP request URL (http.request-url) listenerId = "http", localPort = 443, remoteIp = 192.0.2.10, remotePort = 44090, url = "/jmap/download/c/abc/x"
2026-10-18T20:37:20Z DEBUG IMAP connection started (imap.connection-start) listenerId = "imap", localPort = 993, remoteIp = 52.97.146.1, remotePort = 48416
2026-10-18T20:37:21Z INFO Authentication successful (auth.success) listenerId = "imap", localPort = 993, remoteIp = 52.97.146.1, remotePort = 48416, accountName = "bench@example.org", accountId = 2
2026-10-18T20:37:22Z DEBUG IMAP FETCH command (imap.fetch) listenerId = "imap", localPort = 993, remoteIp = 52.97.146.1, remotePort = 48416, accountId = 2, mailboxId = 0, documentId = [2001, 2002, 2003], details = ["Uid", "BodySection { peek: true, sections: [], partial: None }"], elapsed = 0ms
2026-10-18T20:37:23Z DEBUG IMAP FETCH command (imap.fetch) listenerId = "imap", localPort = 993, remoteIp = 52.97.146.1, remotePort = 48416, accountId = 2, mailboxId = 0, documentId = [2004], details = ["Uid", "BodySection { peek: true, sections: [Header], partial: None }"], elapsed = 0ms
2026-10-18T20:37:24Z DEBUG IMAP FETCH command (imap.fetch) listenerId = "imap", localPort = 993, remoteIp = 52.97.146.1, remotePort = 48416, accountId = 2, mailboxId = 0, documentId = [2002, 2005], details = ["Rfc822"], elapsed = 0ms"""


def test_log_lines_parse():
    events = [LogEvent.parse(line) for line in LINES.splitlines()]
    fetch = events[5]
    assert fetch.event == "imap.fetch" and fetch.source == "52.97.146.1"
    assert fetch.fields["documentId"] == [2001, 2002, 2003]
    assert FetchKinds.full_content(fetch.fields["details"])
    assert not FetchKinds.full_content(events[6].fields["details"])
    assert events[1].fields["accountName"] == "bench@example.org" and events[1].protocol == "http"
    assert StalwartIds.document_id("eaaab1r") == 2001 and StalwartIds.document_id("h7maaab1t") == 2003


def server_log(tmp_path) -> ServerLog:
    config = Config({"workdir": str(tmp_path), "account": {"username": "bench@example.org"},
                     "server": {"log": {"path": "x", "benchmark_ips": ["192.0.2.10"]}}}, tmp_path)
    log = ServerLog(config, None)
    log.owners.cache["52.97.146.1"] = {"ip": "52.97.146.1", "owner": "Microsoft Corporation", "asn": "AS8075",
                                       "as_holder": "MICROSOFT-CORP-MSN-AS-BLOCK", "prefix": "52.96.0.0/14"}
    return log


def test_evidence_report_counts_logins_and_full_fetches(tmp_path):
    log = server_log(tmp_path)
    events = [LogEvent.parse(line) for line in LINES.splitlines()]
    report = log.report(events, {2001: 100, 2002: 200, 2003: 300, 2004: 400, 2005: 500})
    assert report["logins"] == {"benchmark": 1, "cloud": 1, "other": 0}
    assert report["full_messages"]["cloud"] == 4 and report["full_bytes"]["cloud"] == 1100
    sources = {s["source"]: s for s in report["sources"]}
    assert "192.0.2.10" not in json.dumps(report), "the benchmark computer's address isn't published"
    assert sources["benchmark computer"]["downloads"] == 1
    assert sources["52.96.0.0/14"]["asn"] == "AS8075" and sources["52.96.0.0/14"]["header_messages"] == 1
    assert "52.97.146.1" not in json.dumps(report), "single addresses aren't published, only networks"
    assert report["header_messages"]["cloud"] == 1


def test_evidence_summary_values(tmp_path):
    log = server_log(tmp_path)
    events = [LogEvent.parse(line) for line in LINES.splitlines()]
    parula_window = log.report(events[:3], None)
    outlook_window = log.report(events[3:], {2001: 1e8, 2002: 1e8, 2003: 1e8, 2005: 1e8})
    after = log.report([], None)
    run = lambda window, removal=None: {"run": "run-1", "server_evidence": {"windows": {
        "until_removal": window, **({"after_removal": removal} if removal else {})}}}
    sides = {"left": {"name": "Parula", "runs": [run(parula_window)]},
             "right": {"name": "new Outlook", "runs": [run(outlook_window, after)]}}
    summary = EvidenceSummary("C4", "T1", sides, {"right"}).compute()
    assert summary["values"]["left_direct_only"] == 1
    assert summary["values"]["right_direct_only"] == 0
    assert summary["values"]["cloud_login_confirmed"] == 1
    assert summary["values"]["cloud_fetched_messages"] == 4 and summary["values"]["cloud_fetched_gb"] == 0.4
    assert summary["values"]["cloud_asn"] == "AS8075" and summary["values"]["cloud_logins_after_removal"] == 0
    assert summary["values"]["cloud_fetched_headers"] == 1


# --- texts ---------------------------------------------------------------------------------------------------

def test_spoken_durations_match_the_voice_over_rules():
    assert SpokenDuration.text(9.62, "en") == "9.6 seconds"
    assert SpokenDuration.text(9.62, "de") == "9,6 Sekunden"
    assert SpokenDuration.text(34.4, "en") == "34 seconds"
    assert SpokenDuration.text(94, "en") == "1 minute 34"
    assert SpokenDuration.text(1862, "en") == "31 minutes"
    assert SpokenDuration.text(4320, "de") == "1 Stunde 12 Minuten"
    assert SpokenDuration.text(7200, "en") == "2 hours"


def test_text_comparisons_are_false_like_the_validator():
    values = NarrationValues("en")
    values.set_text("env.C2.os", "Linux")
    assert not Condition("env.C2.os == 1").evaluate(values.raw)


def test_method_template_blocks():
    values = NarrationValues("en")
    values.set_count("env.C4.right_protocol_default", 1)
    values.set_text("app.C4.left", "Parula 1.0")
    text, missing = MethodTemplate.render("{{app.C4.left}}{{#if env.C4.right_protocol_default == 1}}, default"
                                          "{{else}}, chosen{{/if}}. {{page_url}}", values)
    assert text == "Parula 1.0, default. –" and missing == ["page_url"]


def test_secrets_are_redacted():
    variables = TextVariables({"account.password": "S3cret!", "account.email": "a@example.org"}, {"account.password"})
    assert variables.redact("xdotool type S3cret! failed") == "xdotool type <secret> failed"
    assert variables.is_secret("${account.password}") and not variables.is_secret("${account.email}")


def test_inbox_profile_has_exact_attachments():
    spec = CorpusSpec.from_dict({"folders": [{"name": "Inbox", "count": 400, "role": "inbox"}],
                                 "attachment_messages": 4})
    generator = CorpusGenerator(spec)
    with_attachment = [m for m in generator.messages() if m.attachment_count]
    assert len(with_attachment) == 4 and all(m.attachment_count == 1 for m in with_attachment)
    import email
    from email import policy
    part = next(email.message_from_bytes(with_attachment[0].raw, policy=policy.default).iter_attachments())
    assert len(part.get_content()) == 1_000_000
    import random
    assert len(SyntheticFiles(random.Random(1)).exact_pdf(1_000_000, "x").data) == 1_000_000
    assert CorpusSpec.from_dict(None).folders[0].count == 30000


def synthetic_results(outcome: str) -> dict:
    def side(name, median, status=0):
        return {"name": name, "version": "1.0", "protocol": "IMAP", "os": "Linux", "status": status,
                "median_s": median if status == 0 else None, "min_s": median * 0.95 if status == 0 else None,
                "max_s": median * 1.05 if status == 0 else None, "actions": 5, "first_s": {"median_s": 1.2},
                "timeout_s": 7200.0, "timed_out_runs": 0, "runs": []}
    comparisons = {}
    for c, (left, right) in {"C1": (8.0, 40.0), "C2": (8.0, 60.0), "C3": (10.0, 180.0), "C4": (10.0, 1800.0)}.items():
        right_status = {"normal": 0, "timeout": 2, "differs": 3}[outcome]
        task = {"title": {"en": "T"}, "left": side("Parula", left), "right": side("Other", right, right_status)}
        task["ratio"] = right / left if right_status == 0 else None
        evidence = {"values": {"left_direct_only": 1, "right_direct_only": 0}}
        if c in ("C1", "C2"):
            evidence["values"]["cpu_pressure"] = 0.8
        if c == "C4":
            evidence["values"].update({"cloud_login_confirmed": 1, "cloud_fetched_messages": 30000,
                                       "cloud_fetched_gb": 33.6, "cloud_ip_owner": "Microsoft Corporation",
                                       "cloud_asn": "AS8075", "cloud_logins_after_removal": 0,
                                       "removal_watch_min": 10, "right_logged_runs": 6,
                                       "right_direct_connections": 0, "right_mail_port_elsewhere": 0,
                                       "right_inbox_complete": 1, "right_inbox_counted": 1,
                                       "right_remote_owner": "Microsoft Corporation", "right_remote_asn": "AS8075",
                                       "right_remote_microsoft": 1, "right_remote_microsoft_share": 97})
        comparisons[c] = {"os": "Linux", "tasks": {"T1": task}, "evidence": evidence}
    environment = {c: {"date": "2026-10-20", "os": "Debian 13", "cpu": "CPU", "ram": "32 GB",
                       "display": {"resolution": "2560x1440"}, "server": {"version": "0.16.26"},
                       "rtt_ms": {"imap_connect": 12.3}} for c in comparisons}
    return {"runs": {"measured": 5}, "corpus": {"messages": 30000, "inbox_messages": 30000},
            "comparisons": comparisons, "environment": environment}


def test_every_variant_narration_resolves_without_spoken_placeholders():
    """Set BENCH_VOICEOVER=<the voice-over directory> to check the real narration files (m17)."""
    import os
    from benchlib.compose import ValuesBuilder
    from benchlib.narration import Narration
    root = Path(os.environ.get("BENCH_VOICEOVER", ""))
    files = sorted((root / "variants").glob("narration.*.*.json")) if root.is_dir() else []
    if not files:
        pytest.skip("BENCH_VOICEOVER not set")
    variants = json.loads((root / "variants" / "variants.json").read_text())
    facts = {"server_ours": 1, **{c: {"right_protocol_default": 1} for c in ("C1", "C2", "C3", "C4")}}
    facts["C4"].update({"cloud_sync_confirmed": 1, "dialog_text": "Sync with the Microsoft Cloud",
                        "microsoft_footage": 1})
    for path in files:
        _, language, variant = path.stem.split(".")
        for outcome in ("normal", "timeout", "differs"):
            config = Config({"workdir": "/nonexistent"}, Path("."))
            values = ValuesBuilder(config, synthetic_results(outcome), language, facts).build()
            chosen = Narration.load(path).resolve(values, variants.get(variant))
            for segment in chosen:
                assert not segment.get("missing"), f"{path.name} {outcome} {segment['id']}: {segment['missing']}"


def test_command_speech_engine_synthesizes_the_chosen_lines(tmp_path):
    from benchlib.speech import SpeechEngine, VoiceSynthesizer
    writer = ("import sys, wave; text = sys.stdin.read(); w = wave.open(sys.argv[1], 'wb'); w.setnchannels(1); "
              "w.setsampwidth(2); w.setframerate(48000); w.writeframes(b'\\0\\0' * 4800 * len(text.split())); w.close()")
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"model")
    config = Config({"workdir": str(tmp_path), "speech": {"en": {
        "engine": "command", "command": [sys.executable, "-c", writer, "{out}"], "model": str(model),
        "voice": "test-voice", "lexicon": {"JMAP": "Jay-Map"}}}}, tmp_path)
    engine = SpeechEngine.create(config, "en")
    assert engine.prepared("Parula with JMAP") == "Parula with Jay-Map"
    script = [{"file": "c2-t1.before.wav", "text": "Who's first?"}, {"file": "end.wav", "text": "Parula dot app now"}]
    made = VoiceSynthesizer(engine, tmp_path / "voice", "en").run(script)
    assert [m["file"] for m in made["made"]] == ["c2-t1.before.wav", "end.wav"]
    assert made["made"][1]["seconds"] == 0.4 and made["credit"]["voice"] == "test-voice"
    assert len(made["credit"]["model_sha256"]) == 64
    assert VoiceSynthesizer(engine, tmp_path / "voice", "en").run(script)["made"] == [], "existing files are kept"


def test_method_templates_render_completely():
    """Set BENCH_VOICEOVER=<the voice-over directory> to render its real method templates (M8)."""
    import os
    import tempfile
    from benchlib.compose import ValuesBuilder
    from benchlib.method import MethodTexts
    root = Path(os.environ.get("BENCH_VOICEOVER", ""))
    if not (root / "method").is_dir():
        pytest.skip("BENCH_VOICEOVER not set")
    facts = {"server_ours": 1, **{c: {"right_protocol_default": 1} for c in ("C1", "C2", "C3", "C4")}}
    facts["C4"].update({"cloud_sync_confirmed": 1, "dialog_text": "Sync with the Microsoft Cloud",
                        "microsoft_footage": 1})
    with tempfile.TemporaryDirectory() as tmp:
        voice = Path(tmp) / "voice"
        for language in ("en", "de"):
            (voice / language).mkdir(parents=True)
            (voice / language / "credit.json").write_text(json.dumps({"engine": "Piper", "voice": "norman"}))
        config = Config({"workdir": tmp, "compose": {"voice_dir": str(voice)}, "deviations": ["start page off"],
                         "instrumentation": ["DevTools find the setup's fields; never a time."],
                         "publish": {"page_url": "https://parula.app/speed", "repo_url": "https://github.com/x",
                                     "imprint_url": "https://parula.app/imprint"}}, Path(tmp))
        variants = json.loads((root / "variants" / "variants.json").read_text())
        for template in sorted((root / "method").glob("*.youtube.txt")):
            variant, language = template.name.split(".")[:2]
            results = synthetic_results("normal")
            for comparison in results["comparisons"].values():
                for side in (comparison["tasks"]["T1"]["left"], comparison["tasks"]["T1"]["right"]):
                    side.update({"action_list": ["type the email address", "key Return"], "warmups": [],
                                 "median_run": "run-1",
                                 "runs": [{"run": "run-1", "order": 2, "warmup": False, "status": "ok",
                                           "total_s": side["median_s"], "attempt": 1, "tail": None}]})
            values = ValuesBuilder(config, results, language, facts).build()
            comparisons = sorted({s.split("-")[0].upper() for s in variants[variant] if s[:2] in ("c1", "c2", "c3", "c4")})
            report = MethodTexts(config, results, values, language, voice).render(
                root / "method", variant, Path(tmp) / "out", comparisons)
            assert report["youtube"]["characters"] <= 5000 and not report["youtube"]["missing"]


def test_voice_direction_pauses_before_the_last_sentence(tmp_path):
    from benchlib.speech import VoiceSynthesizer
    chunks = VoiceSynthesizer.chunks("New Outlook sent the password. Microsoft copied the emails. Password and "
                                     "emails: also at Microsoft.", [0.2])
    assert chunks == [("New Outlook sent the password. Microsoft copied the emails.", 0.0),
                      ("Password and emails: also at Microsoft.", 0.2)]
    assert VoiceSynthesizer.chunks("One sentence only.", [0.2]) == [("One sentence only.", 0.0)]
