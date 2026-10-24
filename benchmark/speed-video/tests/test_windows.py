"""Unit tests of the Windows package with fakes (it can't run here): UI Automation lookups by English and German
names, page detection, the Outlook setup flows through the shared driver and flow context, the Inbox probes, the
network log, the run plan, the session's lifecycles and the cleanup after errors.
Run: python -m pytest tests/test_windows.py"""

import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchlib.account import AccountServer, AccountSession  # noqa: E402
from benchlib.config import Config  # noqa: E402
from benchlib.corpus import CorpusGenerator, CorpusSpec  # noqa: E402
from benchlib.driver import Calibration, EventLog, ScenarioDriver, TextVariables  # noqa: E402
from benchlib.flows import (FlowContext, FlowError, Flows, NewOutlookRemoval, NewOutlookSetupFlow,  # noqa: E402
                            OutlookClassicSetupFlow, ParulaSetupFlow, WrongServer)
from benchlib.method import ManifestTexts  # noqa: E402
from benchlib.probe import ParulaProbe, Probes  # noqa: E402
from benchlib.runner import Orchestrator, RunExecutor  # noqa: E402
from benchlib.settle import Rect  # noqa: E402
from benchlib.uia import ElementInfo, ElementQuery, UiaError, UiTree  # noqa: E402
from benchlib.winapps import (CredentialManager, OutlookClassicProfile, ParulaProfile, ParulaUpdates,  # noqa: E402
                              SessionState, WindowsSettings)
from benchlib.winnet import ConnectionTracker, ProcessEntry, ProcessTable, TcpRow, TcpTable, WindowsConnectionWatcher  # noqa: E402
from benchlib.winprobe import CountText, UiaAppMap, UiaProbe  # noqa: E402
from benchlib.winsession import DisplayPlan, NewOutlookLifecycle, WindowsConfig, WindowsSession  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ELEMENTS = ROOT / "windows" / "uia-elements.yaml"
EMAIL = "robin@example.org"


# ---------------------------------------------------------------------------------------------------------------
# Fakes

class Node:
    """One element of the fake UI Automation tree; `info.handle` points back to the node."""

    def __init__(self, control_type, name="", children=None, **fields):
        self.info = ElementInfo(name=name, control_type=control_type, **fields)
        self.info.handle = self
        self.children = list(children or [])


class FakeBackend:
    """A UI Automation backend over Node trees: the top-level windows are `windows` (changed by the fake app)."""

    def __init__(self):
        self.windows: list[Node] = []
        self.root_node = Node("Pane", "Desktop")
        self.calls = 0

    def root(self):
        return self.root_node.info

    def children(self, element):
        self.calls += 1
        node = element.handle
        return [w.info for w in self.windows] if node is self.root_node else [c.info for c in node.children]

    def descendants(self, element, control_types=None):
        self.calls += 1
        out = []

        def visit(node, depth):
            for child in node.children:
                child.info.depth = depth
                if not control_types or child.info.control_type in control_types:
                    out.append(child.info)
                visit(child, depth + 1)

        visit(element.handle, element.depth + 1)
        return out

    def refresh(self, element):
        node = element.handle
        if not any(node is n for n in self.all_nodes()):
            raise UiaError("element gone")
        return node.info

    def all_nodes(self):
        stack = list(self.windows)
        while stack:
            node = stack.pop()
            yield node
            stack.extend(node.children)

    def walk(self, element, max_depth, max_elements):
        out = []

        def visit(node, depth):
            node.info.depth = depth
            out.append(node.info)
            if depth < max_depth:
                for child in node.children:
                    visit(child, depth + 1)

        visit(element.handle, element.depth)
        return out[:max_elements]


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeProcessTable:
    def __init__(self, entries):
        self.entries = entries

    def snapshot(self):
        return list(self.entries)


def element(control_type, name="", x=10, y=10, width=100, height=24, **fields):
    return Node(control_type, name, rect=Rect(x, y, width, height), process_id=fields.pop("pid", 4242), **fields)


class FakeApp:
    """A scripted app: pages (lists of Nodes) and what each click, key or typed text does."""

    def __init__(self, backend: FakeBackend, pages: dict, start: str, pid: int = 4242):
        self.backend = backend
        self.pages = pages
        self.pid = pid
        self.typed: dict[str, str] = {}
        self.typing: list[tuple[str, str]] = []
        self.focus: str | None = None
        self.focus_node: Node | None = None
        self.history: list[str] = []
        self.page = None
        self.show(start)
        self.on_click = {}
        self.on_key = {}
        self.inbox_polls = 0

    def show(self, page: str):
        self.page = page
        built = self.pages[page]() if callable(self.pages[page]) else self.pages[page]
        self.backend.windows = [Node("Window", "App", built, rect=Rect(0, 0, 1280, 940), process_id=self.pid)]
        for node in self.backend.all_nodes():
            node.info.process_id = self.pid
            if node.info.focused:
                self.focus, self.focus_node = node.info.name, node
        self.history.append(page)

    def node_at(self, x, y):
        hits = [n for n in self.backend.all_nodes() if n.info.rect and n.info.control_type != "Window" and
                n.info.rect.x <= x < n.info.rect.x + n.info.rect.width and
                n.info.rect.y <= y < n.info.rect.y + n.info.rect.height]
        return hits[-1] if hits else None

    def click(self, x, y):
        node = self.node_at(x, y)
        if node is None:
            raise AssertionError(f"click at {x},{y} hits nothing on page {self.page}")
        for n in self.backend.all_nodes():
            n.info.focused = False
        node.info.focused = True
        self.focus, self.focus_node = node.info.name, node
        action = self.on_click.get((self.page, node.info.name))
        if action:
            action(node)

    def key(self, combo):
        action = self.on_key.get((self.page, combo))
        if action:
            action()

    def type(self, text):
        self.typed[self.focus or ""] = text
        self.typing.append((self.page, self.focus or ""))
        if self.focus_node is not None and self.focus_node.info.control_type == "Edit":
            self.focus_node.info.value = text


class FakeDesktop:
    def __init__(self, app: FakeApp):
        self.app = app
        self.moves = []

    def click(self, x, y, button=1, count=1, hover_s=0.15):
        self.app.click(x, y)

    def key(self, combo):
        self.app.key(combo)

    def type_text(self, text, delay_ms):
        self.app.type(text)

    def move(self, x, y):
        self.moves.append((x, y))


class FakeAppProcess:
    process = None

    def ensure_foreground(self):
        pass


class GateLive:
    """The live gate (`LiveMonitor.wait_settled`): the screen is quiet whenever the driver asks; with a completion
    check, the gate asks it until it confirms."""

    def __init__(self):
        self.calls = 0

    def wait_settled(self, since, quiet_s, timeout_s, label, expect_change=True, complete=None, **_):
        self.calls += 1
        now = EventLog.now()
        if complete is None:
            return "settled", {"live_end": now if expect_change else None, "live_quiet_s": quiet_s}
        for _ in range(50):
            if complete():
                return "settled", {"live_end": now, "live_quiet_s": quiet_s, "confirmed_at": EventLog.now(),
                                   "live_matched": True}
        return "timeout", {"live_end": now, "timeout_s": timeout_s}


FINAL = {"complete": "inbox_listed", "verify": True, "after_end": "fail", "first_visible": True}


def make_context(tmp_path, app: FakeApp, kind: str, expected: dict | None = None):
    """The shared driver and flow context with the real UI Automation probe over the fake app's tree."""
    clock = FakeClock()
    backend = app.backend
    app_map = UiaAppMap.load(ELEMENTS, kind)
    probe = UiaProbe(app_map, backend_factory=lambda: backend,
                     process_table=FakeProcessTable([ProcessEntry(app.pid, 1, app_map.process_names[0])]),
                     sleep=clock.sleep, clock=clock)
    probe.tree = UiTree(backend, lambda: {app.pid})
    values = {"account.email": EMAIL, "account.password": "s3cret-Pw",
              "server.jmap_url": "https://mail.example.org/.well-known/jmap",
              "server.imap_host": "mail.example.org", "server.imap_port": "993",
              "server.smtp_host": "mail.example.org", "server.smtp_port": "465"}
    variables = TextVariables(values, {"account.password"})
    probe.redact = variables.redact
    log = EventLog(tmp_path / "driver.jsonl")
    driver = ScenarioDriver(FakeDesktop(app), FakeAppProcess(), Calibration(tmp_path / "none.yaml", Rect(0, 0, 1280, 940)),
                            variables, log, park=(1500, 900), step_timeout_s=60, task_timeout_s=7200, probe=probe,
                            expected=expected or {"inbox_messages": 30000, "inbox_unread": 1500},
                            verify_path=tmp_path / "verify.json")
    driver.live = GateLive()
    return FlowContext(driver, probe, {}, FINAL), log


class MemoryLog:
    def __init__(self):
        self.lines = []

    def write(self, type, t=None, **fields):
        self.lines.append((type, fields))
        return t


def logged(log: EventLog, kind: str, **match) -> list[dict]:
    return [e for e in EventLog.read(log.path) if e["type"] == kind and all(e.get(k) == v for k, v in match.items())]


# ---------------------------------------------------------------------------------------------------------------
# Element lookup, languages, pages

def test_query_matches_english_and_german_names():
    query = ElementQuery("Button", names={"en": ["Next"], "de": ["Weiter"]})
    assert query.matches(ElementInfo(name="Next", control_type="Button", rect=Rect(0, 0, 10, 10))) == "en"
    assert query.matches(ElementInfo(name=" Weiter ", control_type="Button", rect=Rect(0, 0, 10, 10))) == "de"
    assert query.matches(ElementInfo(name="weiter", control_type="Button", rect=Rect(0, 0, 10, 10))) == "de"
    assert query.matches(ElementInfo(name="Weiter", control_type="Text", rect=Rect(0, 0, 10, 10))) is None
    assert query.matches(ElementInfo(name="Next step", control_type="Button", rect=Rect(0, 0, 10, 10))) is None
    hidden = ElementInfo(name="Next", control_type="Button", rect=Rect(0, 0, 10, 10), offscreen=True)
    assert query.matches(hidden) is None
    password = ElementQuery("Edit", password=True)
    assert password.matches(ElementInfo(control_type="Edit", is_password=True, rect=Rect(0, 0, 9, 9))) == "any"
    assert password.matches(ElementInfo(control_type="Edit", rect=Rect(0, 0, 9, 9))) is None
    with pytest.raises(UiaError):
        ElementQuery("Buton")


def test_tree_detects_the_ui_language_and_prefers_it(tmp_path):
    backend = FakeBackend()
    backend.windows = [Node("Window", "Outlook", [element("Button", "Weiter"), element("Button", "Next", y=50)],
                            process_id=7, rect=Rect(0, 0, 500, 500)),
                       Node("Window", "Other app", [element("Button", "Next", pid=8)], process_id=8,
                            rect=Rect(0, 0, 500, 500))]
    tree = UiTree(backend, lambda: {7})
    query = ElementQuery("Button", names={"en": ["Next"], "de": ["Weiter"]})
    assert tree.find(query).name == "Weiter"
    assert tree.language == "de"
    assert [e.name for e in tree.find_all(query)] == ["Weiter", "Next"]
    assert len(tree.windows()) == 1
    data = tree.dump(tmp_path / "dump.json", redact=lambda t: t.replace("Weiter", "<w>"))
    assert len(data["windows"]) == 1
    text = (tmp_path / "dump.txt").read_text()
    assert 'Button "<w>"' in text and 'Button "Next"' in text and "Other app" not in text


def test_tree_wait_times_out_with_the_query_in_the_message():
    backend = FakeBackend()
    tree = UiTree(backend, lambda: {1})
    with pytest.raises(UiaError, match="Button name=en:Next"):
        tree.wait(ElementQuery("Button", names={"en": ["Next"]}), timeout_s=0.05, poll_s=0.01)


def test_element_map_is_consistent_for_every_app():
    data = yaml.safe_load(ELEMENTS.read_text(encoding="utf-8"))
    assert set(data) == {"outlook-classic", "outlook-new"}
    for kind in data:
        app_map = UiaAppMap.load(ELEMENTS, kind)
        assert app_map.process_names
        for name, source in app_map.sources.items():
            assert source in ("docs", "assumed"), (kind, name)
            query = app_map.query(name)
            if query.names:
                assert set(query.names) == {"en", "de"}, (kind, name)
    flows_use = {"outlook-classic": ["field.email", "button.connect", "tile.imap", "button.next", "field.password",
                                     "checkbox.mobile", "button.done"],
                 "outlook-new": ["field.email", "button.continue", "option.imap", "field.password", "button.done",
                                 "button.settings", "nav.accounts", "nav.email_accounts", "button.manage",
                                 "button.remove", "option.remove_all_devices", "button.confirm"]}
    for kind, names in flows_use.items():
        app_map = UiaAppMap.load(ELEMENTS, kind)
        for name in names:
            app_map.query(name)
    assert UiaAppMap.load(ELEMENTS, "outlook-new").near == {"button.manage": "account"}


def test_probe_factory_loads_the_apps_section_of_the_map(tmp_path):
    config = Config({"apps": {}}, ROOT)
    probe = Probes.create({"type": "uia", "app": "outlook-new", "map": "windows/uia-elements.yaml"}, config)
    assert isinstance(probe, UiaProbe) and probe.map.kind == "outlook-new" and not probe.shows_moving_content


def test_count_text_parses_both_languages():
    assert CountText.parse("30,000") == 30000
    assert CountText.parse("30.000") == 30000
    assert CountText.parse("30\u202f000") == 30000
    assert CountText.parse(" 1 500 ") == 1500
    assert CountText.parse("about 30k") is None
    assert CountText.parse(None) is None


# ---------------------------------------------------------------------------------------------------------------
# Outlook (classic), German UI

def outlook_classic_app(items, found_host: str | None = "mail.example.org", back_link: bool = True):
    """Outlook (classic), German UI. `found_host`: the server its IMAP settings page shows after the IMAP tile; None:
    it asks for the password right away (without showing the server), and shows the settings page only in its
    manual setup, prefilled with the address's domain."""
    backend = FakeBackend()
    state = {"manual_shown": False, "manual": False}

    def account_email():
        nodes = [element("Edit", "E-Mail-Adresse", focused=True, value=state.get("email")),
                 element("Hyperlink", "Erweiterte Optionen", y=60), element("Button", "Verbinden", y=120)]
        if state["manual_shown"]:
            nodes.append(element("CheckBox", "Ich möchte mein Konto manuell einrichten", y=90,
                                 toggle_state=1 if state["manual"] else 0))
        return nodes

    def imap_settings():
        host = found_host or "imap.example.org"
        return [element("Text", "IMAP-Kontoeinstellungen"),
                element("Edit", "Server", y=60, value=host), element("Edit", "Port", x=200, y=60, value="993"),
                element("Edit", "Server", y=90, value=host.replace("imap.", "smtp.")),
                element("Edit", "Port", x=200, y=90, value="587"), element("Button", "Weiter", y=160)]

    def password():
        nodes = [element("Edit", "Kennwort", is_password=True, focused=True), element("Button", "Verbinden", y=120)]
        if back_link:
            nodes.append(element("Hyperlink", "Nicht Sie?", y=30))
        return nodes

    pages = {
        "account-email": account_email,
        "advanced-setup": [element("Text", "Erweitertes Setup"), element("Button", "IMAP", y=100),
                           element("Button", "POP", y=140)],
        "imap-settings": imap_settings,
        "password": password,
        "done": [element("Text", "Konto erfolgreich hinzugefügt"),
                 element("CheckBox", "Outlook Mobile auch auf meinem Telefon einrichten", y=80, toggle_state=1),
                 element("Button", "Fertig", y=120)],
        "mail": lambda: [element("Text", f"Elemente: {items['n']:,}".replace(",", "."), y=920),
                         element("Text", "Alle Ordner sind auf dem neuesten Stand.", x=300, y=920)],
    }
    app = FakeApp(backend, pages, "account-email")

    def imap_tile(node):
        app.show("imap-settings" if found_host or state["manual"] else "password")

    def toggle_manual(node):
        state["manual"] = not state["manual"]
        app.show("account-email")

    def back(node):
        state["email"] = EMAIL
        app.show("account-email")

    def show_manual(node):
        state["manual_shown"] = True
        app.show("account-email")

    app.on_click = {("account-email", "Verbinden"): lambda n: app.show("advanced-setup"),
                    ("account-email", "Erweiterte Optionen"): show_manual,
                    ("account-email", "Ich möchte mein Konto manuell einrichten"): toggle_manual,
                    ("advanced-setup", "IMAP"): imap_tile,
                    ("imap-settings", "Weiter"): lambda n: app.show("password"),
                    ("password", "Verbinden"): lambda n: app.show("done"),
                    ("password", "Nicht Sie?"): back,
                    ("done", "Outlook Mobile auch auf meinem Telefon einrichten"):
                        lambda n: setattr(n.info, "toggle_state", 0),
                    ("done", "Fertig"): lambda n: app.show("mail")}
    return app


def classic_growing_inbox(ctx, app, items):
    original = ctx.probe.inbox_listed

    def growing(expected):
        items["n"] = min(30000, items["n"] + 13000)
        app.show("mail")
        return original(expected)

    ctx.probe.inbox_listed = growing


def test_outlook_classic_flow_german_unchecks_outlook_mobile_and_waits_for_the_item_count(tmp_path):
    items = {"n": 4000}
    app = outlook_classic_app(items)
    ctx, log = make_context(tmp_path, app, "outlook-classic")
    classic_growing_inbox(ctx, app, items)
    OutlookClassicSetupFlow(ctx).run()
    assert app.typed["E-Mail-Adresse"] == EMAIL and app.typed["Kennwort"] == "s3cret-Pw"
    starts = logged(log, "step_start")
    assert [e["step"] for e in starts] == ["connect", "choose-imap", "imap-settings", "login", "open-inbox"]
    assert starts[0]["checks"]["complete"]["pages"] == ["advanced-setup", "done", "error", "imap-settings",
                                                        "password"]
    assert starts[-1]["checks"]["complete"] == "inbox_listed" and starts[-1]["checks"]["after_end"] == "fail"
    assert "advanced-setup" in ctx.path and any("Outlook Mobile" in note for note in ctx.path)
    assert "Outlook's IMAP settings show no other server than the account's" in ctx.path
    assert ctx.probe.language == "de"
    actions = RunExecutor.user_actions(log.path, ctx.variables)
    assert actions["user_actions"] == 8 and actions["prepare_actions"] == []
    final = logged(log, "probe", step="open-inbox")
    assert [p["complete"] for p in final] == [False, True] and final[-1]["listed"] == 30000
    assert final[-1]["idle"] is True
    assert [e["step"] for e in logged(log, "step_live_settled")] == [e["step"] for e in starts]
    verify = json.loads((tmp_path / "verify.json").read_text())
    assert verify["step"] == "open-inbox" and verify["listed"] == 30000
    assert verify["count_rect"] == {"x": 10, "y": 920, "w": 100, "h": 24}
    assert all(e.get("arg") != "s3cret-Pw" for e in EventLog.read(log.path))


def test_outlook_classic_corrects_another_server_on_its_imap_settings_page_before_the_password(tmp_path):
    items = {"n": 30000}
    app = outlook_classic_app(items, found_host="imap.beonex.example")
    ctx, log = make_context(tmp_path, app, "outlook-classic")
    servers = []
    app.on_click[("imap-settings", "Weiter")] = lambda n: (
        servers.append([e.value for e in ctx.probe.snapshot() if e.control_type == "Edit"]), app.show("password"))
    OutlookClassicSetupFlow(ctx).run()
    assert servers == [["mail.example.org", "993", "mail.example.org", "465"]]
    assert any("another server (imap.beonex.example, smtp.beonex.example)" in note for note in ctx.path)
    assert app.typing.index(("password", "Kennwort")) > app.typing.index(("imap-settings", "Server"))
    assert [e["step"] for e in logged(log, "step_start")] == ["connect", "choose-imap", "imap-settings", "login",
                                                              "open-inbox"]
    assert RunExecutor.user_actions(log.path, ctx.variables)["user_actions"] == 8 + 3 * 3


def test_outlook_classic_that_asks_for_the_password_without_a_server_goes_to_its_manual_setup(tmp_path):
    items = {"n": 30000}
    app = outlook_classic_app(items, found_host=None)
    ctx, log = make_context(tmp_path, app, "outlook-classic")
    OutlookClassicSetupFlow(ctx).run()
    assert app.history[:4] == ["account-email", "advanced-setup", "password", "account-email"]
    assert [page for page, field in app.typing if field == "Kennwort"] == ["password"]
    assert app.typing.index(("password", "Kennwort")) > app.typing.index(("imap-settings", "Server"))
    assert [e["step"] for e in logged(log, "step_start")] == ["connect", "choose-imap", "change-setup",
                                                              "connect-manually", "choose-imap-2", "imap-settings",
                                                              "login", "open-inbox"]
    assert any("back to the address" in note for note in ctx.path)
    clicked = [e["arg"] for e in logged(log, "input", phase="step") if e["action"] == "click"]
    assert clicked[2:6] == ["link.back", "link.advanced", "checkbox.manual", "button.connect"]


def test_outlook_classic_without_a_way_to_its_manual_setup_stops_before_the_password(tmp_path):
    app = outlook_classic_app({"n": 30000}, found_host=None, back_link=False)
    ctx, log = make_context(tmp_path, app, "outlook-classic")
    with pytest.raises(WrongServer, match="stopped before the password, which goes only to mail.example.org"):
        OutlookClassicSetupFlow(ctx).run()
    assert "Kennwort" not in app.typed and app.page == "password"
    assert isinstance(WrongServer("x"), FlowError)


def test_outlook_classic_settings_without_readable_server_fields_stop_before_the_password(tmp_path):
    app = outlook_classic_app({"n": 30000}, found_host="imap.beonex.example")
    app.pages["imap-settings"] = [element("Text", "IMAP-Kontoeinstellungen"), element("Button", "Weiter", y=160)]
    ctx, _ = make_context(tmp_path, app, "outlook-classic")
    with pytest.raises(WrongServer, match="shows no field 'field.incoming_server'"):
        OutlookClassicSetupFlow(ctx).run()
    assert "Kennwort" not in app.typed


def test_outlook_classic_unguarded_enters_the_password_on_its_own_path_without_a_detour(tmp_path):
    app = outlook_classic_app({"n": 30000}, found_host=None)
    ctx, log = make_context(tmp_path, app, "outlook-classic")
    ctx.variables.values["server.guard"] = "off"
    OutlookClassicSetupFlow(ctx).run()
    assert app.history[:3] == ["account-email", "advanced-setup", "password"]
    assert [e["step"] for e in logged(log, "step_start")] == ["connect", "choose-imap", "login", "open-inbox"]
    assert not logged(log, "input", phase="prepare")
    clicked = [e["arg"] for e in logged(log, "input", phase="step") if e["action"] == "click"]
    assert "link.back" not in clicked and "checkbox.manual" not in clicked


def test_outlook_classic_unguarded_checks_its_settings_page_without_actions_and_stops_at_another_server(tmp_path):
    own = outlook_classic_app({"n": 30000})
    own_ctx, own_log = make_context(tmp_path, own, "outlook-classic")
    own_ctx.variables.values["server.guard"] = "off"
    OutlookClassicSetupFlow(own_ctx).run()
    assert RunExecutor.user_actions(own_log.path, own_ctx.variables)["user_actions"] == 8
    (tmp_path / "other").mkdir()
    app = outlook_classic_app({"n": 30000}, found_host="imap.beonex.example")
    ctx, log = make_context(tmp_path / "other", app, "outlook-classic")
    ctx.variables.values["server.guard"] = "off"
    with pytest.raises(WrongServer, match="found imap.beonex.example, smtp.beonex.example, although"):
        OutlookClassicSetupFlow(ctx).run()
    assert "Kennwort" not in app.typed and ("imap-settings", "Server") not in app.typing
    assert [e["step"] for e in logged(log, "step_start")] == ["connect", "choose-imap"]


def test_an_unknown_page_stops_the_flow(tmp_path):
    backend = FakeBackend()
    app = FakeApp(backend, {"odd": [element("Text", "Something unexpected")]}, "odd")
    ctx, _ = make_context(tmp_path, app, "outlook-classic")
    with pytest.raises(FlowError, match="shows 'unknown'"):
        OutlookClassicSetupFlow(ctx).run()
    ctx.probe.dump(tmp_path / "dump.json")
    assert "Something unexpected" in (tmp_path / "dump.txt").read_text()


def test_a_privacy_notice_in_between_is_closed_without_counting(tmp_path):
    items = {"n": 30000}
    app = outlook_classic_app(items)
    app.pages["privacy"] = [element("Text", "Microsoft respects your privacy"), element("Button", "Next", y=200)]
    app.show("privacy")
    app.on_click[("privacy", "Next")] = lambda n: app.show("account-email")
    ctx, log = make_context(tmp_path, app, "outlook-classic")
    OutlookClassicSetupFlow(ctx).run()
    assert any("privacy.next" in note for note in ctx.path)
    prepared = [e for e in logged(log, "input") if e["phase"] == "prepare"]
    assert [e["arg"] for e in prepared] == ["privacy.next"]
    assert RunExecutor.user_actions(log.path, ctx.variables)["user_actions"] == 8


# ---------------------------------------------------------------------------------------------------------------
# New Outlook, English UI: setup, the cloud-sync notice, the probes, the removal from all devices

def imap_form(state):
    """New Outlook's IMAP form: the servers it found (`state["found_host"]`), shown at once or behind "Show more"
    (`state["hidden"]`); `state["no_servers"]`: a form without server fields."""
    nodes = [element("Edit", "Email address"), element("Edit", "IMAP password", y=60, is_password=True),
             element("Button", "Continue", y=400)]
    if state.get("no_servers"):
        return nodes
    if state.get("hidden"):
        return nodes + [element("Button", "Show more", y=90)]
    host = state.get("found_host", "mail.example.org")
    return nodes + [element("Edit", "IMAP incoming server", y=150, value=host),
                    element("Edit", "Port", x=200, y=150, value="993"),
                    element("Edit", "SMTP outgoing server", y=200, value=host),
                    element("Edit", "Port", x=200, y=200, value="587")]


def new_outlook_pages(state):
    def mail():
        rows = [element("ListItem", f"Row {i}", y=100 + 30 * i, size_of_set=state["size"]) for i in range(3)]
        if state.get("oldest_visible"):
            rows.append(element("ListItem", "From Robin, Oldest subject in the corpus, 2016", y=300))
        return [element("TreeItem", f"Inbox {state['unread']} unread", y=60), element("Button", "Settings", x=1200, y=10),
                element("ListItem", "From Robin, Newest subject in the corpus, today", y=70)] + rows

    return {
        "add-account": [element("Edit", "Email address", focused=True), element("Button", "Continue", y=120)],
        "choose-provider": [element("Text", "Choose your provider"), element("Button", "IMAP", y=100)],
        "imap-form": lambda: imap_form(state),
        "cloud-sync": [element("Text", "Sync your email account with the Microsoft Cloud so you can use the new "
                                       "Outlook features"), element("Button", "Continue", y=120)],
        "success": [element("Text", "Success!"), element("Button", "Done", y=120)],
        "mail": mail,
        "settings": [element("TabItem", "Accounts", y=100), element("Button", "Close", x=1200, y=10)],
        "accounts": [element("ListItem", "Your accounts", y=100)],
        "email-accounts": [element("Text", EMAIL, y=200), element("Button", "Manage", x=600, y=200),
                           element("Text", "ben@example.net", y=300), element("Button", "Manage", x=600, y=300)],
        "manage": [element("Button", "Remove", y=200)],
        "remove": [element("RadioButton", "Remove from this device", y=150),
                   element("RadioButton", "Remove from all devices", y=200), element("Button", "OK", y=260)],
        "gone": [element("Edit", "Email address", focused=True), element("Button", "Continue", y=120)],
    }


def new_outlook_app(state):
    backend = FakeBackend()
    app = FakeApp(backend, new_outlook_pages(state), "add-account")
    manage_clicked = []
    app.on_click = {("add-account", "Continue"): lambda n: app.show("choose-provider"),
                    ("choose-provider", "IMAP"): lambda n: app.show("imap-form"),
                    ("imap-form", "Continue"): lambda n: app.show("cloud-sync"),
                    ("cloud-sync", "Continue"): lambda n: app.show("success"),
                    ("success", "Done"): lambda n: app.show("mail"),
                    ("mail", "Settings"): lambda n: app.show("settings"),
                    ("settings", "Accounts"): lambda n: app.show("accounts"),
                    ("accounts", "Your accounts"): lambda n: app.show("email-accounts"),
                    ("email-accounts", "Manage"): lambda n: (manage_clicked.append(n.info.rect.y), app.show("manage")),
                    ("manage", "Remove"): lambda n: app.show("remove"),
                    ("remove", "OK"): lambda n: app.show("gone")}

    def press_end():
        state["oldest_visible"] = True
        app.show("mail")

    app.on_key = {("mail", "End"): press_end}
    return app, manage_clicked


NEW_OUTLOOK_EXPECTED = {"inbox_messages": 30000, "inbox_unread": 1500,
                        "inbox_oldest_subject": "Oldest subject in the corpus",
                        "inbox_newest_subject": "Newest subject in the corpus"}


def growing_inbox(ctx, app, state):
    original = ctx.probe.inbox_listed

    def growing(expected):
        state["size"] = min(30000, state["size"] * 4)
        state["unread"] = min(1500, state["unread"] * 4)
        if app.page == "mail":
            app.show("mail")
        return original(expected)

    ctx.probe.inbox_listed = growing


def test_new_outlook_flow_verify_and_removal_from_all_devices(tmp_path):
    state = {"size": 500, "unread": 100}
    app, manage_clicked = new_outlook_app(state)
    ctx, log = make_context(tmp_path, app, "outlook-new", NEW_OUTLOOK_EXPECTED)
    growing_inbox(ctx, app, state)
    NewOutlookSetupFlow(ctx).run()
    assert [e["step"] for e in logged(log, "step_start")] == ["continue", "choose-imap", "connect", "cloud-sync",
                                                              "open-inbox"]
    assert ctx.path[:5] == ["choose-provider", "imap-form",
                            "new Outlook's IMAP form shows no other server than the account's", "cloud-sync", "success"]
    final = logged(log, "probe", step="open-inbox")
    assert final[-1]["complete"] and final[-1]["listed"] == 30000 and final[-1]["listed_from"] == "size_of_set"
    verify = json.loads((tmp_path / "verify.json").read_text())
    assert verify["inbox_complete"] and verify["oldest_visible"] and verify["newest_visible"]
    assert verify["step"] == "open-inbox" and verify["basis"] == "count"
    kinds = [e["type"] for e in EventLog.read(log.path)]
    assert kinds.index("verify_start") < kinds.index("verify_end")
    assert [e["action"] for e in logged(log, "input") if e["phase"] == "verify"] == ["click", "key"]
    counted = RunExecutor.user_actions(log.path, ctx.variables)["user_actions"]

    NewOutlookRemoval(FlowContext(ctx.driver, ctx.probe, {}, {}), EMAIL).run()
    assert manage_clicked == [200]
    assert app.history[-1] == "gone"
    assert RunExecutor.user_actions(log.path, ctx.variables)["user_actions"] == counted
    assert len([e for e in logged(log, "input") if e["phase"] == "finish"]) == 7
    assert logged(log, "account_removed")[0]["email_domain"] == "example.org"


def test_new_outlook_reads_the_servers_behind_show_more_and_corrects_another_server_before_the_password(tmp_path):
    state = {"size": 30000, "unread": 1500, "hidden": True, "found_host": "mail.beonex.example"}
    app, _ = new_outlook_app(state)

    def show_more(node):
        state["hidden"] = False
        app.show("imap-form")

    app.on_click[("imap-form", "Show more")] = show_more
    sent = []
    app.on_click[("imap-form", "Continue")] = lambda n: (
        sent.append([e.value for e in ctx.probe.snapshot() if e.control_type == "Edit" and not e.is_password]),
        app.show("cloud-sync"))
    ctx, log = make_context(tmp_path, app, "outlook-new", NEW_OUTLOOK_EXPECTED)
    NewOutlookSetupFlow(ctx).run()
    assert sent == [[None, "mail.example.org", "993", "mail.example.org", "465"]]
    assert app.typing.index(("imap-form", "IMAP password")) > app.typing.index(("imap-form", "SMTP outgoing server"))
    assert any("not counted" in note for note in ctx.path)
    assert any("another server (mail.beonex.example, mail.beonex.example)" in note for note in ctx.path)
    actions = RunExecutor.user_actions(log.path, ctx.variables)
    assert [e["arg"] for e in logged(log, "input") if e["phase"] == "prepare"] == ["button.show_more"]
    assert [e["step"] for e in logged(log, "step_start")] == ["continue", "choose-imap", "connect", "cloud-sync",
                                                              "open-inbox"]
    (tmp_path / "plain").mkdir()
    plain = make_context(tmp_path / "plain", new_outlook_app({"size": 30000, "unread": 1500})[0], "outlook-new",
                         NEW_OUTLOOK_EXPECTED)
    NewOutlookSetupFlow(plain[0]).run()
    assert actions["user_actions"] == RunExecutor.user_actions(plain[1].path, plain[0].variables)["user_actions"] + 3 * 3


def test_new_outlook_unguarded_doesnt_open_show_more_and_checks_only_the_servers_its_form_shows(tmp_path):
    hidden = {"size": 30000, "unread": 1500, "hidden": True, "found_host": "mail.beonex.example"}
    app, _ = new_outlook_app(hidden)
    ctx, log = make_context(tmp_path, app, "outlook-new", NEW_OUTLOOK_EXPECTED)
    ctx.variables.values["server.guard"] = "off"
    NewOutlookSetupFlow(ctx).run()
    assert not logged(log, "input", phase="prepare") and "IMAP password" in app.typed
    (tmp_path / "plain").mkdir()
    plain = make_context(tmp_path / "plain", new_outlook_app({"size": 30000, "unread": 1500})[0], "outlook-new",
                         NEW_OUTLOOK_EXPECTED)
    NewOutlookSetupFlow(plain[0]).run()
    assert RunExecutor.user_actions(log.path, ctx.variables)["user_actions"] == \
        RunExecutor.user_actions(plain[1].path, plain[0].variables)["user_actions"]
    (tmp_path / "shown").mkdir()
    shown = {"size": 30000, "unread": 1500, "found_host": "mail.beonex.example"}
    app, _ = new_outlook_app(shown)
    ctx, _ = make_context(tmp_path / "shown", app, "outlook-new", NEW_OUTLOOK_EXPECTED)
    ctx.variables.values["server.guard"] = "off"
    with pytest.raises(WrongServer, match="New Outlook found mail.beonex.example"):
        NewOutlookSetupFlow(ctx).run()
    assert "IMAP password" not in app.typed and app.page == "imap-form"


def test_new_outlook_without_server_fields_stops_before_the_password(tmp_path):
    state = {"size": 1, "unread": 1, "no_servers": True}
    app, _ = new_outlook_app(state)
    ctx, _ = make_context(tmp_path, app, "outlook-new", NEW_OUTLOOK_EXPECTED)
    with pytest.raises(WrongServer, match="New Outlook shows no field 'field.imap_server'"):
        NewOutlookSetupFlow(ctx).run()
    assert "IMAP password" not in app.typed and app.page == "imap-form"


def test_parula_on_windows_takes_the_same_flow_and_probe_as_on_linux_so_its_found_server_is_checked(tmp_path):
    raw = yaml.safe_load((ROOT / "windows" / "config.windows.yaml").read_text(encoding="utf-8"))
    scenario = yaml.safe_load((ROOT / "scenarios" / "T1.yaml").read_text(encoding="utf-8"))
    assert raw["apps"]["parula-jmap"]["probe"]["type"] == "cdp"
    assert isinstance(Probes.create(raw["apps"]["parula-jmap"]["probe"], Config({"apps": {}}, ROOT)), ParulaProbe)
    assert scenario["apps"]["parula-jmap"]["flow"]["name"] == "parula-setup"
    assert Flows.known["parula-setup"] is ParulaSetupFlow
    assert "parula-jmap" in raw["sessions"]["windows"]["apps"]


def test_new_outlook_that_opens_its_inbox_right_after_the_cloud_notice_measures_the_listing_in_that_step(tmp_path):
    state = {"size": 500, "unread": 100}
    app, _ = new_outlook_app(state)
    app.on_click[("cloud-sync", "Continue")] = lambda n: app.show("mail")
    ctx, log = make_context(tmp_path, app, "outlook-new", NEW_OUTLOOK_EXPECTED)
    growing_inbox(ctx, app, state)
    NewOutlookSetupFlow(ctx).run()
    assert [e["step"] for e in logged(log, "step_start")] == ["continue", "choose-imap", "connect", "cloud-sync"]
    assert [e["step"] for e in logged(log, "step_final")] == ["cloud-sync"]
    probes = logged(log, "probe", step="cloud-sync")
    assert probes[0]["became_final"] and probes[-1]["complete"] and probes[-1]["listed"] == 30000
    assert json.loads((tmp_path / "verify.json").read_text())["step"] == "cloud-sync"
    from benchlib.analyze import RunAnalyzer
    steps = RunAnalyzer.flow_steps(EventLog.read(log.path))
    assert steps[-1].complete == "inbox_listed" and steps[-1].after_end == "fail" and steps[0].complete != "inbox_listed"


def test_new_outlook_with_an_existing_account_stops_before_typing(tmp_path):
    backend = FakeBackend()
    app = FakeApp(backend, new_outlook_pages({"size": 1, "unread": 1}), "mail")
    ctx, _ = make_context(tmp_path, app, "outlook-new")
    with pytest.raises(FlowError, match="already has an account"):
        NewOutlookSetupFlow(ctx).run()
    assert app.typed == {}


def test_new_outlook_keeps_the_account_until_the_listing_is_complete_for_a_while_then_removes_it(
        windows_env, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr("benchlib.winsession.time", type("Time", (), {"monotonic": clock, "sleep": clock.sleep,
                                                                      "time": time.time}))
    session = make_session(windows_env, FakeCommands())
    lifecycle = session.lifecycles["outlook-new"]
    listed = iter([False, True, False, True, True, True, True])

    class Probe:
        def inbox_listed(self, expected):
            return {"complete": next(listed, True)}

    removed = []
    monkeypatch.setattr(NewOutlookLifecycle, "remove", lambda self, driver, probe: removed.append(True))
    driver = type("Driver", (), {"expected": {}, "log": MemoryLog()})()
    result = lifecycle.finish(driver, Probe())
    assert removed == [True] and result["removed"] and 180 <= result["kept_s"] <= 260
    assert driver.log.lines[0][0] == "cloud_wait"


def test_inbox_probe_reads_the_unread_count_when_no_set_size_exists(tmp_path):
    backend = FakeBackend()
    app = FakeApp(backend, {"mail": [element("TreeItem", "Inbox 1,500 unread")]}, "mail")
    ctx, _ = make_context(tmp_path, app, "outlook-new")
    listed = ctx.probe.inbox_listed({"inbox_messages": 30000, "inbox_unread": 1500})
    assert listed["listed"] is None and listed["unread"] == 1500 and listed["complete"]


# ---------------------------------------------------------------------------------------------------------------
# Network log

def ipv4_table(rows):
    data = struct.pack("<I", len(rows))
    for state, local, lport, remote, rport, pid in rows:
        data += struct.pack("<I4sI4sII", state, socket.inet_aton(local), socket.htons(lport), socket.inet_aton(remote),
                            socket.htons(rport), pid)
    return data


def ipv6_table(rows):
    data = struct.pack("<I", len(rows))
    for state, local, lport, remote, rport, pid in rows:
        data += struct.pack("<16sII16sIIII", socket.inet_pton(socket.AF_INET6, local), 0, socket.htons(lport),
                            socket.inet_pton(socket.AF_INET6, remote), 0, socket.htons(rport), state, pid)
    return data


def test_tcp_tables_parse_ipv4_and_ipv6_rows():
    rows = TcpTable.parse_ipv4(ipv4_table([(5, "192.168.1.20", 50123, "203.0.113.5", 993, 4242),
                                           (2, "0.0.0.0", 135, "0.0.0.0", 0, 900)]))
    assert rows[0] == TcpRow("192.168.1.20", 50123, "203.0.113.5", 993, "ESTABLISHED", 4242)
    assert rows[1].state == "LISTEN"
    six = TcpTable.parse_ipv6(ipv6_table([(3, "2001:db8::20", 50200, "2603:1026:c03::12", 443, 77),
                                          (5, "::ffff:192.168.1.20", 50201, "::ffff:203.0.113.5", 993, 77)]))
    assert six[0] == TcpRow("2001:db8::20", 50200, "2603:1026:c03::12", 443, "SYN_SENT", 77)
    assert six[1].remote == "203.0.113.5" and six[1].key == ("192.168.1.20:50201", "203.0.113.5", 993)
    assert TcpTable.parse_ipv4(b"") == []


def test_process_tree_follows_children_and_named_processes():
    entries = [ProcessEntry(10, 1, "explorer.exe"), ProcessEntry(20, 10, "olk.exe"),
               ProcessEntry(21, 20, "msedgewebview2.exe"), ProcessEntry(22, 21, "msedgewebview2.exe"),
               ProcessEntry(30, 1, "msedgewebview2.exe"), ProcessEntry(40, 5, "olk.exe")]
    assert ProcessTable.tree(entries, set(), {"olk.exe"}) == {20: "olk.exe", 21: "msedgewebview2.exe",
                                                              22: "msedgewebview2.exe", 40: "olk.exe"}
    assert set(ProcessTable.tree(entries, {10}, set())) == {10, 20, 21, 22}


def test_connection_tracker_reports_open_state_close_and_outside_connections():
    tracker = ConnectionTracker({"203.0.113.5"})
    tree = {4242: "parula.exe"}
    a = TcpRow("10.0.0.2", 50000, "203.0.113.5", 993, "SYN_SENT", 4242)
    events = tracker.update([a], tree)
    assert [e["type"] for e in events] == ["open"] and events[0]["process"] == "parula.exe"
    events = tracker.update([TcpRow("10.0.0.2", 50000, "203.0.113.5", 993, "ESTABLISHED", 4242)], tree)
    assert [(e["type"], e["state"]) for e in events] == [("state", "ESTABLISHED")]
    time_wait = TcpRow("10.0.0.2", 50000, "203.0.113.5", 993, "TIME_WAIT", 0)
    foreign = TcpRow("10.0.0.2", 51000, "203.0.113.5", 993, "ESTABLISHED", 999)
    elsewhere = TcpRow("10.0.0.2", 52000, "198.51.100.7", 443, "ESTABLISHED", 999)
    events = tracker.update([time_wait, foreign, elsewhere], tree)
    assert sorted(e["type"] for e in events) == ["close", "open_outside_tree"]
    assert next(e for e in events if e["type"] == "open_outside_tree")["pid"] == 999
    assert tracker.update([time_wait, foreign], tree) == []


class ListLog:
    def __init__(self):
        self.lines = []

    def header(self, os_name, app_id, source, poll_hz, root_pids):
        self.lines.append({"type": "header", "version": 1, "os": os_name, "app": app_id, "source": source,
                           "poll_hz": poll_hz, "root_pids": root_pids, "utc_offset": time.time() - time.perf_counter()})

    def write(self, type, **fields):
        self.lines.append({"type": type, **fields})


def test_watcher_writes_the_shared_network_log_format():
    class Tcp:
        def __init__(self):
            self.polls = [[TcpRow("10.0.0.2", 50000, "52.97.146.1", 443, "ESTABLISHED", 21)],
                          [TcpRow("10.0.0.2", 50000, "52.97.146.1", 443, "ESTABLISHED", 21),
                           TcpRow("10.0.0.2", 50001, "52.97.146.2", 443, "ESTABLISHED", 22)], []]

        def rows(self):
            return self.polls.pop(0) if self.polls else []

    procs = FakeProcessTable([ProcessEntry(20, 1, "olk.exe"), ProcessEntry(21, 20, "msedgewebview2.exe"),
                              ProcessEntry(22, 21, "msedgewebview2.exe")])
    log = ListLog()
    watcher = WindowsConnectionWatcher(log, "outlook-new", lambda: set(), ["olk.exe"], poll_hz=50,
                                       watched_addresses={"203.0.113.5"}, tcp_table=Tcp(), process_table=procs)
    watcher.start()
    time.sleep(0.2)
    watcher.stop()
    header = log.lines[0]
    assert header["type"] == "header" and header["os"] == "windows" and header["source"] == "iphlpapi"
    assert header["poll_hz"] == 50 and "utc_offset" in header and header["app"] == "outlook-new"
    assert log.lines[1]["type"] == "watch" and log.lines[1]["process_names"] == ["olk.exe"]
    kinds = [line["type"] for line in log.lines[2:]]
    assert kinds[:4] == ["open", "open", "close", "close"] and kinds[-1] == "stats"
    first = log.lines[2]
    assert {"t", "utc", "pid", "process", "local", "remote", "remote_port", "state"} <= set(first)
    assert first["process"] == "msedgewebview2.exe" and first["remote_port"] == 443
    stats = log.lines[-1]
    assert stats["polls"] >= 3 and stats["processes_seen"]["msedgewebview2.exe"] == 2


# ---------------------------------------------------------------------------------------------------------------
# Computer state: profiles, credentials, settings; cleanup after errors

class FakeCommands:
    def __init__(self, outputs: dict | None = None):
        self.calls = []
        self.outputs = outputs or {}
        self.registry = set()

    def run(self, command, check=False, timeout=120):
        self.calls.append(list(command))
        key = " ".join(command[:2])
        if command[:2] == ["reg", "add"] and len(command) == 4:
            self.registry.add(command[2])
        if command[:2] == ["reg", "delete"] and len(command) == 4:
            self.registry.discard(command[2])
        if command[:2] == ["reg", "query"] and len(command) == 3:
            return subprocess.CompletedProcess(command, 0 if command[2] in self.registry else 1, "", "")
        out = self.outputs.get(key, "")
        return subprocess.CompletedProcess(command, 0, out() if callable(out) else out, "")


def test_parula_profile_moved_aside_and_restored(tmp_path):
    appdata, home = tmp_path / "AppData" / "Roaming", tmp_path / "home"
    (appdata / "Parula").mkdir(parents=True)
    (appdata / "Parula" / "mail.db").write_text("Ben's mail")
    state = SessionState(tmp_path / "state.json")
    profile = ParulaProfile(state, tmp_path / "aside", appdata, home)
    moved = profile.move_user_profile_aside()
    assert len(moved) == 1 and not (appdata / "Parula").exists()
    (appdata / "Parula").mkdir()
    (appdata / "Parula" / "bench.db").write_text("benchmark")
    profile.mark()
    profile.reset()
    assert not (appdata / "Parula").exists()
    (appdata / "Parula").mkdir()
    with pytest.raises(Exception, match="refusing"):
        profile.reset()
    shutil.rmtree(appdata / "Parula")
    again = ParulaProfile(SessionState(tmp_path / "state.json"), tmp_path / "aside", appdata, home)
    assert again.restore_user_profile() == [str(appdata / "Parula")]
    assert (appdata / "Parula" / "mail.db").read_text() == "Ben's mail"
    assert SessionState(tmp_path / "state.json").get("parula_moved") == []


def test_parula_updates_renamed_and_back(tmp_path):
    resources = tmp_path / "parula" / "resources"
    resources.mkdir(parents=True)
    (resources / "app-update.yml").write_text("provider: github")
    state = SessionState(tmp_path / "state.json")
    updates = ParulaUpdates(state, tmp_path / "parula")
    assert updates.disable() and not (resources / "app-update.yml").exists()
    updates.restore()
    assert (resources / "app-update.yml").read_text() == "provider: github"


def test_credential_manager_deletes_only_new_entries_of_the_test_account():
    listing = ("Currently stored credentials:\n\n    Target: LegacyGeneric:target=MicrosoftOffice16_Data:imap:"
               f"{EMAIL}\n    Type: Generic\n\n    Target: LegacyGeneric:target=git:https://github.com\n"
               f"    Ziel: Domain:target={EMAIL}-old\n")
    targets = CredentialManager.parse_targets(listing)
    assert targets == [f"MicrosoftOffice16_Data:imap:{EMAIL}", "git:https://github.com", f"{EMAIL}-old"]
    commands = FakeCommands({"cmdkey /list": listing})
    deleted = CredentialManager(commands).delete_new(EMAIL, before=[f"{EMAIL}-old"])
    assert deleted == [f"MicrosoftOffice16_Data:imap:{EMAIL}"]
    assert ["cmdkey", f"/delete:MicrosoftOffice16_Data:imap:{EMAIL}"] in commands.calls


def test_outlook_profile_and_only_new_account_files_deleted(tmp_path):
    data = tmp_path / "Outlook"
    data.mkdir()
    (data / "ben@example.net.ost").write_text("Ben's")
    (data / f"{EMAIL}.ost").write_text("older file of the same address, from before the session")
    state = SessionState(tmp_path / "state.json")
    commands = FakeCommands({"cmdkey /list": ""})
    profile = OutlookClassicProfile(state, EMAIL, data_dir=data, runner=commands)
    profile.remember_existing()
    profile.create_empty()
    assert profile.profile_exists() and state.get("outlook_profile") == "ParulaBench"
    (data / f"{EMAIL} - ParulaBench.ost").write_text("benchmark")
    removed = profile.delete()
    assert removed["profile"] and removed["files"] == [f"{EMAIL} - ParulaBench.ost"]
    assert sorted(p.name for p in data.iterdir()) == ["ben@example.net.ost", f"{EMAIL}.ost"]
    assert not profile.profile_exists() and state.get("outlook_profile") is None


def test_windows_settings_applied_and_reverted():
    commands = FakeCommands({
        "powercfg /getactivescheme": "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
        "powercfg /list": "381b4222-f694-41f0-9685-ff5bb260df2e (Balanced) *\n"
                          "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c (High performance)",
        "reg query": "    ToastEnabled    REG_DWORD    0x1\n"})
    state = SessionState(Path(os.devnull + ".notused") if False else Path("/tmp") / f"ws-{os.getpid()}.json")
    try:
        settings = WindowsSettings(state, commands)
        changes = settings.apply()
        assert any("High performance" in c for c in changes)
        assert ["powercfg", "/setactive", WindowsSettings.high_performance] in commands.calls
        assert state.get("settings_saved") == {"power_scheme": "381b4222-f694-41f0-9685-ff5bb260df2e", "toasts": 1}
        assert settings.apply()
        assert commands.calls.count(["powercfg", "/setactive", WindowsSettings.high_performance]) == 1
        reverted = WindowsSettings(SessionState(state.path), commands).revert()
        assert ["powercfg", "/setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"] in commands.calls
        assert any(c[:2] == ["reg", "add"] and c[-3:] == ["/d", "1", "/f"] for c in commands.calls)
        assert len(reverted) == 2 and SessionState(state.path).get("settings_saved") is None
    finally:
        state.path.unlink(missing_ok=True)


def session_config(tmp_path) -> tuple[Config, Path]:
    values = {"root": tmp_path, "code": ROOT, "server": "mail.example.org", "email": EMAIL,
              "ffmpeg": "ffmpeg", "ffprobe": "ffprobe", "parula_exe": str(tmp_path / "Programs" / "parula" / "Parula.exe"),
              "outlook_exe": "C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE"}
    data = WindowsConfig.build(ROOT / "windows" / "config.windows.yaml", values)
    path = tmp_path / "state" / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data))
    return Config.load(path), path


def test_config_template_is_filled_without_secrets(tmp_path):
    config, path = session_config(tmp_path)
    text = path.read_text()
    assert "{{" not in text and "s3cret" not in text
    assert config.get("account.password_env") == "BENCH_PASSWORD"
    assert config.get("server.jmap_session_url") == "https://mail.example.org/.well-known/jmap"
    assert config.app("outlook-classic")["launch"][0].startswith("C:/Program Files/")
    assert "--remote-debugging-port=29222" in config.app("parula-jmap")["launch"]
    assert config.app("parula-jmap")["probe"]["type"] == "cdp"
    assert config.path(config.app("outlook-new")["probe"]["map"]) == ELEMENTS
    assert config.group_apps("C3") == ["parula-jmap", "outlook-classic", "outlook-new"]
    assert config.group_apps("C4") == config.group_apps("C3")
    assert config.scenario_dir == ROOT / "scenarios"
    from benchlib.scenario import ScenarioLibrary
    scenario = ScenarioLibrary(config.scenario_dir).get("T1")
    assert {a: scenario.for_app(a).flow["name"] for a in config.group_apps("C3")} == {
        "parula-jmap": "parula-setup", "outlook-classic": "outlook-classic-setup", "outlook-new": "outlook-new-setup"}
    assert scenario.for_app("outlook-new").finish_required
    assert any("background video" in d and "left out" in d for d in config.get("deviations"))
    assert not any("paused" in d for d in config.get("deviations"))


class FakeSessionDesktop:
    """Ben's text editor is open at first and closed during the wait; the console overlaps the recorded area."""

    def __init__(self):
        self.shown = []
        self.window_lists = [[(5, 50, "notes.txt - Editor", "Notepad")], []]

    def kill_by_name(self, names):
        pass

    def top_level_windows(self):
        return self.window_lists.pop(0) if len(self.window_lists) > 1 else self.window_lists[0]

    def is_minimized(self, hwnd):
        return False

    def window_geometry(self, hwnd):
        return Rect(100, 100, 800, 600)

    def has_caption(self, hwnd):
        return True

    def process_image_name(self, pid):
        return "notepad.exe"

    def console_window(self):
        return 77

    def show_window(self, hwnd, minimized):
        self.shown.append((hwnd, minimized))


@pytest.fixture
def windows_env(tmp_path, monkeypatch):
    for name, sub in (("APPDATA", "AppData/Roaming"), ("USERPROFILE", "home"), ("LOCALAPPDATA", "AppData/Local")):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(name, str(tmp_path / sub))
    monkeypatch.setenv("BENCH_PASSWORD", "s3cret-Pw")
    (tmp_path / "AppData/Local/Microsoft/Outlook").mkdir(parents=True)
    (tmp_path / "AppData/Roaming/Parula").mkdir()
    (tmp_path / "AppData/Roaming/Parula/settings.json").write_text("Ben's settings")
    resources = tmp_path / "Programs" / "parula" / "resources"
    resources.mkdir(parents=True)
    (resources / "app-update.yml").write_text("provider: github")
    found = {"checked_utc": "2026-10-24T08:00:00+00:00", "domain": "example.org", "server_hosts": ["mail.example.org"],
             "sources": [{"source": "autoconfig (.well-known)", "url": "https://example.org/.well-known/x",
                          "status": 200, "hosts": ["mail.beonex.example"]}],
             "other_hosts": ["mail.beonex.example"], "other_sources": ["autoconfig (.well-known)"], "unchecked": [],
             "guarded": True}
    monkeypatch.setattr("benchlib.stages.PublishedConfig.check", lambda self: found)
    return tmp_path


def make_session(tmp_path, commands):
    config, _ = session_config(tmp_path)
    return WindowsSession(config, tmp_path, lambda m: None, commands, FakeSessionDesktop())


def test_session_error_in_preflight_still_undoes_everything(windows_env, monkeypatch):
    tmp_path = windows_env
    commands = FakeCommands({"powercfg /getactivescheme": "GUID: 381b4222-f694-41f0-9685-ff5bb260df2e",
                             "powercfg /list": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "cmdkey /list": ""})
    session = make_session(tmp_path, commands)

    def failing_preflight(self):
        raise RuntimeError("UI Automation found nothing")

    monkeypatch.setattr("benchlib.winsession.Preflight.run", failing_preflight)
    monkeypatch.setattr("benchlib.winsession.time.sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        session.run()
    desktop = session.pipeline.desktop
    assert desktop.shown == [(77, True)]
    assert not (tmp_path / "AppData/Roaming/Parula").exists()
    assert not (tmp_path / "Programs/parula/resources/app-update.yml").exists()
    manifest = session.folder.manifest()
    assert manifest["os"] == "windows" and manifest["corpus"]["inbox_messages"] == 30000
    assert manifest["config"]["account"]["email"] == "<redacted>@example.org"
    assert any("Power plan" in d for d in manifest["deviations"])
    assert any("moved aside" in d for d in manifest["deviations"])
    assert manifest["server_discovery"]["other_hosts"] == ["mail.beonex.example"]
    assert any(d.startswith("Server check: before the session, autoconfig (.well-known) named "
                            "mail.beonex.example") for d in manifest["deviations"])
    german = ManifestTexts(session.config, "de").lines(session.folder.path, "deviations")
    assert german is not None and any("Energiesparplan" in d for d in german)
    assert "s3cret" not in json.dumps(manifest)
    done = session.cleanup()
    assert (tmp_path / "AppData/Roaming/Parula/settings.json").read_text() == "Ben's settings"
    assert (tmp_path / "Programs/parula/resources/app-update.yml").exists()
    assert ["powercfg", "/setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"] in commands.calls
    assert any("Parula: the user's profile is back" in line for line in done)
    assert session.state.get("settings_saved") is None
    assert desktop.shown == [(77, True), (77, False)]


def test_crash_recovery_by_a_new_session(windows_env):
    tmp_path = windows_env
    commands = FakeCommands({"powercfg /getactivescheme": "GUID: 381b4222-f694-41f0-9685-ff5bb260df2e",
                             "powercfg /list": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "cmdkey /list": ""})
    crashed = make_session(tmp_path, commands)
    WindowsSettings(crashed.state, commands).apply()
    crashed.lifecycles["parula-jmap"].before_session()
    crashed.lifecycles["outlook-classic"].before_session()
    crashed.lifecycles["outlook-classic"].reset()
    (tmp_path / "AppData/Roaming/Parula").mkdir()
    (tmp_path / "AppData/Roaming/Parula/bench.db").write_text("half a run")
    later = make_session(tmp_path, commands)
    later.cleanup()
    assert (tmp_path / "AppData/Roaming/Parula/settings.json").read_text() == "Ben's settings"
    assert not (tmp_path / "AppData/Roaming/Parula/bench.db").exists()
    assert not commands.registry
    assert later.state.get("parula_moved") == [] and later.state.get("outlook_profile") is None
    assert not (tmp_path / "results-windows").exists() and not list(tmp_path.glob("results-windows-*"))


def test_preflight_finds_each_apps_first_page_or_its_first_run_notice_and_resets_it(windows_env, monkeypatch):
    from benchlib.winsession import Preflight
    commands = FakeCommands({"cmdkey /list": ""})
    session = make_session(windows_env, commands)
    shown = {"outlook-classic": "notice", "parula-jmap": "email", "outlook-new": "mail"}

    class StartProbe:
        language = "en"

        def __init__(self, app_id):
            self.app_id = app_id

        def attach(self, app, timeout_s):
            pass

        def wait_page(self, pages, timeout_s, on_interruption=None):
            page = shown[self.app_id]
            if page == "notice":
                on_interruption("privacy.next")
            if page not in pages:
                raise RuntimeError(f"Expected one of the pages {sorted(pages)}, but it shows '{page}'")
            return page

        def dump(self, path):
            Path(path).write_text("tree")

        def close(self):
            pass

    class StartedApp:
        def launch(self):
            pass

        def close(self):
            return True

    monkeypatch.setattr("benchlib.winsession.Probes.create",
                        lambda spec, config: StartProbe(next(a for a in shown if config.app(a)["probe"] == spec)))
    for lifecycle in session.lifecycles.values():
        monkeypatch.setattr(lifecycle, "app_process", lambda *args: StartedApp())
    session.pipeline.desktop.screenshot = lambda path: Path(path).write_bytes(b"png")
    session.folder = session.pipeline.results_folder()
    out = session.folder.path / "preflight"
    out.mkdir()
    preflight = Preflight(session)
    refused = preflight.app("parula-jmap", out)
    assert not refused["ok"] and "refusing to delete" in refused["error"] and "refusing to mark" in refused["reset_error"]
    assert (windows_env / "AppData/Roaming/Parula/settings.json").read_text() == "Ben's settings"
    session.lifecycles["parula-jmap"].before_session()
    classic = preflight.app("outlook-classic", out)
    assert classic["ok"] and classic["page"] == "notice closed by privacy.next" and classic["closed_cleanly"]
    parula = preflight.app("parula-jmap", out)
    assert parula["ok"], parula
    new = preflight.app("outlook-new", out)
    assert not new["ok"] and "'mail'" in new["error"]
    assert (out / "outlook-new.png").exists() and (out / "outlook-new-ui-dump.json").read_text() == "tree"
    assert not commands.registry
    session.cleanup()
    assert (windows_env / "AppData/Roaming/Parula/settings.json").read_text() == "Ben's settings"


def test_window_titles_in_the_run_record_show_the_account_only_as_its_domain(windows_env):
    session = make_session(windows_env, FakeCommands())
    assert session.hide_address(f"Inbox - {EMAIL} - Outlook") == "Inbox - <account>@example.org - Outlook"


# ---------------------------------------------------------------------------------------------------------------
# Run plan (the shared Orchestrator with the Windows executor's interface)

class PlanExecutor:
    server_log = None

    def __init__(self, root: Path, fail_once: set):
        self.root = root
        self.fail_once = set(fail_once)
        self.executed = []

    def run_dir(self, comparison, task, app_id, run_id):
        return self.root / "runs" / app_id / task / run_id

    def execute(self, comparison, task, app_id, run_id, warmup, order, reference_run=False, record=True, attempt=1):
        run_dir = self.run_dir(comparison, task, app_id, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        failed = (app_id, run_id) in self.fail_once and attempt == 1
        (run_dir / "meta.json").write_text(json.dumps({"status": "failed" if failed else "complete",
                                                       "failure": "technical" if failed else None}))
        self.executed.append((app_id, run_id, attempt))
        return run_dir


def test_run_plan_interleaves_all_apps_and_re_records_failures_at_the_end(tmp_path):
    config, _ = session_config(tmp_path)
    executor = PlanExecutor(tmp_path, {("outlook-new", "run-2")})
    Orchestrator(config, executor, lambda m: None, None).run_comparison("C3", resume=False)
    apps = ["parula-jmap", "outlook-classic", "outlook-new"]
    expected = [(a, "warmup-1", 1) for a in apps] + [(a, f"run-{r}", 1) for r in range(1, 6) for a in apps]
    assert executor.executed[:len(expected)] == expected
    assert executor.executed[len(expected):] == [("outlook-new", "run-2", 2)]
    assert (tmp_path / "runs/outlook-new/T1/run-2.failed-1/meta.json").exists()


# ---------------------------------------------------------------------------------------------------------------
# Display, corpus expectations, the note for Ben

def test_display_plan_fits_the_window_and_marker_or_says_how_to_fix_it():
    full_hd = DisplayPlan.compute(Rect(0, 0, 1920, 1032), 100)
    assert full_hd["ok"] and full_hd["app_region"] == {"x": 0, "y": 0, "width": 1280, "height": 940}
    assert full_hd["pointer_park"]["x"] > 1280
    laptop = DisplayPlan.compute(Rect(0, 0, 1920, 1032), 150)
    assert not laptop["ok"] and "100 %" in laptop["fix"]
    qhd = DisplayPlan.compute(Rect(0, 0, 2560, 1392), 125)
    assert qhd["ok"] and qhd["app_region"]["width"] == 1600 and qhd["app_region"]["height"] == 1174
    uhd = DisplayPlan.compute(Rect(0, 0, 3840, 2088), 150)
    assert uhd["ok"] and uhd["app_region"]["width"] == 1920


def test_inbox_expectations_include_the_unread_count_new_outlook_shows(windows_env):
    config, _ = session_config(windows_env)
    session = AccountSession(AccountServer.from_config(config), CorpusGenerator(CorpusSpec.from_dict(config.get("corpus"))))
    expected = session.expected
    assert expected["inbox_messages"] == 30000 and 0 < expected["inbox_unread"] < 30000
    assert expected["inbox_oldest_subject"] != expected["inbox_newest_subject"]


# ---------------------------------------------------------------------------------------------------------------
# PowerShell: parse and lint (needs PowerShell 7 + PSScriptAnalyzer; BENCH_PWSH=<pwsh>, BENCH_PSSA=<module dir>)

@pytest.mark.skipif(not os.environ.get("BENCH_PWSH"), reason="set BENCH_PWSH to a pwsh binary")
def test_powershell_script_parses_and_is_compatible_with_windows_powershell_5_1():
    script = ROOT / "windows" / "run-windows-tests.ps1"
    module = os.environ.get("BENCH_PSSA", "PSScriptAnalyzer")
    command = f"""
$errors = $null; $tokens = $null
[void][System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ $errors | ForEach-Object {{ 'PARSE ' + $_.ToString() }}; exit 3 }}
Import-Module '{module}'
$settings = @{{ Rules = @{{ PSUseCompatibleSyntax = @{{ Enable = $true; TargetVersions = @('5.1') }};
  PSUseCompatibleCommands = @{{ Enable = $true; TargetProfiles = @('win-48_x64_10.0.17763.0_5.1.17763.316_x64_4.0.30319.42000_framework') }};
  PSUseCompatibleTypes = @{{ Enable = $true; TargetProfiles = @('win-48_x64_10.0.17763.0_5.1.17763.316_x64_4.0.30319.42000_framework') }} }} }}
$found = @(Invoke-ScriptAnalyzer -Path '{script}' -Severity Warning,Error) + @(Invoke-ScriptAnalyzer -Path '{script}' -Settings $settings)
$found | ForEach-Object {{ 'LINT ' + $_.RuleName + ' line ' + $_.Line + ': ' + $_.Message }}
exit $found.Count
"""
    out = subprocess.run([os.environ["BENCH_PWSH"], "-NoProfile", "-NonInteractive", "-Command", command],
                         capture_output=True, text=True, env={**os.environ, "NO_COLOR": "1"}, timeout=600)
    assert out.returncode == 0, out.stdout + out.stderr


class PrereqDesktop:
    def __init__(self, work_area=Rect(0, 0, 1920, 1032), scale=100, on_ac=True, running=()):
        self.work_area, self.scale, self.on_ac, self.running = work_area, scale, on_ac, set(running)

    def primary_monitor(self):
        return {"monitor": Rect(0, 0, self.work_area.width, self.work_area.height + 48), "work_area": self.work_area}

    def scale_percent(self):
        return self.scale

    def on_ac_power(self):
        return self.on_ac

    def running_image_names(self):
        return self.running


class PrereqAccount:
    def __init__(self, report=None, error=None):
        self.report, self.error = report, error

    def check(self, repair):
        assert repair is False
        if self.error:
            raise self.error
        return self.report


def prereq_commands(command, **_):
    text = " ".join(command)
    out = {"-filters": " ... ddagrab V->V Grab Windows desktop", "-encoders": " V..... libx264rgb"}
    stdout = next((v for k, v in out.items() if text.endswith(k)), "")
    if "Win32_OperatingSystem" in text:
        stdout = "Microsoft Windows 11 Pro"
    if "Get-AppxPackage" in text:
        stdout = "1.2026.1001.400"
    return subprocess.CompletedProcess(command, 0, stdout, "")


def test_prerequisites_report_what_to_fix(tmp_path):
    config, _ = session_config(tmp_path)
    (tmp_path / "Programs" / "parula").mkdir(parents=True)
    (tmp_path / "Programs" / "parula" / "Parula.exe").write_text("")
    seeded = {"ok": True, "protocol": "imap", "before": {"ok": True, "folders": {"Inbox": {"expected": 30000,
                                                                                    "actual": 30000}}}}
    from benchlib.winsession import Prerequisites
    good = Prerequisites(config, PrereqDesktop(), PrereqAccount(seeded).check, lambda m: None, prereq_commands).run(tmp_path)
    names = {c["name"]: c for c in good["checks"]}
    assert names["Parula installed"]["ok"] and names["Outlook (new) installed"]["ok"]
    assert not names["Outlook (classic) installed"]["ok"]
    assert "Microsoft 365" in names["Outlook (classic) installed"]["fix"]
    assert names["ffmpeg with ddagrab and libx264rgb"]["ok"] and names["Mail account seeded"]["ok"]
    assert good["display"]["ok"] and not good["ok"]

    unseeded = {"ok": False, "before": {"ok": False, "folders": {"Inbox": {"expected": 30000, "actual": 12}}}}
    bad = Prerequisites(config, PrereqDesktop(Rect(0, 0, 1280, 672), 150, on_ac=False, running={"olk.exe"}),
                        PrereqAccount(unseeded).check, lambda m: None, prereq_commands).run(tmp_path)
    names = {c["name"]: c for c in bad["checks"]}
    assert not names["Display"]["ok"] and "100 %" in names["Display"]["fix"]
    assert not names["Power supply"]["ok"] and names["Power supply"]["fatal"]
    assert not names["The test apps are closed"]["ok"] and "olk.exe" in names["The test apps are closed"]["fix"]
    assert not names["Mail account seeded"]["ok"] and "Seeding is done once" in names["Mail account seeded"]["fix"]
    assert "Inbox 12/30000" in names["Mail account seeded"]["detail"]

    unreachable = Prerequisites(config, PrereqDesktop(), PrereqAccount(error=OSError("connection refused")).check,
                                lambda m: None, prereq_commands).run(tmp_path)
    check = next(c for c in unreachable["checks"] if c["name"] == "Mail account reachable")
    assert not check["ok"] and "connection refused" in check["detail"]
