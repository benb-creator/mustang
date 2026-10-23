"""Tests of the account mode, the network evidence, the result folder, the completion gate and the setup flows
(pipeline v3). Run: python -m pytest tests/test_v3.py"""

import json
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchlib.account import AccountCheck, AccountServer, AccountSession, ImapSession  # noqa: E402
from benchlib.analyze import Aggregator, ListRows, RunAnalyzer  # noqa: E402
from benchlib.capture import LiveMonitor  # noqa: E402
from benchlib.config import Config  # noqa: E402
from benchlib.corpus import CorpusGenerator, CorpusSpec  # noqa: E402
from benchlib.evidence import RunEvidence, SessionEvidence  # noqa: E402
from benchlib.flows import Flows  # noqa: E402
from benchlib.netwatch import NetworkLog, ProcNet, SsOutput  # noqa: E402
from benchlib.probe import AppProbe, Element  # noqa: E402
from benchlib.resultfolder import ResultFolder, ResultFolderError  # noqa: E402
from benchlib.scenario import Step  # noqa: E402
from benchlib.settle import ChangeSeries, CompletionGate, Rect, SettleDetector, SettleParams  # noqa: E402


def small_corpus(count=40, attachments=2) -> CorpusGenerator:
    return CorpusGenerator(CorpusSpec.from_dict({
        "profile": "inbox-30k", "attachment_messages": attachments,
        "folders": [{"name": "Inbox", "count": count, "role": "inbox", "days_back_from": 100, "days_back_to": 0,
                     "seen_ratio": 0.9, "flagged_ratio": 0.1},
                    {"name": "Sent", "count": 0, "role": "sent"}, {"name": "Trash", "count": 0, "role": "trash"}],
        "planted": [{"term": "kumquat", "count": 3, "field": "body"}]}))


class FakeImap:
    """Folders and messages as an IMAP server holds them; records the repairs."""

    def __init__(self, folders: dict, special: dict, shared_prefixes: list | None = None):
        self.data = folders
        self.special = special
        self.shared_prefixes = shared_prefixes or []
        self.calls = []

    def foreign_prefixes(self):
        return self.shared_prefixes

    def folders(self):
        return [{"name": n, "flags": {self.special[n]} if n in self.special else set(), "delimiter": "/",
                 "special_use": self.special.get(n)} for n in self.data]

    def messages(self, name):
        return [dict(m) for m in self.data[name]]

    def move_uids(self, folder, uids, target):
        self.calls.append(("move", folder, sorted(uids), target))
        moving = [m for m in self.data[folder] if m["uid"] in uids]
        self.data[folder] = [m for m in self.data[folder] if m["uid"] not in uids]
        self.data[target] += moving

    def delete_uids(self, folder, uids):
        self.calls.append(("delete", folder, sorted(uids)))
        self.data[folder] = [m for m in self.data[folder] if m["uid"] not in uids]

    def store_flags(self, folder, changes):
        self.calls.append(("flags", folder, [c[0] for c in changes]))
        for uid, add, remove in changes:
            for m in self.data[folder]:
                if m["uid"] == uid:
                    m["flags"] = (set(m["flags"]) | add) - remove

    def delete_folder(self, name):
        self.calls.append(("delete-folder", name))
        del self.data[name]

    def create_folder(self, name, special_use):
        self.data[name] = []


def seeded_imap(generator: CorpusGenerator) -> FakeImap:
    inbox = [{"uid": i + 1, "message_id": generator.message_id("Inbox", i), "size": 1000,
              "flags": ImapSession.flags_for(generator.keywords("Inbox", i))} for i in range(40)]
    return FakeImap({"INBOX": inbox, "Sent Items": [], "Deleted Items": []},
                    {"Sent Items": "\\sent", "Deleted Items": "\\trash"})


def test_account_check_finds_and_repairs_every_kind_of_difference():
    generator = small_corpus()
    check = AccountCheck(None, generator, lambda *_: None)
    imap = seeded_imap(generator)
    assert check.inspect(imap).ok
    inbox = imap.data["INBOX"]
    inbox[0]["flags"] = set(inbox[0]["flags"]) | {"$Junk"}
    inbox[1]["flags"] = set(inbox[1]["flags"]) ^ {"\\Seen"}
    imap.data["Deleted Items"].append(inbox.pop(2))
    inbox.append({**inbox[3], "uid": 99})
    inbox.append({"uid": 100, "message_id": "<spam@example.net>", "size": 10, "flags": set()})
    imap.data["Templates"] = []
    removed = inbox.pop(10)["message_id"]
    state = check.inspect(imap)
    summary = state.summary(check.expected_counts())
    assert summary["misplaced_messages"] == 1 and summary["duplicate_messages"] == 1
    assert summary["foreign_messages"] == 1 and summary["flag_differences"] == 2
    assert summary["extra_folders"] == ["Templates"] and summary["missing_messages"] == 1
    assert summary["folders"]["Inbox"] == {"expected": 40, "actual": 40, "server_name": "INBOX"}
    state.missing = []
    repairs = check.repair(imap, state)
    assert {r["what"] for r in repairs} == {"messages moved back", "duplicates deleted",
                                           "messages not from the corpus deleted", "flags restored", "folder deleted"}
    after = check.inspect(imap)
    assert not (after.duplicates or after.misplaced or after.foreign or after.flag_changes or after.extra_folders)
    assert [m.message_id for m in after.missing] == [removed]


def test_account_check_leaves_other_users_and_shared_folders_alone():
    generator = small_corpus()
    imap = seeded_imap(generator)
    imap.data["Shared Folders/team/Inbox"] = [{"uid": 1, "message_id": "<team@example.net>", "size": 5, "flags": set()}]
    imap.shared_prefixes = ["Shared Folders/"]
    state = AccountCheck(None, generator, lambda *_: None).inspect(imap)
    assert state.ok and "Shared Folders/team/Inbox" not in state.folders


def test_account_expectations_name_the_oldest_and_newest_inbox_message():
    generator = small_corpus()
    expected = AccountSession(None, generator).expected
    assert expected["inbox_messages"] == 40
    assert expected["inbox_oldest_message_id"] == generator.message_id("Inbox", 0)
    assert expected["inbox_oldest_subject"] == generator.subject("Inbox", 0)
    assert generator.envelope("Inbox", 0).date < generator.envelope("Inbox", 39).date


def test_config_derives_endpoints_from_the_host_and_redacts_the_account(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("server: {host: mail.example.org}\naccount: {email: bench@example.org, password_env: X_PW}\n"
                    "speech: {de: {api_key_env: K, api_key: secret-value}}\n")
    config = Config.load(path)
    assert config.get("server.jmap_session_url") == "https://mail.example.org/.well-known/jmap"
    assert config.get("server.imap") == {"host": "mail.example.org", "port": 993, "tls": True}
    redacted = config.redacted()
    assert redacted["account"]["email"] == "<redacted>@example.org"
    assert redacted["speech"]["de"]["api_key"] == "<redacted>" and redacted["speech"]["de"]["api_key_env"] == "K"
    os.environ["X_PW"] = "pw"
    server = AccountServer.from_config(config)
    assert server.mail_hostnames() == {"mail.example.org"}


def test_proc_net_and_ss_parsing():
    tcp = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
           "   0: 0100007F:51E5 0100007F:9C40 01 00000000:00000000 00:00000000 00000000  1000        0 4242 1 0\n")
    entry = ProcNet.parse(tcp)[0]
    assert entry == {"local": "127.0.0.1:20965", "remote": "127.0.0.1", "remote_port": 40000,
                     "state": "ESTABLISHED", "inode": 4242}
    tcp6 = ("  sl  local_address                         remote_address                        st\n"
            "   0: 0000000000000000FFFF00000200A8C0:C350 0000000000000000FFFF0000050071CB:03E1 01 0:0 0:0 0 1000 0 77"
            " 1\n")
    entry6 = ProcNet.parse(tcp6)[0]
    assert entry6["remote"] == "203.113.0.5" and entry6["remote_port"] == 993 and entry6["local"] == "192.168.0.2:50000"
    ss = ("ESTAB 0 0 192.168.0.2:50000 203.113.0.5:993\n"
          "\t cubic wscale:7,7 bytes_sent:1200 bytes_acked:1201 bytes_received:5000000 segs_out:10\n"
          "ESTAB 0 0 [::ffff:127.0.0.1]:41000 [::ffff:127.0.0.1]:28443\n\t cubic bytes_received:77\n")
    assert SsOutput.parse(ss) == [("192.168.0.2:50000", "203.113.0.5:993", 5000000, 1200),
                                  ("127.0.0.1:41000", "127.0.0.1:28443", 77, 0)]


class FakeOwners:
    table = {"52.97.1.1": ("Microsoft Corporation", "AS8075", "52.96.0.0/14"),
             "140.82.1.1": ("GitHub, Inc.", "AS36459", "140.82.112.0/20")}

    def lookup(self, ip):
        owner, asn, prefix = self.table.get(ip, ("unknown", None, None))
        return {"ip": ip, "owner": owner, "asn": asn, "prefix": prefix}


def network_run(tmp_path, name, lines, inbox_complete=True, window=(10.0, 20.0)) -> Path:
    run_dir = tmp_path / name
    run_dir.mkdir()
    log = NetworkLog(run_dir / "network.jsonl")
    log.write("resolve", t=1.0, host="mail.example.org", addresses=["203.0.113.5"])
    log.write("mail_server", t=1.0, addresses=["203.0.113.5"], ports=[443, 465, 993], mail_only_ports=[993, 465, 143])
    log.header("linux", "app", "proc", 10, [1])
    for line in lines:
        log.write(line.pop("type"), **line)
    log.close()
    (run_dir / "analysis.json").write_text(json.dumps({"measured_window": {"from_t": window[0], "to_t": window[1]}}))
    (run_dir / "verify.json").write_text(json.dumps({"inbox_complete": inbox_complete}))
    return run_dir


def test_run_evidence_counts_direct_connections_and_other_networks(tmp_path):
    conn = {"local": "10.0.0.2:5000", "remote": "203.0.113.5", "remote_port": 993}
    github = {"local": "10.0.0.2:5001", "remote": "140.82.1.1", "remote_port": 443}
    run_dir = network_run(tmp_path, "run-1", [
        {"type": "open", "t": 5.0, "pid": 7, "process": "parula", **conn, "state": "ESTABLISHED"},
        {"type": "bytes", "t": 15.0, **conn, "received": 400000, "sent": 10},
        {"type": "bytes", "t": 25.0, **conn, "received": 900000, "sent": 10},
        {"type": "open", "t": 2.0, "pid": 7, "process": "parula", **github, "state": "ESTABLISHED"},
        {"type": "close", "t": 3.0, "pid": 7, **github},
        {"type": "open", "t": 2.5, "pid": 8, "process": "parula", "local": "127.0.0.1:29222", "remote": "127.0.0.1",
         "remote_port": 40000, "state": "ESTABLISHED"},
    ])
    summary = RunEvidence(run_dir, FakeOwners(), protocol="IMAP", endpoints={"imap": {"port": 993}}).summarize()
    assert summary["direct_connections"] == 1 and summary["direct_ports"] == {"993": 1}
    assert summary["direct_mail_connections"] == 1
    assert summary["direct_bytes_received"] == 900000 and summary["direct_bytes_after_measured_end"] == 500000
    assert summary["loopback_connections"] == 1 and summary["direct_only"] is True
    network = summary["remote_networks"][0]
    assert network["owner"] == "GitHub, Inc." and network["connections"] == 1 and network["connections_measured"] == 0
    assert json.loads((run_dir / "evidence.json").read_text())["inbox_complete"] is True


def test_session_evidence_for_a_cloud_synced_app(tmp_path):
    microsoft = {"local": "10.0.0.2:6000", "remote": "52.97.1.1", "remote_port": 443}
    cloud = network_run(tmp_path, "cloud", [
        {"type": "open", "t": 12.0, "pid": 9, "process": "olk", **microsoft, "state": "ESTABLISHED"},
        {"type": "bytes", "t": 13.0, **microsoft, "received": 70000, "sent": 1}])
    imap_elsewhere = network_run(tmp_path, "elsewhere", [
        {"type": "open", "t": 12.0, "pid": 9, "process": "x", "local": "10.0.0.2:6001", "remote": "52.97.1.1",
         "remote_port": 993, "state": "ESTABLISHED"}])
    jmap = {"local": "10.0.0.2:6002", "remote": "203.0.113.5", "remote_port": 443}
    direct = network_run(tmp_path, "direct", [
        {"type": "open", "t": 12.0, "pid": 3, "process": "parula", **jmap, "state": "ESTABLISHED"},
        {"type": "bytes", "t": 13.0, **jmap, "received": 800000, "sent": 1}])
    runs = {}
    for name, protocol in (("cloud", "IMAP"), ("elsewhere", "IMAP"), ("direct", "JMAP")):
        runs[name] = {"run": name, "status": "ok", "evidence": RunEvidence(
            tmp_path / name, FakeOwners(), protocol=protocol,
            endpoints={"jmap_session_url": "https://mail.example.org/jmap/session", "imap": {"port": 993}}).summarize()}
    assert runs["elsewhere"]["evidence"]["mail_port_elsewhere"] == 1 and not runs["elsewhere"]["evidence"]["direct_only"]
    assert cloud.exists() and imap_elsewhere.exists() and direct.exists()
    comparison = {"tasks": {"T1": {"left": {"app": "parula-jmap", "name": "Parula", "runs": [runs["direct"]]},
                                   "right": {"app": "outlook-new", "name": "new Outlook", "runs": [runs["cloud"]]}}}}
    result = SessionEvidence({"C4": comparison}, {"outlook-new"}).summarize("T1")
    env = result["env"]
    assert env["C4.left_direct_only"] == 1 and env["C4.right_direct_only"] == 0
    assert env["C4.right_direct_connections"] == 0 and env["C4.right_inbox_complete"] == 1
    assert env["C4.right_remote_owner"] == "Microsoft Corporation" and env["C4.right_remote_asn"] == "AS8075"


def test_result_folder_layout(tmp_path):
    folder = ResultFolder.create(tmp_path, "linux")
    assert folder.name.startswith("results-linux-") and (folder.path / "runs").is_dir()
    again = ResultFolder.create(tmp_path, "linux")
    assert again.path != folder.path
    run = folder.run_dir("parula-jmap", "T1", "run-1")
    run.mkdir(parents=True)
    (run / "meta.json").write_text("{}")
    (run.parent / "run-2.failed-1").mkdir()
    (run.parent / "run-2.failed-1" / "meta.json").write_text("{}")
    assert folder.run_dirs("parula-jmap", "T1") == [run]
    assert folder.relative(run) == "runs/parula-jmap/T1/run-1"
    folder.write_manifest(environment={"linux": {"cpu": "x"}})
    opened = ResultFolder.open(folder.path)
    assert opened.manifest()["environment"]["linux"]["cpu"] == "x" and opened.manifest()["format"] == ResultFolder.format_name
    archive = opened.zip()
    assert archive.exists() and archive.parent == tmp_path
    with pytest.raises(ResultFolderError):
        ResultFolder.open(tmp_path)


def test_small_zip_holds_every_data_file_but_only_the_recordings_the_videos_use(tmp_path):
    import zipfile
    from benchlib.resultfolder import ReadmeFirst
    folder = ResultFolder.create(tmp_path, "windows")
    runs = {}
    for app in ("parula-jmap", "outlook-new"):
        for run in ("warmup-1", "run-1", "run-2", "run-3"):
            path = folder.run_dir(app, "T1", run)
            (path / "screenshots").mkdir(parents=True)
            for name in ("meta.json", "driver.jsonl", "network.jsonl", "evidence.json", "verify.json"):
                (path / name).write_text("{}")
            (path / "capture.mkv").write_bytes(b"\0" * 1000)
            (path / "screenshots" / "failure.png").write_bytes(b"png")
            runs[(app, run)] = folder.relative(path)
    side = lambda app, median, timeout=None: {"median_run": median, "timeout_run": timeout, "runs": [
        {"run": r, "dir": runs[(app, r)]} for r in ("run-1", "run-2", "run-3")]}
    (folder.results_path).write_text(json.dumps({"comparisons": {"C4": {"tasks": {"T1": {
        "left": side("parula-jmap", "run-2"), "right": side("outlook-new", None, "run-3")}}}}}))
    text = folder.package("Windows", False, "stopped with Ctrl+C", progress=lambda _: None)
    with zipfile.ZipFile(folder.small_zip_path) as small:
        names = set(small.namelist())
    recordings = sorted(n for n in names if n.endswith(".mkv"))
    assert recordings == [f"{folder.name}/runs/outlook-new/T1/run-3/capture.mkv",
                          f"{folder.name}/runs/parula-jmap/T1/run-2/capture.mkv"]
    assert f"{folder.name}/runs/parula-jmap/T1/warmup-1/driver.jsonl" in names
    assert f"{folder.name}/runs/outlook-new/T1/run-1/screenshots/failure.png" in names
    with zipfile.ZipFile(folder.zip_path) as full:
        assert len([n for n in full.namelist() if n.endswith(".mkv")]) == 8
    assert folder.small_zip_path.name in text and folder.zip_path.name in text and "being written" not in text
    assert "stopped before the end" in text and "Ctrl+C" in text
    assert (folder.path / "README-FIRST.txt").read_text(encoding="utf-8") == text
    assert ReadmeFirst.size(folder.small_zip_path).endswith("MB")


def test_a_step_turns_final_on_a_final_page_and_then_waits_for_the_full_inbox():
    from benchlib.driver import ScenarioDriver, TextVariables

    class InboxProbe(PageProbe):
        def __init__(self, pages, listed):
            super().__init__(pages)
            self.listed = list(listed)

        def inbox_listed(self, expected):
            listed = self.listed.pop(0)
            return {"complete": listed == expected["inbox_messages"], "listed": listed}

    log = MemoryLog()
    driver = ScenarioDriver(None, None, None, TextVariables({}), log,
                            probe=InboxProbe(["imap-form", "mail"], [100, 2000, 3000]),
                            expected={"inbox_messages": 3000})
    step = Step("connect", [], complete={"pages": ["cloud-sync"], "fail": []},
                becomes_final={"pages": ["mail"], "checks": {"complete": "inbox_listed", "verify_probe": True,
                                                             "after_end": "fail", "first_visible_list": True}})
    check = driver.completion_check(step)
    assert [check(), check(), check(), check()] == [False, False, False, True]
    assert step.final_reached and step.as_final().complete == "inbox_listed" and step.as_final().after_end == "fail"
    probes = [e for e in log.events if e["type"] == "probe"]
    assert [p["check"] for p in probes][1:] == ["inbox_listed"] * 3 and probes[1]["became_final"]
    events = [{"type": "step_start", "step": "connect", "checks": step.checks}, {"type": "step_final", "step": "connect"}]
    rebuilt = RunAnalyzer.flow_steps(events)[0]
    assert rebuilt.complete == "inbox_listed" and rebuilt.verify_probe and rebuilt.first_visible_list


def test_completion_gate_chooses_the_quiet_period_with_the_confirmation():
    times = np.arange(0, 20, 1 / 60)
    counts = np.zeros(len(times), dtype=np.int64)
    for t in (1.0, 1.5, 5.0, 9.0):
        counts[int(t * 60)] = 5000
    series = ChangeSeries(times, counts)
    params = SettleParams(quiet_s=1.0)
    detector = SettleDetector(params)
    without = detector.find_end(series, 0.5, 19.0)
    assert abs(without.end_time - 1.5) < 0.02
    gated = detector.find_end(series, 0.5, 19.0, CompletionGate(series, params, [], 9.6).accept)
    assert abs(gated.end_time - 9.0) < 0.02 and gated.rejected_candidates == 2
    early = detector.find_end(series, 0.5, 19.0, CompletionGate(series, params, [], 5.5).accept)
    assert abs(early.end_time - 5.0) < 0.02 and early.late_changes == 1


class FramePipe:
    """A fake live stream: frames written by a thread at 60 fps."""

    def __init__(self, changes_at: list[float], duration: float, size=(8, 8)):
        self.read_fd, self.write_fd = os.pipe()
        self.stream = os.fdopen(self.read_fd, "rb")
        self.changes_at = sorted(changes_at)
        self.duration = duration
        self.size = size
        self.started = time.perf_counter()
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        out = os.fdopen(self.write_fd, "wb")
        frame = np.zeros(self.size, dtype=np.uint8)
        pending = list(self.changes_at)
        while time.perf_counter() - self.started < self.duration:
            elapsed = time.perf_counter() - self.started
            while pending and pending[0] <= elapsed:
                pending.pop(0)
                frame = 255 - frame
            out.write(frame.tobytes())
            out.flush()
            time.sleep(1 / 60)
        out.close()


def test_live_gate_waits_for_the_probe_during_quiet_periods():
    pipe = FramePipe([0.1, 0.3, 1.0], 4.0)
    monitor = LiveMonitor(pipe.stream, 8, 8, 6, 2)
    calls = []

    def complete():
        elapsed = time.perf_counter() - pipe.started
        calls.append(elapsed)
        return elapsed > 1.5
    status, info = monitor.wait_settled(pipe.started, 0.3, 3.5, "test", complete=complete, probe_interval_s=0.2)
    assert status == "settled"
    assert all(c >= 0.6 for c in calls)
    assert calls[0] < 1.0 and info["confirmed_at"] - pipe.started > 1.5
    assert info["live_end"] - pipe.started == pytest.approx(1.0, abs=0.1)


def test_list_rows_first_frame_with_rows():
    rows = ListRows(Rect(0, 0, 40, 40))
    blank = np.full((40, 40, 3), 255, dtype=np.uint8)
    loading = blank.copy()
    listed = blank.copy()
    listed[5:8, 2:30] = 0
    listed[15:18, 2:30] = 0
    for frame in [blank] * 3 + [loading] * 3 + [listed] * 4:
        rows.add(frame)
    times = np.arange(10, dtype=np.float64)
    assert rows.first_rows(times, 0.5, 9.0) == 6.0


class FakeProbe(AppProbe):
    """Pages in order; each measured step moves to the next page."""
    method = "fake"

    def __init__(self, pages: list[str], values: dict | None = None, hosts: list[str] | None = None):
        self.pages = pages
        self.values = values or {}
        self.hosts = hosts or []

    def page(self):
        return self.pages[0]

    def found_hosts(self):
        return self.hosts if self.pages[0] == "found" else []

    def find(self, name):
        if name == "found.option":
            return None
        return Element(x=10, y=10, w=10, h=10, enabled=True, text=name, value=self.values.get(name), hit=True,
                       focused=name in self.values.get("focused", ()))

    def page_text(self):
        return self.pages[0]


class FakeDriver:
    def __init__(self, probe: FakeProbe):
        from benchlib.driver import TextVariables
        self.probe = probe
        self.inputs = []
        self.steps = []
        self.variables = TextVariables({"account.email": "a@example.org", "account.password": "pw",
                                        "account.name": "A", "server.jmap_url": "https://mail.example.org/jmap",
                                        "server.imap_host": "mail.example.org", "server.imap_port": "993",
                                        "server.smtp_host": "mail.example.org", "server.smtp_port": "465"},
                                       {"account.password"})
        self.log = type("Log", (), {"write": lambda *a, **k: None})()

    def do_actions(self, actions, phase, step=None, trigger=-1):
        self.inputs += [(phase, a.kind, a.arg) for a in actions]

    def run_step(self, step: Step):
        self.do_actions(step.actions, "step")
        self.steps.append((step.name, step.complete, step.verify_probe))
        if len(self.probe.pages) > 1:
            self.probe.pages.pop(0)
        if step.name == "show-details":
            self.probe.pages.insert(0, "manual-full")


def test_parula_flow_manual_jmap_counts_its_actions():
    probe = FakeProbe(["email", "manual", "finalize", "mail"], {"focused": ["setup.email"]})
    driver = FakeDriver(probe)
    path = Flows.run({"name": "parula-setup", "protocol": "jmap"}, driver, probe,
                     {"complete": "inbox_listed", "verify": True})
    assert [s[0] for s in driver.steps] == ["find-config", "show-details", "check-config", "open-inbox"]
    assert driver.steps[-1] == ("open-inbox", "inbox_listed", True)
    counted = [i for i in driver.inputs if i[0] == "step"]
    assert not [i for i in driver.inputs if i[0] == "prepare"]
    assert counted[0] == ("step", "type", "${account.email}")
    assert ("step", "type", "${server.jmap_url}") in counted and len(counted) == 13
    assert any("manual setup" in note for note in path) and any("JMAP URL" in note for note in path)


def test_parula_flow_clicks_into_the_address_field_when_it_has_no_cursor_and_skips_the_import():
    probe = FakeProbe(["import-accounts", "import-addressbooks", "initial", "email", "manual", "finalize", "mail"])
    driver = FakeDriver(probe)

    def do_actions(actions, phase, step=None, trigger=-1, original=driver.do_actions):
        original(actions, phase, step, trigger)
        if any(a.arg == "setup.add_email" for a in actions):
            probe.pages.pop(0)
    driver.do_actions = do_actions
    path = Flows.run({"name": "parula-setup", "protocol": "jmap"}, driver, probe,
                     {"complete": "inbox_listed", "verify": True})
    assert [s[0] for s in driver.steps][:2] == ["skip-import", "skip-addressbooks"]
    counted = [i for i in driver.inputs if i[0] == "step"]
    assert counted[:2] == [("step", "click", "setup.skip"), ("step", "click", "setup.skip")]
    assert ("step", "click", "setup.email") in counted
    assert any("import" in note for note in path)


def test_thunderbird_flow_manual_configuration():
    probe = FakeProbe(["email", "protocol-select", "manual", "password", "success", "mail", "inbox"],
                      {"manual.incoming_host": "mail.example.org", "manual.incoming_port": "993",
                       "manual.outgoing_host": "mail.example.org", "manual.outgoing_port": "465"})
    driver = FakeDriver(probe)
    Flows.run({"name": "thunderbird-setup"}, driver, probe, {"complete": "inbox_listed", "verify": True})
    assert [s[0] for s in driver.steps] == ["find-config", "choose-imap", "connect", "create-account", "finish",
                                           "open-inbox"]
    assert not any(i[2] == "ctrl+a" for i in driver.inputs)


def test_parula_flow_uses_a_found_configuration_of_the_accounts_server():
    probe = FakeProbe(["email", "found", "finalize", "mail"], {"focused": ["setup.email"]},
                      ["mail.example.org", "mail.example.org"])
    driver = FakeDriver(probe)
    Flows.run({"name": "parula-setup", "protocol": "imap"}, driver, probe, {"complete": "inbox_listed"})
    assert [s[0] for s in driver.steps] == ["find-config", "check-config", "open-inbox"]


def test_parula_flow_corrects_a_found_configuration_of_another_server_in_its_manual_setup():
    probe = FakeProbe(["email", "found", "manual", "finalize", "mail"], {"focused": ["setup.email"]},
                      ["mail.other.example.net", "mail.other.example.net"])
    driver = FakeDriver(probe)
    path = Flows.run({"name": "parula-setup", "protocol": "imap"}, driver, probe, {"complete": "inbox_listed"})
    assert [s[0] for s in driver.steps] == ["find-config", "manual-setup", "show-details", "check-config", "open-inbox"]
    assert ("step", "type", "${server.imap_host}") in driver.inputs
    assert any("mail.other.example.net" in note for note in path)


class FoundJmapProbe(FakeProbe):
    """Parula's found configuration offers JMAP (already selected)."""

    def find(self, name):
        if name == "found.option":
            return Element(x=1, y=1, w=1, h=1, enabled=True, checked=True)
        return super().find(name)


def test_parula_jmap_flow_corrects_a_found_jmap_configuration_of_another_server():
    probe = FoundJmapProbe(["email", "found", "manual", "finalize", "mail"], {"focused": ["setup.email"]},
                           ["jmap.other.example.net"])
    driver = FakeDriver(probe)
    path = Flows.run({"name": "parula-setup", "protocol": "jmap"}, driver, probe, {"complete": "inbox_listed"})
    assert [s[0] for s in driver.steps] == ["find-config", "manual-setup", "show-details", "check-config", "open-inbox"]
    assert ("step", "type", "${server.jmap_url}") in driver.inputs
    assert any("jmap.other.example.net" in note for note in path)


def test_parula_jmap_flow_uses_a_found_configuration_on_the_jmap_urls_host():
    probe = FoundJmapProbe(["email", "found", "finalize", "mail"], {"focused": ["setup.email"]}, ["jmap.example.org"])
    driver = FakeDriver(probe)
    driver.variables.values["server.jmap_url"] = "https://jmap.example.org/.well-known/jmap"
    Flows.run({"name": "parula-setup", "protocol": "jmap"}, driver, probe, {"complete": "inbox_listed"})
    assert [s[0] for s in driver.steps] == ["find-config", "check-config", "open-inbox"]


def test_thunderbird_flow_edits_a_found_configuration_of_another_server():
    probe = FakeProbe(["email", "found", "manual", "password", "success", "mail", "inbox"],
                      {"manual.incoming_port": "993", "manual.outgoing_port": "465"}, ["mail.other.example.net"])
    driver = FakeDriver(probe)
    path = Flows.run({"name": "thunderbird-setup"}, driver, probe, {"complete": "inbox_listed", "verify": True})
    assert [s[0] for s in driver.steps] == ["find-config", "edit-config", "connect", "create-account", "finish",
                                           "open-inbox"]
    assert ("step", "type", "${server.imap_host}") in driver.inputs
    assert ("step", "type", "${server.smtp_host}") in driver.inputs
    assert any("another server" in note for note in path)


def test_thunderbird_flow_uses_a_found_configuration_of_the_accounts_server():
    probe = FakeProbe(["email", "found", "password", "success", "mail", "inbox"], {},
                      ["mail.example.org", "mail.example.org"])
    driver = FakeDriver(probe)
    Flows.run({"name": "thunderbird-setup"}, driver, probe, {"complete": "inbox_listed", "verify": True})
    assert [s[0] for s in driver.steps] == ["find-config", "use-config", "create-account", "finish", "open-inbox"]


def test_flow_actions_come_from_the_median_run():
    side = {}
    runs = [{"run": "run-1", "user_actions": 13, "action_list": ["a"], "flow_path": ["manual"]},
            {"run": "run-2", "user_actions": 14, "action_list": ["b"], "flow_path": ["manual"]}]
    Aggregator.flow_actions(side, runs[0], runs)
    assert side["actions"] == 13 and side["actions_differ"] == {"run-2": 14} and side["flow_path"] == ["manual"]


class PageProbe(AppProbe):
    method = "fake"

    def __init__(self, pages):
        self.pages = list(pages)

    def page(self):
        return self.pages.pop(0)


class MemoryLog:
    def __init__(self):
        self.events = []

    def write(self, type, t=None, **fields):
        self.events.append({"type": type, **fields})
        return t


def test_page_completion_check_logs_every_probe_answer():
    from benchlib.driver import ScenarioDriver, TextVariables
    log = MemoryLog()
    driver = ScenarioDriver(None, None, None, TextVariables({}), log, probe=PageProbe(["busy:email", "password",
                                                                                     "error:password"]))
    step = Step("create-account", [], complete={"pages": ["success"], "fail": ["error:"]})
    check = driver.completion_check(step)
    assert [check(), check(), check()] == [False, False, True]
    answers = [(e["page"], e["complete"], e["failed"]) for e in log.events if e["type"] == "probe"]
    assert answers == [("busy:email", False, False), ("password", False, False), ("error:password", True, True)]


def test_completion_gate_allows_the_paint_after_the_probe_read_the_result():
    times = np.arange(0, 12, 1 / 60)
    counts = np.zeros(len(times), dtype=np.int64)
    for t in (2.0, 5.0, 5.05):
        counts[int(round(t * 60))] = 5000
    series = ChangeSeries(times, counts)
    params = SettleParams(quiet_s=1.0)
    result = SettleDetector(params).find_end(series, 1.0, 11.0, CompletionGate(series, params, [], 5.0).accept)
    assert abs(result.end_time - 5.05) < 0.02 and result.late_changes == 0


def test_merged_results_of_two_result_folders_remember_their_folders(tmp_path):
    from benchlib.stages import Pipeline
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"workdir: {tmp_path / 'work'}\nserver: {{host: mail.example.org}}\n"
                           "account: {email: a@example.org, password_env: X_PW}\n")
    config = Config.load(config_path)
    folders = []
    for os_name, comparison in (("linux", "C2"), ("windows", "C3")):
        folder = ResultFolder.create(tmp_path, os_name)
        run = folder.run_dir("parula-jmap", "T1", "run-1")
        run.mkdir(parents=True)
        (folder.results_path).write_text(json.dumps({
            "version": 3, "runs": {"measured": 5, "warmup": 1}, "corpus": {"inbox_messages": 30000},
            "environment": {comparison: {"os": os_name}},
            "comparisons": {comparison: {"tasks": {"T1": {"left": {"runs": [{"run": "run-1", "dir": folder.relative(run)}]}}}}}}))
        folders.append(folder)
    merged = Pipeline(config, lambda *_: None).merged_results([str(f.path) for f in folders])
    assert set(merged["comparisons"]) == {"C2", "C3"}
    assert merged["comparisons"]["C3"]["result_folder"] == str(folders[1].path)
    run_dir = Path(merged["comparisons"]["C3"]["result_folder"]) / \
        merged["comparisons"]["C3"]["tasks"]["T1"]["left"]["runs"][0]["dir"]
    assert run_dir == folders[1].run_dir("parula-jmap", "T1", "run-1")
    assert (folders[0].path / "facts.json").exists()


def test_marionette_client_frames_commands_and_answers():
    import socket
    from benchlib.marionette import MarionetteClient, MarionetteError
    server, client_end = socket.socketpair()

    def send(obj):
        data = json.dumps(obj).encode()
        server.sendall(b"%d:%s" % (len(data), data))

    def serve():
        send({"applicationType": "gecko", "marionetteProtocol": 3})
        buffer = b""
        for answer in ({"value": 42}, None):
            while b":" not in buffer:
                buffer += server.recv(4096)
            length, rest = buffer.split(b":", 1)
            while len(rest) < int(length):
                rest += server.recv(4096)
            message, buffer = json.loads(rest[:int(length)]), rest[int(length):]
            send([1, message[1], None if answer else {"error": "javascript error", "message": "boom"}, answer])

    thread = threading.Thread(target=serve)
    thread.start()
    client = MarionetteClient(client_end)
    assert client.execute("return 42;") == 42
    with pytest.raises(MarionetteError, match="boom"):
        client.execute("throw 1;")
    thread.join(5)


class FakeDevTools:
    """/json/list over HTTP and a WebSocket that answers Runtime.evaluate with the expression's length."""

    def __init__(self):
        import socket
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(4)
        self.port = self.listener.getsockname()[1]
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            threading.Thread(target=self.handle, args=(conn,), daemon=True).start()

    def handle(self, conn):
        import base64
        import hashlib
        request = b""
        while b"\r\n\r\n" not in request:
            request += conn.recv(4096)
        head = request.decode()
        if head.startswith("GET /json/list"):
            body = json.dumps([{"type": "page", "url": "file:///app/index.html",
                                "webSocketDebuggerUrl": f"ws://127.0.0.1:{self.port}/devtools/page/1"}]).encode()
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s"
                         % (len(body), body))
            conn.close()
            return
        key = next(line.split(":", 1)[1].strip() for line in head.split("\r\n") if line.lower().startswith("sec-websocket-key"))
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        while True:
            header = conn.recv(2)
            if len(header) < 2 or header[0] & 0x0F == 0x8:
                return
            length = header[1] & 0x7F
            if length == 126:
                length = int.from_bytes(conn.recv(2), "big")
            mask = conn.recv(4)
            payload = b""
            while len(payload) < length:
                payload += conn.recv(length - len(payload))
            message = json.loads(bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
            answer = json.dumps({"id": message["id"], "result": {"result": {
                "type": "number", "value": len(message["params"]["expression"])}}}).encode()
            frame = bytes([0x81, len(answer)]) if len(answer) < 126 else \
                bytes([0x81, 126]) + len(answer).to_bytes(2, "big")
            conn.sendall(frame + answer)


def test_cdp_client_finds_the_page_and_evaluates():
    from benchlib.cdp import CdpClient
    devtools = FakeDevTools()
    client = CdpClient.connect(devtools.port, 10, "index.html")
    assert client.evaluate("12345") == 5
    client.close()


def test_config_takes_host_and_address_from_the_environment(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text("server: {host: '${BENCH_SERVER}'}\naccount: {email: '${BENCH_EMAIL}'}\n"
                    "variables: {greeting: '${account.name}'}\n")
    monkeypatch.setenv("BENCH_SERVER", "mail.example.net")
    monkeypatch.setenv("BENCH_EMAIL", "bench@example.net")
    config = Config.load(path)
    assert config.get("server.imap.host") == "mail.example.net" and config.get("account.email") == "bench@example.net"
    assert config.get("variables.greeting") == "${account.name}"
    monkeypatch.delenv("BENCH_SERVER")
    with pytest.raises(Exception, match="BENCH_SERVER"):
        Config.load(path)


@pytest.mark.skipif(not Path("/proc/net/tcp").exists(), reason="Linux only")
def test_linux_watcher_logs_this_process_connections(tmp_path):
    import socket
    from benchlib.netwatch import LinuxConnectionWatcher
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    log = NetworkLog(tmp_path / "network.jsonl")
    watcher = LinuxConnectionWatcher(log, "test", lambda: [os.getpid()], poll_hz=20, ss="ss")
    watcher.start()
    client = socket.create_connection(listener.getsockname())
    server, _ = listener.accept()
    time.sleep(0.4)
    client.close()
    server.close()
    time.sleep(0.4)
    watcher.stop()
    log.close()
    events = NetworkLog.read(tmp_path / "network.jsonl")
    port = listener.getsockname()[1]
    opened = [e for e in events if e["type"] == "open" and e["remote_port"] == port]
    assert opened and opened[0]["pid"] == os.getpid() and opened[0]["remote"] == "127.0.0.1"
    assert any(e["type"] == "close" and e["remote_port"] == port for e in events)
    stats = next(e for e in events if e["type"] == "stats")
    assert stats["mean_interval_s"] < 0.2
    listener.close()


def test_probe_page_names():
    from benchlib.probe import ParulaProbe, ThunderbirdProbe

    class TB(ThunderbirdProbe):
        def __init__(self, state):
            super().__init__(0)
            self.fixed = state

        def state(self):
            return self.fixed
    hub = lambda view, note=None, kind=None: TB({"view": view, "notification": note, "notificationType": kind,
                                                 "folder": None, "tabs": ["mail3PaneTab"]})
    assert hub("email-auto-form").page() == "email"
    assert hub("email-auto-form", "Looking up configuration Show more").page() == "busy:email-auto-form"
    assert hub("email-manual-config-form", "Thunderbird found the correct settings", "success").page() == "manual:success"
    assert hub("email-password-form", "Login failed", "error").page() == "error:password"
    assert TB({"view": None, "folder": "imap://a@b/INBOX", "tabs": []}).page() == "inbox"
    assert TB({"view": None, "folder": None, "tabs": ["mail3PaneTab"]}).page() == "mail"

    class Parula(ParulaProbe):
        def __init__(self, state):
            super().__init__(0)
            self.fixed = {"headings": [], "text": "", "error": None, "radios": 0, "expanded": False, "counts": [],
                          **state}

        def state(self):
            return self.fixed
    assert Parula({"hash": "#/setup/initial"}).page() == "initial"
    assert Parula({"hash": "#/setup/mail", "headings": ["Manual configuration"]}).page() == "manual"
    assert Parula({"hash": "#/setup/mail", "headings": ["Manual configuration"], "expanded": True,
                   "error": "We could not find a configuration for example.com"}).page() == "error:manual-full"
    assert Parula({"hash": "#/setup/mail", "text": "a@b is working and ready"}).page() == "finalize"
    assert Parula({"hash": "#/setup/mail", "text": "We found a configuration", "radios": 2}).page() == "found"
    assert Parula({"hash": "#/mail", "counts": ["3000 mails"]}).inbox_listed({"inbox_messages": 3000})["complete"]
    assert not Parula({"hash": "#/mail", "counts": ["2,800 mails"]}).inbox_listed({"inbox_messages": 3000})["complete"]
