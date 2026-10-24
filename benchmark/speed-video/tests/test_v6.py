"""Tests of spec "Interface extension v6": the network evidence values (warm-up runs, the app's own mail endpoint,
connections outside the app's process tree, Microsoft's share), the CPU stall share, the person-set facts, the
label bars, the publication gates and the method texts' manifest blocks. Run: python -m pytest tests/test_v6.py"""

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchlib.analyze import Aggregator  # noqa: E402
from benchlib.compose import ComposeError, Composer, PaneLabels, ShortSettings, ValuesBuilder  # noqa: E402
from benchlib.config import Config  # noqa: E402
from benchlib.environment import EnvironmentProbe  # noqa: E402
from benchlib.evidence import MicrosoftNetworks, RunEvidence, SessionEvidence  # noqa: E402
from benchlib.facts import FactsError, PersonFacts  # noqa: E402
from benchlib.method import ManifestTexts  # noqa: E402
from benchlib.netwatch import NetworkLog  # noqa: E402
from benchlib.pressure import CpuPressure, CpuPressureLog  # noqa: E402
from benchlib.resultfolder import ResultFolder  # noqa: E402
from benchlib.runner import Orchestrator  # noqa: E402

SERVER = "203.0.113.5"
ENDPOINTS = {"jmap_session_url": "https://mail.example.org/jmap/session", "imap": {"port": 993}}


class FakeOwners:
    table = {"52.97.1.1": ("Microsoft Corporation", "AS8075", "52.96.0.0/14"),
             "52.98.1.1": ("Contoso Ltd", "AS8068", "52.98.0.0/16"),
             "23.1.1.1": ("Akamai International B.V.", "AS20940", "23.0.0.0/12")}

    def lookup(self, ip):
        owner, asn, prefix = self.table.get(ip, ("unknown", None, None))
        return {"ip": ip, "owner": owner, "asn": asn, "prefix": prefix}


def write_run(root: Path, name: str, lines: list[dict], launch_t: float | None = 4.0, verify: dict | None = None,
              window=(10.0, 20.0), script_pid: int | None = None) -> Path:
    run_dir = root / name
    run_dir.mkdir(parents=True)
    log = NetworkLog(run_dir / "network.jsonl")
    log.write("resolve", t=1.0, host="mail.example.org", addresses=[SERVER])
    log.write("mail_server", t=1.0, addresses=[SERVER], ports=[443, 465, 993], mail_only_ports=[993, 465, 143])
    log.write("header", t=1.0, version=1, os="windows", app="app", source="iphlpapi", poll_hz=10, root_pids=[1],
              **({"script_pid": script_pid} if script_pid is not None else {}))
    for line in lines:
        log.write(line.pop("type"), **line)
    log.close()
    events = [{"type": "clock", "t": 0.0, "label": "start", "utc": 1000.0}]
    if launch_t is not None:
        events.append({"type": "input", "t": launch_t + 0.5, "t_before": launch_t, "phase": "prepare",
                       "action": "launch"})
    (run_dir / "driver.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (run_dir / "analysis.json").write_text(json.dumps({"measured_window": {"from_t": window[0], "to_t": window[1]}}))
    (run_dir / "verify.json").write_text(json.dumps(verify if verify is not None else
                                                    {"inbox_complete": True, "basis": "count", "listed": 30000}))
    return run_dir


def conn(remote, port, local_port, pid=7, process="olk.exe"):
    return {"pid": pid, "process": process, "local": f"10.0.0.2:{local_port}", "remote": remote, "remote_port": port}


def opened(t, c, state="ESTABLISHED"):
    return {"type": "open", "t": t, **c, "state": state}


def closed(t, c):
    return {"type": "close", "t": t, **{k: c[k] for k in ("pid", "local", "remote", "remote_port")}}


def evidence(run_dir, protocol="IMAP"):
    return RunEvidence(run_dir, FakeOwners(), protocol=protocol, endpoints=ENDPOINTS).summarize()


def test_direct_only_needs_data_on_the_apps_own_mail_endpoint(tmp_path):
    https = conn(SERVER, 443, 5000, process="parula")
    jmap = write_run(tmp_path, "jmap", [opened(10.0, https), {"type": "bytes", "t": 12.0, **https, "received": 900000,
                                                              "sent": 10}])
    assert evidence(jmap, "JMAP")["direct_mail_connections"] == 1 and evidence(jmap, "JMAP")["direct_only"] is True
    probe = conn(SERVER, 443, 5001)
    autodiscover = write_run(tmp_path, "autodiscover", [opened(10.0, probe), closed(10.3, probe)])
    summary = evidence(autodiscover, "IMAP (via Microsoft cloud)")
    assert summary["mail_endpoint"] == {"protocol": "IMAP", "port": 993}
    assert summary["direct_connections"] == 1 and summary["direct_mail_connections"] == 0
    assert summary["direct_only"] is False, "one HTTPS request to the server's address isn't 'directly for its mail'"
    imap = conn(SERVER, 993, 5002, process="OUTLOOK.EXE")
    long_open = write_run(tmp_path, "imap", [opened(10.0, imap), closed(16.0, imap)])
    assert evidence(long_open)["direct_only"] is True, "open > 5 s without byte counts carries data (Windows)"


def test_outside_tree_connections_after_the_launch_count_but_not_leftovers(tmp_path):
    def outside(t, state, pid, port):
        return {"type": "open_outside_tree", "t": t, "pid": pid, "process": None, "local": f"10.0.0.2:{port}",
                "remote": SERVER, "remote_port": 993, "state": state}
    run_dir = write_run(tmp_path, "run", [outside(1.5, "ESTABLISHED", 4242, 6000),
                                          outside(5.0, "TIME_WAIT", 0, 6001),
                                          outside(6.0, "ESTABLISHED", 4242, 6002),
                                          outside(7.0, "SYN_SENT", 3000, 6003),
                                          outside(8.0, "CLOSE_WAIT", 3001, 6004)], script_pid=4242)
    summary = evidence(run_dir)
    assert summary["outside_tree_connections"] == 2
    assert summary["outside_tree_not_counted"] == {"before the app's launch": 1, "TIME_WAIT": 1, "the test script": 1}
    assert summary["server_connections"] == 2 and summary["direct_connections"] == 0


def test_every_connection_to_the_server_counts_whatever_the_port(tmp_path):
    http = conn(SERVER, 80, 5000)
    run_dir = write_run(tmp_path, "run", [opened(11.0, http), closed(11.2, http)])
    summary = evidence(run_dir)
    assert summary["direct_connections"] == 0 and summary["server_connections"] == 1


def test_inbox_basis_and_completeness(tmp_path):
    oldest_only = write_run(tmp_path, "a", [], verify={"inbox_complete": True, "basis": "oldest message only"})
    assert (evidence(oldest_only)["inbox_complete"], evidence(oldest_only)["inbox_basis"]) == (None, "oldest message only")
    linux = write_run(tmp_path, "b", [], verify={"inbox_complete": True, "listed": 30000})
    assert evidence(linux)["inbox_basis"] == "count" and evidence(linux)["inbox_complete"] is True
    unread = write_run(tmp_path, "c", [], verify={"inbox_complete": True, "basis": "unread count", "listed": None})
    assert evidence(unread)["inbox_basis"] == "unread count"


def test_microsoft_networks_and_share(tmp_path):
    rule = MicrosoftNetworks()
    assert rule.registered("Microsoft Corporation", "AS1") and rule.registered("x", "AS8075")
    assert rule.registered(None, None, "MICROSOFT-CORP-MSN-AS-BLOCK - Microsoft Corporation")
    assert not rule.registered("Akamai International B.V.", "AS20940")
    assert MicrosoftNetworks(["8075"]).asns == ["AS8075"]
    lines = []
    for n, remote in enumerate(["52.97.1.1", "52.97.1.1", "52.98.1.1", "23.1.1.1"]):
        c = conn(remote, 443, 6000 + n)
        lines += [opened(12.0, c), closed(13.0, c)]
    before = conn("23.1.1.1", 443, 6100)
    lines += [opened(2.0, before), closed(3.0, before)]
    summary = evidence(write_run(tmp_path, "run", lines))
    assert summary["connections_measured"] == 4 and summary["remote_microsoft_share"] == 75
    assert {n["owner"]: n["microsoft"] for n in summary["remote_networks"]} == {
        "Microsoft Corporation": True, "Contoso Ltd": True, "Akamai International B.V.": False}


def cloud_run(root, name, extra=(), verify=None):
    lines = []
    for n in range(3):
        c = conn("52.97.1.1", 443, 7000 + n)
        lines += [opened(12.0, c), closed(14.0, c)]
    return write_run(root, name, lines + list(extra), verify=verify)


def parula_run(root, name):
    c = conn(SERVER, 443, 5000, process="parula")
    return write_run(root, name, [opened(10.0, c), {"type": "bytes", "t": 12.0, **c, "received": 900000, "sent": 1}])


def side(app, name, runs, warmups=(), attempts=()):
    def entries(dirs, protocol):
        return [{"run": d.name, "status": "ok", "evidence": evidence(d, protocol)} for d in dirs]
    protocol = "JMAP" if app.startswith("parula") else "IMAP"
    return {"app": app, "name": name, "runs": entries(runs, protocol), "warmups": entries(warmups, protocol),
            "failed_attempts": entries(attempts, protocol)}


def c4_values(right_runs, right_warmups=(), attempts=(), left_root=None):
    left_root = left_root or right_runs[0].parent / f"parula-{right_runs[0].name}"
    left = side("parula-jmap", "Parula", [parula_run(left_root, f"run-{n}") for n in range(2)],
                [parula_run(left_root, "warmup-1")])
    right = side("outlook-new", "Outlook (new)", right_runs, right_warmups, attempts)
    comparison = {"tasks": {"T1": {"left": left, "right": right}}}
    return SessionEvidence({"C4": comparison}, {"outlook-new"}).summarize("T1")["env"]


def test_c4_values_for_the_client_evidence_gate(tmp_path):
    env = c4_values([cloud_run(tmp_path, "run-1"), cloud_run(tmp_path, "run-2")], [cloud_run(tmp_path, "warmup-1")])
    assert env["C4.left_direct_only"] == 1 and env["C4.right_direct_only"] == 0
    assert env["C4.right_direct_connections"] == 0 and env["C4.right_mail_port_elsewhere"] == 0
    assert env["C4.right_logged_runs"] == 3, "warm-up included, so the gate's `> runs` holds"
    assert env["C4.right_inbox_complete"] == 1 and env["C4.right_inbox_counted"] == 1
    assert env["C4.right_remote_owner"] == "Microsoft Corporation" and env["C4.right_remote_asn"] == "AS8075"
    assert env["C4.right_remote_microsoft"] == 1 and env["C4.right_remote_microsoft_share"] == 100


def test_c4_values_count_the_warmup_and_failed_attempts_and_go_missing_without_logs(tmp_path):
    imap = conn(SERVER, 993, 8000)
    direct_warmup = cloud_run(tmp_path, "warmup-1", [opened(12.0, imap), closed(12.5, imap)])
    env = c4_values([cloud_run(tmp_path, "run-1")], [direct_warmup])
    assert env["C4.right_direct_connections"] == 1, "a connection in the warm-up run counts"
    elsewhere = conn("198.51.100.9", 993, 8001)
    attempt = cloud_run(tmp_path, "run-1.failed-1", [opened(12.0, elsewhere), closed(12.5, elsewhere)])
    env = c4_values([cloud_run(tmp_path, "run-2")], [cloud_run(tmp_path, "warmup-2")], [attempt])
    assert env["C4.right_mail_port_elsewhere"] == 1 and env["C4.right_direct_connections"] == 0
    unlogged = tmp_path / "warmup-3"
    left = side("parula-jmap", "Parula", [parula_run(tmp_path / "p", "run-1")])
    right = side("outlook-new", "Outlook (new)", [cloud_run(tmp_path, "run-3")])
    right["warmups"] = [{"run": unlogged.name, "status": "ok", "evidence": None}]
    env = SessionEvidence({"C4": {"tasks": {"T1": {"left": left, "right": right}}}}, {"outlook-new"}).summarize()["env"]
    for name in ("right_direct_connections", "right_mail_port_elsewhere", "right_logged_runs"):
        assert f"C4.{name}" not in env, f"{name} must be missing when a run has no network log"


def test_c4_inbox_counted_and_share_follow_the_weakest_run(tmp_path):
    weak = cloud_run(tmp_path, "run-2", verify={"inbox_complete": True, "basis": "unread count", "listed": None})
    akamai = conn("23.1.1.1", 443, 7100)
    shared = cloud_run(tmp_path, "run-1", [opened(12.0, akamai), closed(13.0, akamai)])
    env = c4_values([shared, weak], [cloud_run(tmp_path, "warmup-1")])
    assert env["C4.right_inbox_complete"] == 1 and env["C4.right_inbox_counted"] == 0
    assert env["C4.right_remote_microsoft_share"] == 75


def test_cpu_pressure_of_a_run_and_of_a_comparison(tmp_path):
    samples = [{"utc": 1000.0 + s, "some_us": int(s * 20000), "cgroup_some_us": int(s * 1000), "loadavg": [1.0, 1, 1]}
               for s in range(0, 40)]
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "driver.jsonl").write_text(json.dumps({"type": "clock", "t": 0.0, "label": "start", "utc": 1000.0}) + "\n")
    (run_dir / "analysis.json").write_text(json.dumps({"measured_window": {"from_t": 10.0, "to_t": 20.0}}))
    result = CpuPressure(samples, 5.0).write(run_dir)
    assert result["pct"] == 2.0 and result["cgroup_pct"] == 0.1 and result["basis"] == "measured window"
    assert result["over_limit"] is False and json.loads((run_dir / "cpu-pressure.json").read_text())["pct"] == 2.0
    assert CpuPressure(samples, 1.5).of_run(run_dir)["over_limit"] is True
    assert CpuPressure(samples[:15], 5.0).of_run(run_dir) is None, "the log must cover the window"
    task = {"left": {"runs": [{"status": "ok", "cpu_pressure": {"pct": 0.31}}]},
            "right": {"runs": [{"status": "ok", "cpu_pressure": {"pct": 1.24}}, {"status": "failed"}]}}
    assert SessionEvidence.cpu_pressure(task) == 1.3
    task["right"]["runs"].append({"status": "ok", "cpu_pressure": None})
    assert SessionEvidence.cpu_pressure(task) is None


def test_cpu_pressure_log_writes_samples(tmp_path):
    if not CpuPressureLog.available():
        pytest.skip("no /proc/pressure/cpu here")
    log = CpuPressureLog(tmp_path / "logs" / CpuPressureLog.file_name, interval_s=0.05).start()
    import time
    time.sleep(0.3)
    log.stop()
    samples = CpuPressureLog.read(log.path)
    assert len(samples) >= 2 and samples[-1]["some_us"] >= samples[0]["some_us"]


def test_a_stalled_run_is_recorded_again_and_counts_as_failed(tmp_path):
    folder = ResultFolder.create(tmp_path, "linux")
    log = folder.logs_dir / CpuPressureLog.file_name
    log.write_text("".join(json.dumps({"utc": 1000.0 + s, "some_us": s * 100000}) + "\n" for s in range(40)))
    run_dir = folder.run_dir("thunderbird", "T1", "run-1")
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({"run": "run-1", "status": "complete", "warmup": False}))
    (run_dir / "driver.jsonl").write_text(json.dumps({"type": "clock", "t": 0.0, "label": "start", "utc": 1000.0}) + "\n")
    (run_dir / "analysis.json").write_text(json.dumps({"status": "ok", "total_s": 9.0,
                                                       "measured_window": {"from_t": 10.0, "to_t": 20.0}}))
    config = Config({"runs": {"max_cpu_pressure_pct": 5}}, tmp_path)
    orchestrator = Orchestrator(config, None, lambda *_: None, None, log)
    assert orchestrator.outcome(run_dir) == "technical"
    assert orchestrator.done_before(run_dir) is False
    entry = Aggregator(config, None, folder).run_entry(run_dir)
    assert entry["status"] == "failed" and "CPU stall 10.0 %" in entry["reason"]


def test_facts_whitelist_names_every_measured_key():
    allowed = PersonFacts.default_allowed
    facts = PersonFacts({"_help": "x", "server_ours": 1, "C1": {"right_protocol_default": 1},
                         "C4": {"cloud_sync_confirmed": 1, "right_direct_connections": 0, "_note": "ok"},
                         "left_direct_only": 1}, allowed)
    assert facts.unknown_keys() == ["C4.right_direct_connections", "left_direct_only"]
    with pytest.raises(FactsError, match="C4.right_direct_connections, left_direct_only"):
        facts.check()
    template = PersonFacts.template(["C3", "C4"])
    assert template["server_ours"] is None and template["C3"] == {"right_protocol_default": None}
    assert set(template["C4"]) == {"right_protocol_default", "cloud_sync_confirmed", "dialog_text", "microsoft_footage"}
    assert PersonFacts(template).unknown_keys() == []


def test_facts_of_two_folders_merge_and_must_agree():
    linux = PersonFacts({"server_ours": 1, "C1": {"right_protocol_default": 1}}, source="linux")
    windows = PersonFacts({"server_ours": None, "C4": {"cloud_sync_confirmed": 1}}, source="windows")
    merged = PersonFacts.merged([linux, windows])
    assert merged.env() == {"server_ours": 1, "C1.right_protocol_default": 1, "C4.cloud_sync_confirmed": 1}
    with pytest.raises(FactsError, match="server_ours"):
        PersonFacts.merged([linux, PersonFacts({"server_ours": 0}, source="windows")])


def results_for(protocol="IMAP (via Microsoft cloud)") -> dict:
    def side(app, name, protocol):
        return {"app": app, "name": name, "protocol": protocol, "os": "Windows", "version": "1.2", "median_s": 9.0,
                "min_s": 8.0, "max_s": 10.0, "status": 0, "actions": 4, "runs": []}
    return {"runs": {"measured": 5}, "corpus": {"messages": 30000},
            "comparisons": {"C4": {"tasks": {"T1": {"left": side("parula-jmap", "Parula", "JMAP"),
                                                    "right": side("outlook-new", "Outlook (new)", protocol),
                                                    "ratio": 2.0}},
                                   "evidence": {"values": {"right_direct_connections": 0}}}},
            "environment": {}}


def test_values_take_person_set_facts_only():
    config = Config({}, Path("."))
    values = ValuesBuilder(config, results_for(), "en", {"server_ours": 1, "C4": {"cloud_sync_confirmed": 1}}).build()
    assert values.raw["env.server_ours"] == 1 and values.raw["env.C4.cloud_sync_confirmed"] == 1
    assert values.raw["env.C4.right_direct_connections"] == 0
    with pytest.raises(FactsError, match="C4.right_direct_connections"):
        ValuesBuilder(config, results_for(), "en", {"C4": {"right_direct_connections": 0}}).build()


def test_label_bars_use_the_narrations_names_and_protocols():
    settings = ShortSettings({"pane_protocol": {"left": "JMAP", "right": "IMAP"},
                              "pane_names": {"de": {"left": "Parula", "C4": "neues Outlook"}}}, {})
    labels = PaneLabels(settings, "de")
    task = results_for()["comparisons"]["C4"]["tasks"]["T1"]
    assert labels.bar("C4", "right", task["right"]) == "neues Outlook 1.2 · IMAP · Windows"
    assert labels.named("C4", "left", task["left"]) == "Parula (JMAP)"
    with pytest.raises(ComposeError, match="pane_protocol"):
        labels.bar("C4", "right", {**task["right"], "protocol": "Exchange"})
    plain = PaneLabels(ShortSettings(None, {}), "en")
    assert plain.bar("C4", "right", task["right"]) == "Outlook (new) 1.2 · IMAP (via Microsoft cloud) · Windows"


def test_a_variant_without_its_own_gate_is_not_published():
    composer = Composer.__new__(Composer)
    composer.settings = ShortSettings({"publish_when": {"c4": "env.server_ours == 1"},
                                       "publish_instead": {"c4": ["c4-neutral"]}}, {})
    composer.values = ValuesBuilder(Config({}, Path(".")), results_for(), "en", {"server_ours": 1}).build()
    composer.variant = "c4"
    assert composer.publication()["allowed"] is True
    composer.variant = "c4-neutral"
    assert composer.publication()["allowed"] is False and composer.publication()["ungated"] is True
    composer.values = ValuesBuilder(Config({}, Path(".")), results_for(), "en", {}).build()
    composer.variant = "c4"
    assert composer.publication()["allowed"] is False and composer.publication()["instead"] == []


def manifest_folder(root: Path, os_name: str, **manifest) -> Path:
    folder = ResultFolder.create(root, os_name)
    folder.write_manifest(**manifest)
    return folder.path


def test_manifest_blocks_per_folder_and_language(tmp_path):
    linux = manifest_folder(tmp_path / "l", "linux", instrumentation=["Linux line one.", "Linux line two."],
                            deviations=["Thunderbird: start page off."])
    windows = manifest_folder(tmp_path / "w", "windows", instrumentation={"en": ["Windows line."],
                                                                          "de": ["Windows-Zeile."]})
    config = Config({"translations": {"de": {"Linux line one.": "Linux-Zeile eins.",
                                             "Linux line two.": "Linux-Zeile zwei."}}}, tmp_path)
    english = ManifestTexts(config, "en")
    assert english.block([linux], "instrumentation", " ") == "Linux line one. Linux line two."
    assert english.block([linux, windows], "instrumentation", " ") == \
        "Linux: Linux line one. Linux line two. Windows: Windows line."
    assert english.block([linux], "deviations", "; ", list_items=True) == "Thunderbird: start page off"
    german = ManifestTexts(config, "de")
    assert german.block([linux, windows], "instrumentation", " ") == \
        "Linux: Linux-Zeile eins. Linux-Zeile zwei. Windows: Windows-Zeile."
    assert german.block([linux], "deviations", "; ", list_items=True) is None
    assert german.untranslated == {f"{linux.name}/manifest.json deviations": ["Thunderbird: start page off."]}


def test_every_shipped_deviation_and_instrumentation_line_has_a_german_text():
    root = Path(__file__).resolve().parent.parent
    table = yaml.safe_load((root / "translations" / "de.yaml").read_text(encoding="utf-8"))
    for config in (root / "config.linux.example.yaml", root / "windows" / "config.windows.yaml"):
        data = yaml.safe_load(config.read_text(encoding="utf-8"))
        for key in ("deviations", "instrumentation"):
            for line in data.get(key) or []:
                assert line in table, f"{config.name} {key}: no German text for {line[:60]}…"


def test_every_session_note_the_windows_and_linux_code_can_produce_has_a_german_text():
    import re
    from benchlib.sessionnotes import SessionNotes
    root = Path(__file__).resolve().parent.parent
    produced = set()
    for source in (root / "benchlib").glob("*.py"):
        produced |= set(re.findall(r"notes\.add\(\"(\w+)\"", source.read_text(encoding="utf-8")))
    assert produced == set(SessionNotes.templates), "every template is produced by the code, every note is a template"
    table = yaml.safe_load((root / "translations" / "de.yaml").read_text(encoding="utf-8"))
    texts = ManifestTexts(Config({}, root), "de")
    for name, template in SessionNotes.templates.items():
        placeholders = set(re.findall(r"\{(\w+)\}", template))
        assert template in table, f"no German text for the note template {name}"
        assert set(re.findall(r"\{(\w+)\}", table[template])) == placeholders, name
        notes = SessionNotes()
        notes.add(name, **{key: f"<{key} value 1,5>" for key in placeholders})
        german = texts.translated(notes.lines[0])
        assert german and all(f"<{key} value 1,5>" in german for key in placeholders), name
    assert texts.translated("Power plan: unchanged (381b4222-f694-41f0-9685-ff5bb260df2e)") == \
        "Energiesparplan: unverändert (381b4222-f694-41f0-9685-ff5bb260df2e)"
    assert texts.translated("Power plan: unchanged") is None


def test_session_notes_of_the_windows_settings_come_from_templates():
    from benchlib.winapps import SessionState, WindowsSettings

    class Commands:
        def __init__(self, outputs):
            self.outputs = outputs

        def run(self, command):
            return type("Result", (), {"stdout": self.outputs.get(" ".join(command[:2]), ""), "returncode": 0})()

    texts = ManifestTexts(Config({}, Path(__file__).resolve().parent.parent), "de")
    for outputs in ({"powercfg /getactivescheme": "GUID: 381b4222-f694-41f0-9685-ff5bb260df2e",
                     "powercfg /list": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"},
                    {"powercfg /getactivescheme": "GUID: 381b4222-f694-41f0-9685-ff5bb260df2e"}, {}):
        state = SessionState(Path("/nonexistent") / "state.json")
        state.set = lambda key, value: None
        notes = WindowsSettings(state, Commands(outputs)).apply()
        assert len(notes) == 3 and all(texts.translated(line) for line in notes)


def test_a_network_without_an_rdap_owner_reads_unknown_owner_and_german_numbers_use_a_comma():
    from benchlib.method import MethodTexts
    from benchlib.narration import NarrationValues
    network = {"owner": None, "asn": "AS15169", "prefix": "8.8.8.0/24", "connections": 2}
    sides = {"left": {"runs_with_evidence": 1, "logged_runs": 1, "all_runs_logged": True, "direct_only": 1,
                      "inbox_complete": 1, "inbox_counted": 1,
                      "runs": [{"run": "run-1", "server_connections": 3, "remote_networks": [network]}]}}
    task = {"left": {"name": "Parula"}, "right": {"name": "Thunderbird"}}
    lines = SessionEvidence.lines(task, sides)
    assert lines[-1] == "Parula: also 2 connection(s) to unknown owner (AS15169, 8.8.8.0/24)"
    results = results_for()
    results["environment"]["C4"] = {"rtt_ms": {"imap_connect": 1.07, "https_connect": 1.02}, "ram": "48 GB",
                                    "server": {"software": "Stalwart", "version": "0.16.27"}}
    for language, rtt, owner in (("de", "1,07", "Eigentümer unbekannt"), ("en", "1.07", "unknown owner")):
        values = ValuesBuilder(Config({}, Path(".")), results, language, {}).build()
        assert values.text["env.C4.rtt_ms"] == rtt and values.text["env.C4.server"] == "0.16.27"
        texts = MethodTexts(Config({}, Path(".")), results, values, language, None)
        evidence = {"task": "T1", "sides": {"right": {"runs_with_evidence": 1, "runs": [
            {"run": "run-1", "server_connections": 0, "remote_networks": [network]}]}}}
        block = texts.client_evidence_block("C4", results["comparisons"]["C4"], evidence)
        assert f"{owner} (AS15169, 8.8.8.0/24)" in block and "None" not in block
    assert NarrationValues("de").recorded(30000) == "30.000" and NarrationValues("de").recorded("0.16.27") == "0.16.27"


def test_recorded_config_analyzes_another_computers_result_folder(tmp_path):
    local = Config({"workdir": str(tmp_path / "work"), "tools": {"ffmpeg": "/usr/bin/ffmpeg"},
                    "evidence": {"microsoft_asns": ["AS8075"]}}, tmp_path)
    manifest = {"config": {"workdir": "C:\\Users\\ben\\parula-speed-test/work", "tools": {"ffmpeg": "C:\\ff.exe"},
                           "apps": {"outlook-new": {"protocol": "IMAP (via Microsoft cloud)", "cloud_sync": True}},
                           "evidence": {"poll_hz": 10}, "comparisons": {"C4": {"left": "a", "right": "b"}}}}
    config = Config.recorded(manifest, local)
    assert config.workdir == tmp_path / "work" and config.tool("ffmpeg") == "/usr/bin/ffmpeg"
    assert config.app("outlook-new")["cloud_sync"] is True and config.get("evidence.poll_hz") == 10
    assert config.get("evidence.microsoft_asns") == ["AS8075"]
    assert config.comparison("C4") == {"left": "a", "right": "b"}


def test_recorded_config_takes_the_local_configs_environment_of_the_same_comparison(tmp_path):
    local = Config({"comparisons": {
        "C4": {"left": "x", "right": "y", "environment": {"server": {"software": "Stalwart", "version": "0.16.27"},
                                                          "ram_limit": "32 GB"}},
        "C9": {"left": "x", "right": "y", "environment": {"server": {"version": "1"}}}}}, tmp_path)
    manifest = {"config": {"comparisons": {
        "C3": {"left": "parula-jmap", "right": "outlook-classic", "session": "windows"},
        "C4": {"left": "parula-jmap", "right": "outlook-new", "session": "windows",
               "environment": {"server": {"software": "Stalwart", "host": "mail.pia.im"}, "gpu": "Intel"}}}}}
    config = Config.recorded(manifest, local)
    assert config.comparison("C4") == {"left": "parula-jmap", "right": "outlook-new", "session": "windows",
                                       "environment": {"server": {"software": "Stalwart", "host": "mail.pia.im",
                                                                  "version": "0.16.27"},
                                                       "gpu": "Intel", "ram_limit": "32 GB"}}
    assert "environment" not in config.comparison("C3") and "C9" not in config.get("comparisons")


def test_published_environment_names_the_containers_cpus_and_memory_limit():
    linux = EnvironmentProbe.published({"os": "Debian GNU/Linux 13", "cpu": "AMD Ryzen 5 3600 6-Core Processor",
                                        "cpu_cores": 12, "ram": "63 GB", "ram_limit": "48 GB"})
    assert linux["cpu"] == "AMD Ryzen 5 3600 6-Core Processor, 12 vCPUs"
    assert linux["ram"] == "48 GB" and linux["ram_host"] == "63 GB"
    windows = EnvironmentProbe.published({"os": "Windows 11 (10.0.26100)", "cpu": "Intel", "cpu_cores": 8, "ram": "32 GB"})
    assert windows["cpu"] == "Intel" and windows["ram"] == "32 GB"


def windows_folder(root: Path) -> ResultFolder:
    """A Windows session's result folder as the pinned script writes it (no recordings: the small zip), with the
    older config's protocol text for new Outlook."""
    folder = ResultFolder.create(root, "windows")
    corpus = {"profile": "inbox-30k", "attachment_messages": 1, "planted": [{"term": "kumquat", "count": 1, "field": "body"}],
              "folders": [{"name": "Inbox", "count": 30, "role": "inbox", "days_back_from": 100, "days_back_to": 0},
                          {"name": "Sent", "count": 0, "role": "sent"}]}
    config = {"workdir": "C:\\Users\\ben\\parula-speed-test/work", "server": {"mode": "account", "host": "mail.example.org"},
              "corpus": corpus, "display": {"platform": "windows"}, "runs": {"measured": 2, "warmup": 1},
              "apps": {"parula-jmap": {"name": "Parula", "protocol": "JMAP", "os": "Windows"},
                       "outlook-new": {"name": "Outlook (new)", "protocol": "IMAP (via Microsoft cloud)", "os": "Windows",
                                       "microsoft_ui": True, "cloud_sync": True}},
              "sessions": {"windows": {"apps": ["parula-jmap", "outlook-new"]}},
              "comparisons": {"C4": {"os": "Windows", "left": "parula-jmap", "right": "outlook-new", "tasks": ["T1"],
                                     "session": "windows"}},
              "instrumentation": ["Parula: the Chrome DevTools Protocol, as on Linux, found the setup's buttons."]}
    folder.write_manifest(config=config, runs={"measured": 2, "warmup": 1},
                          server={"mode": "account", "host": "mail.example.org", "endpoints": ENDPOINTS},
                          environment={"windows": {"os": "Windows 11 (10.0.26100)", "cpu": "Intel", "cpu_cores": 8,
                                                   "ram": "32 GB", "date": "2026-10-24"}})
    order = 0
    for run_id, warmup in (("warmup-1", True), ("run-1", False), ("run-2", False)):
        for app_id in ("parula-jmap", "outlook-new"):
            order += 1
            if app_id == "parula-jmap":
                c = conn(SERVER, 443, 5000 + order, process="parula.exe")
                lines = [opened(9.0, c), closed(19.0, c)]
            else:
                c = conn("52.97.1.1", 443, 7000 + order)
                leftover = {"type": "open_outside_tree", "t": 2.0, "pid": 0, "process": None, "local": "10.0.0.2:1",
                            "remote": SERVER, "remote_port": 993, "state": "TIME_WAIT"}
                lines = [leftover, opened(12.0, c), closed(14.0, c)]
            run_dir = write_run(folder.run_dir(app_id, "T1", run_id).parent, run_id, lines)
            (run_dir / "meta.json").write_text(json.dumps({"run": run_id, "app": app_id, "task": "T1", "warmup": warmup,
                                                           "order": order, "status": "complete"}))
            analysis = json.loads((run_dir / "analysis.json").read_text())
            analysis.update({"status": "ok", "total_s": 9.0 + order if app_id == "parula-jmap" else 600.0 + order})
            (run_dir / "analysis.json").write_text(json.dumps(analysis))
    return folder


def test_a_windows_result_folder_is_analyzed_again_here_from_its_files_alone(tmp_path):
    from benchlib.stages import Pipeline
    folder = windows_folder(tmp_path / "from-windows")
    work = tmp_path / "work"
    (work / "evidence").mkdir(parents=True)
    (work / "evidence" / "ip-owners.json").write_text(json.dumps({"52.97.1.1": {
        "ip": "52.97.1.1", "owner": "Microsoft Corporation", "asn": "AS8075", "as_holder": None,
        "prefix": "52.96.0.0/14"}}))
    config = Config.recorded(folder.manifest(), Config({"workdir": str(work)}, tmp_path))
    results = Pipeline(config, lambda *_: None, folder).analyze("C4")
    values = results["comparisons"]["C4"]["evidence"]["values"]
    assert values["left_direct_only"] == 1 and values["right_direct_only"] == 0
    assert values["right_direct_connections"] == 0 and values["right_logged_runs"] == 3
    assert values["right_remote_microsoft"] == 1 and values["right_remote_microsoft_share"] == 100
    assert values["right_inbox_counted"] == 1 and "cpu_pressure" not in values
    assert json.loads(folder.evidence_path.read_text())["env"]["C4.right_logged_runs"] == 3
    assert folder.manifest()["evidence_rules"]["microsoft_asns"][0].startswith("AS")
    facts = json.loads((folder.path / "facts.json").read_text())
    assert "server_ours" in facts and "cloud_sync_confirmed" in facts["C4"]
    task = results["comparisons"]["C4"]["tasks"]["T1"]
    labels = PaneLabels(ShortSettings({"pane_protocol": {"left": "JMAP", "right": "IMAP"},
                                       "pane_names": {"en": {"left": "Parula", "C4": "new Outlook"}}}, {}), "en")
    assert labels.bar("C4", "right", task["right"]) == "new Outlook · IMAP · Windows"
    assert "TIME_WAIT" in json.dumps(json.loads((folder.run_dir("outlook-new", "T1", "run-1") / "evidence.json")
                                                .read_text())["outside_tree_not_counted"])


# ---------------------------------------------------------------------------------------------------------------
# Decisions of 2026-10-23: CPU stall limit, server software from the config, the YouTube deviations' short form

def test_cpu_stall_limit_defaults_to_15_percent_and_null_only_records():
    assert CpuPressure.configured_limit(Config({}, Path("."))) == 15.0
    assert CpuPressure.configured_limit(Config({"runs": {"max_cpu_pressure_pct": None}}, Path("."))) is None
    assert CpuPressure.configured_limit(Config({"runs": {"max_cpu_pressure_pct": 8}}, Path("."))) == 8.0
    example = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.linux.example.yaml").read_text())
    assert example["runs"]["max_cpu_pressure_pct"] == 15


def test_server_software_comes_from_the_environment_record_with_an_optional_version():
    results = results_for()
    results["environment"] = {"C4": {"server": {"software": "Stalwart", "version": None, "host": "mail.example.org"}}}
    values = ValuesBuilder(Config({}, Path(".")), results, "en", {}).build()
    assert values.text["env.C4.server_software"] == "Stalwart" and "env.C4.server" not in values.text
    results["environment"] = {"C4": {"server": {"name": "Stalwart", "version": "0.16.26"}}}
    values = ValuesBuilder(Config({}, Path(".")), results, "en", {}).build()
    assert values.text["env.C4.server_software"] == "Stalwart" and values.text["env.C4.server"] == "0.16.26"
    probe = EnvironmentProbe(Config({"server": {"software": "Example Mail", "version": "2.1", "host": "h"}}, Path(".")))
    assert probe.server_version() == "2.1"
    for config in ("config.linux.example.yaml", "windows/config.windows.yaml"):
        data = yaml.safe_load((Path(__file__).resolve().parent.parent / config).read_text())
        assert data["server"]["software"] == "Stalwart" and "name" not in data["server"]


def test_youtube_short_form_of_the_deviations_counts_them_and_names_their_subjects(tmp_path):
    root = Path(__file__).resolve().parent.parent
    windows_lines = yaml.safe_load((root / "windows" / "config.windows.yaml").read_text())["deviations"]
    linux = manifest_folder(tmp_path / "l", "linux", deviations=["Test computer: a container.", "Thunderbird: start "
                                                                 "page off.", "Thunderbird: Marionette.", "No subject."])
    windows = manifest_folder(tmp_path / "w", "windows", deviations=windows_lines)
    english = ManifestTexts(Config({}, tmp_path), "en")
    assert english.block([linux], "deviations", "; ", True, summary=True) == "4 (Test computer, Thunderbird)"
    assert english.block([linux, windows], "deviations", "; ", True, summary=True) == \
        "Linux: 4 (Test computer, Thunderbird); Windows: 3 (Windows, Parula)"
    assert ManifestTexts.summary([]) == "" and ManifestTexts.summary(["Plain sentence"]) == "1"
