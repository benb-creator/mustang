"""Tests of the wrong-server rule: the check of the address's published mail configuration before the session (and
which setup path it gives the flows), the check of every run's mail connections afterwards, and how both appear in
the report. Run: python -m pytest tests/test_server_check.py"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchlib.analyze import ReportWriter  # noqa: E402
from benchlib.config import Config  # noqa: E402
from benchlib.discovery import HttpAnswer, PublishedConfig  # noqa: E402
from benchlib.netwatch import NetworkLog  # noqa: E402
from benchlib.resultfolder import ResultFolder  # noqa: E402
from benchlib.runner import Orchestrator, RunExecutor, SeriesStop  # noqa: E402
from benchlib.stages import Pipeline  # noqa: E402

EMAIL = "robin.sample@example.org"
DISPLAY = {"app_region": {"x": 0, "y": 0, "width": 1280, "height": 940}}


def autoconfig(host: str) -> str:
    return (f"<clientConfig version=\"1.1\"><emailProvider id=\"example.org\"><domain>example.org</domain>"
            f"<incomingServer type=\"imap\"><hostname>{host}</hostname><port>993</port></incomingServer>"
            f"<outgoingServer type=\"smtp\"><hostname>{host}</hostname><port>465</port></outgoingServer>"
            f"</emailProvider></clientConfig>")


def pox(*servers: str, redirect_address: str | None = None) -> str:
    protocols = "".join(f"<Protocol><Type>IMAP</Type><Server>{s}</Server></Protocol>" for s in servers)
    redirect = f"<RedirectAddr>{redirect_address}</RedirectAddr>" if redirect_address else ""
    return (f"<?xml version=\"1.0\"?><Autodiscover xmlns=\"http://schemas.microsoft.com/exchange/autodiscover/"
            f"responseschema/2006\"><Response xmlns=\"http://schemas.microsoft.com/exchange/autodiscover/outlook/"
            f"responseschema/2006a\"><Account>{protocols}{redirect}</Account></Response></Autodiscover>")


class FakeWeb:
    """Answers by URL prefix; every other URL: no such host."""

    def __init__(self, answers: dict):
        self.answers = answers
        self.requests = []

    def request(self, url, body=None, content_type=None):
        self.requests.append((url, body))
        for prefix, answer in self.answers.items():
            if url.startswith(prefix):
                return answer
        return HttpAnswer(None, error="Name or service not known")


class FakeDns:
    def __init__(self, records: dict | None):
        self.table = records
        self.used = "dns.example" if records is not None else None

    def records(self, name, kind):
        if self.table is None:
            return None
        return self.table.get((name, kind), [])


OWN_DNS = {("example.org", "MX"): ["10 mail.example.org."],
           ("_imaps._tcp.example.org", "SRV"): ["0 1 993 mail.example.org."],
           ("_submissions._tcp.example.org", "SRV"): ["0 1 465 mail.example.org."]}


def test_a_well_known_file_of_another_server_makes_the_setups_take_the_guarded_path():
    web = FakeWeb({"https://autoconfig.example.org/": HttpAnswer(200, autoconfig("mail.example.org")),
                   "https://example.org/.well-known/": HttpAnswer(200, autoconfig("mail.beonex.example")),
                   "https://autoconfig.thunderbird.net/": HttpAnswer(404),
                   "https://autodiscover.example.org/autodiscover/autodiscover.xml": HttpAnswer(200, pox("mail.example.org")),
                   "https://autodiscover.example.org/autodiscover/autodiscover.json":
                       HttpAnswer(200, json.dumps({"Protocol": "AutodiscoverV1",
                                                   "Url": "https://mail.example.org/autodiscover/autodiscover.xml"}))})
    found = PublishedConfig(EMAIL, {"mail.example.org", "MAIL.example.org."}, web, FakeDns(OWN_DNS)).check()
    assert found["guarded"] and found["other_hosts"] == ["mail.beonex.example"]
    assert found["other_sources"] == ["autoconfig (.well-known)"] and found["unchecked"] == []
    by_source = {s["source"]: s for s in found["sources"]}
    assert by_source["autoconfig"]["hosts"] == ["mail.example.org"]
    assert by_source["Autodiscover (JSON)"]["hosts"] == ["mail.example.org"]
    assert by_source["SRV _imaps._tcp"]["hosts"] == ["mail.example.org"] and by_source["SRV _imap._tcp"]["hosts"] == []
    assert by_source["ISPDB (Thunderbird)"]["status"] == 404 and by_source["ISPDB (Parula)"]["error"]
    assert "robin.sample" not in json.dumps(found) and "{address}" in by_source["autoconfig"]["url"]
    sent_address = sorted({url.split("/")[2] for url, body in web.requests if "robin.sample" in url + (body or "")})
    assert sent_address == ["autoconfig.example.org", "autodiscover.example.org", "example.org"]


def test_only_the_accounts_server_everywhere_lets_every_app_take_its_own_path():
    web = FakeWeb({"https://autoconfig.example.org/": HttpAnswer(200, autoconfig("%EMAILDOMAIN%")),
                   "https://example.org/.well-known/": HttpAnswer(200, "<html>not found</html"),
                   "https://autodiscover.example.org/autodiscover/autodiscover.xml": HttpAnswer(200, pox("example.org"))})
    found = PublishedConfig(EMAIL, {"example.org"}, web, FakeDns(OWN_DNS | {
        ("_imaps._tcp.example.org", "SRV"): ["0 1 993 example.org."],
        ("_submissions._tcp.example.org", "SRV"): ["0 0 0 ."]})).check()
    assert not found["guarded"] and found["other_hosts"] == [] and found["mx"] == ["mail.example.org"]
    well_known = next(s for s in found["sources"] if s["source"] == "autoconfig (.well-known)")
    assert well_known["error"] == "not a configuration" and well_known["hosts"] == []


def test_redirects_and_unanswered_dns_count_as_another_server_or_unchecked():
    web = FakeWeb({"https://autoconfig.example.org/": HttpAnswer(200, autoconfig("mail.example.org")),
                   "https://autodiscover.example.org/autodiscover/autodiscover.xml":
                       HttpAnswer(302, location="https://autodiscover.outlook.example/autodiscover/autodiscover.xml"),
                   "https://example.org/autodiscover/": HttpAnswer(200, pox(redirect_address="robin@contoso.example"))})
    found = PublishedConfig(EMAIL, {"mail.example.org"}, web, FakeDns(None)).check()
    assert found["other_hosts"] == ["autodiscover.outlook.example", "contoso.example"]
    assert "MX" in found["unchecked"] and "SRV _imaps._tcp" in found["unchecked"] and found["dns"] is None
    unchecked_only = PublishedConfig(EMAIL, {"mail.example.org"}, FakeWeb({}), FakeDns(None)).check()
    assert unchecked_only["guarded"] and unchecked_only["other_hosts"] == []


def test_an_mx_host_of_another_domain_adds_that_domains_autoconfig_and_ispdbs():
    web = FakeWeb({"https://autoconfig.provider.example/": HttpAnswer(200, autoconfig("imap.provider.example"))})
    found = PublishedConfig(EMAIL, {"mail.example.org"}, web, FakeDns({("example.org", "MX"): [
        "20 mx2.provider.example.", "10 mx1.provider.example."]})).check()
    assert found["other_hosts"] == ["imap.provider.example"]
    assert found["other_sources"] == ["autoconfig (MX domain provider.example)"]
    assert not any("provider.example" in url and "robin" in url for url, _ in web.requests)


class FakeAccountServer:
    email = EMAIL
    email_domain = "example.org"

    @staticmethod
    def mail_hostnames():
        return {"mail.example.org"}


class FakeAccount:
    server = FakeAccountServer()


def pipeline_with(tmp_path, monkeypatch, found: dict) -> Pipeline:
    checks = []

    class Checked:
        def __init__(self, email, hosts):
            checks.append((email, hosts))

        def check(self):
            return found

    monkeypatch.setattr("benchlib.stages.PublishedConfig", Checked)
    folder = ResultFolder.create(tmp_path, "linux")
    config = Config({"workdir": str(tmp_path / "work"), "display": DISPLAY,
                     "deviations": ["Thunderbird: start page switched off."]}, tmp_path)
    pipeline = Pipeline(config, lambda *_: None, folder)
    monkeypatch.setattr(pipeline, "account", lambda: FakeAccount())
    pipeline.checks = checks
    return pipeline


GUARDED = {"version": 1, "checked_utc": "2026-10-23T23:21:09+00:00", "domain": "example.org",
           "server_hosts": ["mail.example.org"], "mx": ["mail.example.org"], "dns": "dns.example",
           "sources": [{"source": "autoconfig", "url": "https://autoconfig.example.org/x?emailaddress={address}",
                        "status": 200, "hosts": ["mail.example.org"]},
                       {"source": "autoconfig (.well-known)", "url": "https://example.org/.well-known/x", "status": 200,
                        "hosts": ["mail.beonex.example"]},
                       {"source": "SRV _imap._tcp", "name": "_imap._tcp.example.org", "hosts": []}],
           "other_hosts": ["mail.beonex.example"], "other_sources": ["autoconfig (.well-known)"], "unchecked": [],
           "guarded": True}
UNGUARDED = {**GUARDED, "sources": GUARDED["sources"][:1], "other_hosts": [], "other_sources": [], "guarded": False}


def test_the_check_before_the_session_is_recorded_once_and_a_guarded_path_is_listed_with_the_deviations(
        tmp_path, monkeypatch):
    pipeline = pipeline_with(tmp_path, monkeypatch, GUARDED)
    assert pipeline.check_published_config() == GUARDED
    assert pipeline.check_published_config() == GUARDED and len(pipeline.checks) == 1
    manifest = pipeline.folder.manifest()
    assert manifest["server_discovery"] == GUARDED
    assert manifest["deviations"][0] == "Thunderbird: start page switched off."
    assert manifest["deviations"][1].startswith("Server check: before the session, autoconfig (.well-known) "
                                                "named mail.beonex.example for the address's domain, not only the "
                                                "account's server mail.example.org.")
    resumed = Pipeline(pipeline.config, lambda *_: None, ResultFolder.open(pipeline.folder.path))
    monkeypatch.setattr(resumed, "account", lambda: FakeAccount())
    assert resumed.check_published_config() == GUARDED and len(pipeline.checks) == 1
    assert len(resumed.notes) == 1
    executor = RunExecutor(pipeline.config, None, None, folder=pipeline.folder)
    assert executor.variables().values["server.guard"] == "on"


def test_only_the_accounts_server_published_turns_the_guard_off_without_a_deviation(tmp_path, monkeypatch):
    pipeline = pipeline_with(tmp_path, monkeypatch, UNGUARDED)
    pipeline.check_published_config()
    assert pipeline.folder.manifest()["deviations"] == ["Thunderbird: start page switched off."]
    assert RunExecutor(pipeline.config, None, None, folder=pipeline.folder).variables().values["server.guard"] == "off"
    unchecked = RunExecutor(pipeline.config, None, None, folder=ResultFolder.create(tmp_path / "x", "linux"))
    assert unchecked.variables().values["server.guard"] == "on"


def network_run(run_dir: Path, connections: list[tuple[str, int]]):
    run_dir.mkdir(parents=True)
    log = NetworkLog(run_dir / "network.jsonl")
    log.write("resolve", t=1.0, host="mail.example.org", addresses=["203.0.113.5", "2001:db8::5"])
    log.write("mail_server", t=1.0, addresses=["203.0.113.5", "2001:db8::5"], ports=[443, 465, 993],
              mail_only_ports=[25, 110, 143, 465, 587, 993, 995])
    for n, (remote, port) in enumerate(connections):
        log.write("open", t=2.0 + n, pid=7, process="thunderbird", local=f"10.0.0.2:{4000 + n}", remote=remote,
                  remote_port=port, state="ESTABLISHED")
    log.close()


def test_a_mail_connection_to_another_address_fails_the_run_and_stops_the_series(tmp_path):
    executor = RunExecutor(Config({"workdir": str(tmp_path / "work"), "display": DISPLAY}, tmp_path), None, None,
                           progress=lambda *_: None)
    fine = tmp_path / "fine"
    network_run(fine, [("203.0.113.5", 993), ("2001:db8::5", 465), ("198.51.100.7", 443), ("127.0.0.1", 993)])
    meta = {"status": "complete"}
    executor.check_mail_destinations(fine, meta)
    assert meta == {"status": "complete"}
    run_dir = tmp_path / "C2" / "T1" / "thunderbird" / "run-1"
    network_run(run_dir, [("203.0.113.5", 993), ("198.51.100.7", 465), ("198.51.100.7", 587)])
    meta = {"run": "run-1", "status": "complete"}
    executor.check_mail_destinations(run_dir, meta)
    assert meta["status"] == "failed" and meta["failure"] == "wrong-server"
    assert meta["wrong_server"] == {"connections": 2, "ports": [465, 587], "processes": ["thunderbird"]}
    assert "198.51.100.7" not in json.dumps(meta) and "must be changed" in (run_dir / "error.txt").read_text()
    (run_dir / "meta.json").write_text(json.dumps(meta))

    class Executor:
        server_log = None

        def __init__(self):
            self.executed = []

        def run_dir(self, comparison, task, app_id, run_id):
            return run_dir if app_id == "thunderbird" else tmp_path / "parula" / run_id

        def execute(self, comparison, task, app_id, run_id, warmup, order, attempt=1):
            self.executed.append((app_id, run_id))
            if app_id != "thunderbird":
                self.run_dir(comparison, task, app_id, run_id).mkdir(parents=True, exist_ok=True)
                self.run_dir(comparison, task, app_id, run_id).joinpath("meta.json").write_text(
                    json.dumps({"status": "complete"}))

    config = Config({"runs": {"measured": 2, "warmup": 0, "retries": 2},
                     "comparisons": {"C2": {"left": "parula-jmap", "right": "thunderbird", "tasks": ["T1"]}}}, tmp_path)
    executor = Executor()
    with pytest.raises(SeriesStop, match="WrongServer: 2 connection.*the test password may have gone to another "
                                         "server and must be changed"):
        Orchestrator(config, executor, lambda *_: None).run_comparison("C2", resume=False)
    assert executor.executed == [("parula-jmap", "run-1"), ("thunderbird", "run-1")]


def test_the_report_names_runs_with_mail_connections_elsewhere_and_the_published_configuration():
    wrong = {"run": "run-1", "order": 2, "status": "failed", "reason": "WrongServer: …",
             "wrong_server": {"connections": 2, "ports": [465, 587], "processes": ["thunderbird"]}}
    side = {"name": "Thunderbird", "version": "140", "protocol": "IMAP", "runs": [wrong], "warmups": [],
            "failed_attempts": [], "status": 1, "status_reason": "x", "actions": 9, "action_list": [],
            "median_run": None, "warmups_discarded": [], "median_s": None}
    left = {**side, "name": "Parula", "runs": [], "protocol": "JMAP"}
    results = {"generated": "now", "runs": {"measured": 1, "warmup": 0}, "server_mode": "account",
               "environment": {}, "settle": {}, "server_discovery": GUARDED,
               "comparisons": {"C2": {"os": "Linux", "tasks": {"T1": {"title": {"en": "Set up"}, "left": left,
                                                                       "right": side, "ratio": None}}}}}
    lines = ReportWriter(results, []).wrong_server_lines()
    assert lines[0] == "## Wrong server: the test password must be changed"
    assert lines[4].startswith("- T1 Thunderbird run-1: 2 connection(s) on mail ports (465, 587)")
    published = ReportWriter(results, []).published_config_lines()
    assert "- autoconfig (.well-known) (https://example.org/.well-known/x): mail.beonex.example (another server)" \
        in published
    assert "- SRV _imap._tcp (_imap._tcp.example.org): no record" in published
    assert any(line.startswith("Result: another server named by autoconfig (.well-known)") for line in published)
    unguarded = ReportWriter({**results, "server_discovery": UNGUARDED}, []).published_config_lines()
    assert any("every app took its own setup path" in line for line in unguarded)
