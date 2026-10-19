"""Unit tests of the Windows package with fakes (it can't run here): UI Automation lookups by English and German
names, page detection, the setup flows of all three apps, the Inbox probes, the network log, the run plan and the
cleanup after errors. Run: python -m pytest tests/test_windows.py"""

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

from benchlib.config import Config  # noqa: E402
from benchlib.driver import EventLog, ScenarioDriver, TextVariables  # noqa: E402
from benchlib.runner import Orchestrator  # noqa: E402
from benchlib.settle import Rect  # noqa: E402
from benchlib.uia import ElementInfo, ElementQuery, UiaError, UiTree  # noqa: E402
from benchlib.winapps import (CredentialManager, OutlookClassicProfile, ParulaProfile, ParulaUpdates,  # noqa: E402
                              SessionState, WindowsSettings)
from benchlib.winflows import (FlowError, NewOutlookRemoval, NewOutlookSetupFlow, OutlookClassicSetupFlow,  # noqa: E402
                               ParulaSetupFlow, WindowsFlowContext)
from benchlib.winnet import ConnectionTracker, ProcessEntry, ProcessTable, TcpRow, TcpTable, WindowsConnectionWatcher  # noqa: E402
from benchlib.winprobe import CountText, UiaAppMap, UiaProbe  # noqa: E402
from benchlib.winsession import (DisplayPlan, InboxExpectations, ReadmeFirst, WindowsConfig,  # noqa: E402
                                 WindowsSession)

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
        self.focus: str | None = None
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
                self.focus = node.info.name
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
        self.focus = node.info.name
        action = self.on_click.get((self.page, node.info.name))
        if action:
            action(node)

    def key(self, combo):
        action = self.on_key.get((self.page, combo))
        if action:
            action()

    def type(self, text):
        self.typed[self.focus or ""] = text


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


class FakeLive:
    def __init__(self):
        self.calls = 0

    def wait_settled(self, since, quiet_s, timeout_s, label, expect_change=True, no_reaction_s=None, **_):
        self.calls += 1
        now = EventLog.now()
        return "settled", {"live_end": None if not expect_change and label.endswith(":still") else now,
                           "live_quiet_s": quiet_s}


class StillLive(FakeLive):
    """Reports no change during the "stays still" check after a confirmation."""

    def wait_settled(self, since, quiet_s, timeout_s, label, expect_change=True, no_reaction_s=None, **_):
        self.calls += 1
        if not expect_change:
            return "settled", {"live_end": None, "live_quiet_s": quiet_s}
        return "settled", {"live_end": EventLog.now(), "live_quiet_s": quiet_s}


def make_context(tmp_path, app: FakeApp, kind: str, expected: dict | None = None, variables: dict | None = None):
    clock = FakeClock()
    backend = app.backend
    probe = UiaProbe(UiaAppMap.load(ELEMENTS, kind), backend_factory=lambda: backend,
                     process_table=FakeProcessTable([ProcessEntry(app.pid, 1, UiaAppMap.load(ELEMENTS, kind).process_names[0])]),
                     sleep=clock.sleep, clock=clock)
    probe.tree = UiTree(backend, lambda: {app.pid})
    values = {"account.email": EMAIL, "account.password": "s3cret-Pw", "server.jmap_url":
              "https://mail.example.org/.well-known/jmap"}
    values.update(variables or {})
    log = EventLog(tmp_path / "driver.jsonl")

    class Region:
        region = Rect(0, 0, 1280, 940)

    driver = ScenarioDriver(FakeDesktop(app), FakeAppProcess(), Region(), TextVariables(values, {"account.password"}),
                            log, park=(1500, 900))
    driver.live = StillLive()
    ctx = WindowsFlowContext(driver, probe, expected or {"inbox_messages": 30000, "inbox_unread": 1500},
                             tmp_path / "diag", element_timeout_s=5, step_timeout_s=60)
    return ctx, log


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
    assert set(data) == {"parula", "outlook-classic", "outlook-new"}
    for kind in data:
        app_map = UiaAppMap.load(ELEMENTS, kind)
        assert app_map.process_names
        for name, source in app_map.sources.items():
            assert source in ("parula-source", "docs", "assumed"), (kind, name)
            query = app_map.query(name)
            if query.names:
                assert set(query.names) == {"en", "de"}, (kind, name)
    flows_use = {"parula": ["button.pause", "button.skip", "button.add_email", "field.email", "field.password",
                            "button.manual", "combo.protocol", "option.jmap", "field.url", "button.next",
                            "radio.imap"],
                 "outlook-classic": ["field.email", "button.connect", "tile.imap", "button.next", "field.password",
                                     "checkbox.mobile", "button.done"],
                 "outlook-new": ["field.email", "button.continue", "option.imap", "field.password", "button.done",
                                 "button.settings", "nav.accounts", "nav.email_accounts", "button.manage",
                                 "button.remove", "option.remove_all_devices", "button.confirm"]}
    for kind, names in flows_use.items():
        app_map = UiaAppMap.load(ELEMENTS, kind)
        for name in names:
            app_map.query(name)


def test_count_text_parses_both_languages():
    assert CountText.parse("30,000") == 30000
    assert CountText.parse("30.000") == 30000
    assert CountText.parse("30\u202f000") == 30000
    assert CountText.parse(" 1 500 ") == 1500
    assert CountText.parse("about 30k") is None
    assert CountText.parse(None) is None


# ---------------------------------------------------------------------------------------------------------------
# Parula (names verified in its source): the manual JMAP path, English and German

def parula_pages(lang: str):
    t = {"en": {"first": "Set up your first account", "add": "Add email address", "setup": "Set up existing email address",
                "pw": "Your password", "manual": "Manual setup", "next": "Next", "mc": "Manual configuration",
                "auth": "Authentication method", "ready": f"{EMAIL} is working and ready", "mails": "{0} mails",
                "imp": "Import accounts", "skip": "Skip",
                "found": "We received the configuration from your email provider."},
         "de": {"first": "Richten Sie Ihr erstes Konto ein", "add": "E-Mail-Adresse hinzufügen",
                "setup": "Vorhandene E-Mail-Adresse einrichten", "pw": "Ihr Passwort", "manual": "Manuelles Setup",
                "next": "Weiter", "mc": "Manuelle Konfiguration", "auth": "Authentifizierungs-Methode",
                "ready": f"{EMAIL} funktioniert und ist bereit", "mails": "{0} Mails", "imp": "Konten importieren",
                "skip": "Überspringen", "found": "Wir haben die Konfiguration von Ihrem E-Mail-Anbieter erhalten."}}[lang]
    count = {"n": 0}
    pages = {
        "import-accounts": [element("Text", t["imp"]), element("Button", t["skip"], y=600)],
        "first-account": [element("Text", t["first"]), element("Button", t["add"], y=100)],
        "setup-mail": [element("Text", t["setup"]), element("Edit", "you@example.com", y=100),
                       element("Edit", t["pw"], y=150, is_password=True), element("Button", t["manual"], y=600),
                       element("Button", t["next"], x=300, y=600), element("Button", "Pause", y=900, focused=True)],
        "found-config": [element("Text", t["found"]), element("Text", "IMAP mail.example.org", y=60),
                         element("Button", t["manual"], y=600), element("Button", t["next"], x=300, y=600)],
        "manual": [element("Text", t["mc"]), element("ComboBox", "", y=100), element("Edit", "", x=300, y=100),
                   element("Button", t["next"], x=300, y=600)],
        "manual-url": [element("Text", t["mc"]), element("Text", "URL", x=10, y=80), element("ComboBox", "", y=100),
                       element("Edit", "", x=300, y=100, value=""), element("Button", t["next"], x=300, y=600)],
        "manual-url-full": [element("Text", t["mc"]), element("Text", "URL", x=10, y=80),
                            element("Text", t["auth"], x=10, y=200), element("ComboBox", "", y=100),
                            element("Edit", "", x=300, y=100), element("Button", t["next"], x=300, y=600)],
        "ready": [element("Text", t["ready"]), element("Button", t["next"], x=300, y=600)],
        "mail": lambda: [element("Text", t["mails"].format(count["n"]), y=900),
                         element("Text", "Subject of the newest message", y=100)],
    }
    return pages, t, count


@pytest.mark.parametrize("lang", ["en", "de"])
def test_parula_flow_sets_up_jmap_manually_and_waits_for_the_full_inbox(tmp_path, lang):
    backend = FakeBackend()
    pages, t, count = parula_pages(lang)
    app = FakeApp(backend, pages, "import-accounts")
    app.on_click = {
        ("import-accounts", t["skip"]): lambda n: app.show("first-account"),
        ("first-account", t["add"]): lambda n: app.show("setup-mail"),
        ("found-config", t["manual"]): lambda n: app.show("manual"),
        ("manual-url", t["next"]): lambda n: app.show("manual-url-full"),
        ("manual-url-full", t["next"]): lambda n: app.show("ready"),
        ("ready", t["next"]): lambda n: app.show("mail"),
    }
    selected = []

    def setup_return():
        if app.focus == "you@example.com":
            app.focus = t["pw"]
            for n in backend.all_nodes():
                n.info.focused = n.info.name == t["pw"]
        elif app.focus == t["pw"]:
            app.show("found-config")

    app.on_key = {("setup-mail", "Return"): setup_return, ("manual", "j"): lambda: selected.append("JMAP"),
                  ("manual", "Return"): lambda: app.show("manual-url") if selected else None}
    ctx, log = make_context(tmp_path, app, "parula")
    original_inbox_listed = ctx.probe.inbox_listed

    def growing(expected):
        count["n"] = min(30000, count["n"] + 12000)
        app.show("mail")
        return original_inbox_listed(expected)

    ctx.probe.inbox_listed = growing
    ParulaSetupFlow("jmap").run(ctx)

    assert app.typed["you@example.com"] == EMAIL
    assert app.typed[t["pw"]] == "s3cret-Pw"
    assert app.typed[""] == "https://mail.example.org/.well-known/jmap"
    assert [s["name"] for s in ctx.steps] == ["skip-import", "find-config", "manual-setup", "show-details",
                                               "check-config", "open-inbox"]
    assert ctx.steps[-1]["final"] and ctx.final_done
    assert "found configuration offers no JMAP: manual setup" in ctx.flow_path and "video-paused" in ctx.flow_path
    assert ctx.probe.language == lang
    # skip; add; type address, Return, type password, Return; manual setup; protocol, j, Return; URL field,
    # ctrl+a, type URL; next, next, next (the same actions as the Linux flow, plus the skip of the import page)
    assert ctx.user_actions == 16
    assert ctx.prep_actions == 2
    assert ctx.steps[1]["actions"] == ["click button.add_email", "type “${account.email}”", "key Return",
                                       "type the password", "key Return"]
    events = EventLog.read(log.path)
    probes = [e for e in events if e["type"] == "probe" and e["step"] == "open-inbox"]
    assert [p["complete"] for p in probes] == [False, False, True]
    assert probes[-1]["listed"] == 30000
    assert all(e.get("arg") != "s3cret-Pw" for e in events)
    starts = [e for e in events if e["type"] == "step_start"]
    assert [e["step"] for e in starts] == [s["name"] for s in ctx.steps]
    # what the shared analysis rebuilds the steps from (Step.from_checks) and where each step ended
    assert starts[-1]["checks"]["complete"] == "inbox_listed" and starts[-1]["checks"]["after_end"] == "fail"
    assert starts[1]["checks"]["complete"].startswith("page:") and not starts[1]["checks"]["verify_probe"]
    settled = [e for e in events if e["type"] == "step_live_settled"]
    assert [e["step"] for e in settled] == [s["name"] for s in ctx.steps]
    assert all(e["confirmed_at"] >= e["live_end"] for e in settled)
    assert [e["phase"] for e in events if e["type"] == "input" and e["phase"] != "step"] == ["prepare", "prepare"]
    summary = ctx.summary()
    assert summary["action_list"][:2] == ["click button.skip", "click button.add_email"]
    assert summary["preparations"] == ["click button.pause", "click field.email"]


def test_unknown_page_stops_the_flow_with_a_ui_dump(tmp_path):
    backend = FakeBackend()
    app = FakeApp(backend, {"odd": [element("Text", "Something unexpected")]}, "odd")
    ctx, _ = make_context(tmp_path, app, "parula")
    with pytest.raises(FlowError, match="flow-error-1.txt"):
        ParulaSetupFlow("jmap").run(ctx)
    assert "Something unexpected" in (tmp_path / "diag" / "flow-error-1.txt").read_text()


# ---------------------------------------------------------------------------------------------------------------
# Outlook (classic), German UI

def test_outlook_classic_flow_german_unchecks_outlook_mobile_and_waits_for_the_item_count(tmp_path):
    backend = FakeBackend()
    items = {"n": 4000}
    pages = {
        "account-email": [element("Edit", "E-Mail-Adresse", focused=True), element("Hyperlink", "Erweiterte Optionen", y=60),
                          element("Button", "Verbinden", y=120)],
        "advanced-setup": [element("Text", "Erweitertes Setup"), element("Button", "IMAP", y=100),
                           element("Button", "POP", y=140)],
        "password": [element("Edit", "Kennwort", is_password=True, focused=True), element("Button", "Verbinden", y=120)],
        "done": [element("Text", "Konto erfolgreich hinzugefügt"),
                 element("CheckBox", "Outlook Mobile auch auf meinem Telefon einrichten", y=80, toggle_state=1),
                 element("Button", "Fertig", y=120)],
        "mail": lambda: [element("Text", f"Elemente: {items['n']:,}".replace(",", "."), y=920),
                         element("Text", "Alle Ordner sind auf dem neuesten Stand.", x=300, y=920)],
    }
    app = FakeApp(backend, pages, "account-email")
    app.on_click = {("account-email", "Verbinden"): lambda n: app.show("advanced-setup"),
                    ("advanced-setup", "IMAP"): lambda n: app.show("password"),
                    ("password", "Verbinden"): lambda n: app.show("done"),
                    ("done", "Outlook Mobile auch auf meinem Telefon einrichten"):
                        lambda n: setattr(n.info, "toggle_state", 0),
                    ("done", "Fertig"): lambda n: app.show("mail")}
    ctx, log = make_context(tmp_path, app, "outlook-classic")
    original = ctx.probe.inbox_listed

    def growing(expected):
        items["n"] = min(30000, items["n"] + 13000)
        app.show("mail")
        return original(expected)

    ctx.probe.inbox_listed = growing
    OutlookClassicSetupFlow().run(ctx)
    assert app.typed["E-Mail-Adresse"] == EMAIL and app.typed["Kennwort"] == "s3cret-Pw"
    assert [s["name"] for s in ctx.steps] == ["connect", "choose-imap", "login", "open-inbox"]
    assert "unchecked-outlook-mobile" in ctx.flow_path and "advanced-setup" in ctx.flow_path
    assert ctx.probe.language == "de"
    assert ctx.user_actions == 7
    final = [e for e in EventLog.read(log.path) if e["type"] == "probe" and e["step"] == "open-inbox"]
    assert final[-1]["complete"] and final[-1]["listed"] == 30000 and final[-1]["idle"] is True


# ---------------------------------------------------------------------------------------------------------------
# New Outlook, English UI: setup, the cloud-sync notice, the probes, the removal from all devices

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
        "imap-form": [element("Edit", "Email address"), element("Edit", "IMAP password", y=60, is_password=True),
                      element("Button", "Continue", y=120)],
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


def test_new_outlook_flow_and_removal_from_all_devices(tmp_path):
    backend = FakeBackend()
    state = {"size": 500, "unread": 100}
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
    ctx, log = make_context(tmp_path, app, "outlook-new",
                            {"inbox_messages": 30000, "inbox_unread": 1500,
                             "inbox_oldest_subject": "Oldest subject in the corpus",
                             "inbox_newest_subject": "Newest subject in the corpus"})
    original = ctx.probe.inbox_listed

    def growing(expected):
        state["size"] = min(30000, state["size"] * 4)
        state["unread"] = min(1500, state["unread"] * 4)
        if app.page == "mail":
            app.show("mail")
        return original(expected)

    ctx.probe.inbox_listed = growing
    NewOutlookSetupFlow().run(ctx)
    assert [s["name"] for s in ctx.steps] == ["continue", "choose-imap", "connect", "cloud-sync", "open-inbox"]
    assert ctx.flow_path[:4] == ["choose-provider", "imap-form", "cloud-sync", "success"]
    final = [e for e in EventLog.read(log.path) if e["type"] == "probe" and e["step"] == "open-inbox"]
    assert final[-1]["complete"] and final[-1]["listed"] == 30000 and final[-1]["listed_from"] == "size_of_set"

    def press_end():
        state["oldest_visible"] = True
        app.show("mail")

    app.on_key = {("mail", "End"): press_end}
    verify = ctx.verify()
    assert verify["inbox_complete"] and verify["oldest_visible"] and verify["newest_visible"]
    assert verify["step"] == "open-inbox" and verify["oldest_subject"] == "Oldest subject in the corpus"
    kinds = [e["type"] for e in EventLog.read(log.path)]
    assert kinds.index("verify_start") < kinds.index("verify_end")
    assert verify["listed"] == 30000 and verify["basis"] == "count"
    verify_inputs = [e for e in EventLog.read(log.path) if e["type"] == "input" and e["phase"] == "verify"]
    assert [e["action"] for e in verify_inputs] == ["click", "key"]
    actions_before = ctx.user_actions

    assert NewOutlookRemoval(EMAIL).run(ctx)
    assert manage_clicked == [200]
    assert app.history[-1] == "gone"
    assert ctx.user_actions == actions_before
    finish = [e for e in EventLog.read(log.path) if e["type"] == "input" and e["phase"] == "finish"]
    assert len(finish) == 7


def test_new_outlook_with_an_existing_account_stops_before_typing(tmp_path):
    backend = FakeBackend()
    app = FakeApp(backend, new_outlook_pages({"size": 1, "unread": 1}), "mail")
    ctx, _ = make_context(tmp_path, app, "outlook-new")
    with pytest.raises(FlowError, match="already has an account"):
        NewOutlookSetupFlow().run(ctx)
    assert app.typed == {}


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
    return Config(data, path.parent), path


def test_config_template_is_filled_without_secrets(tmp_path):
    config, path = session_config(tmp_path)
    text = path.read_text()
    assert "{{" not in text and "s3cret" not in text
    assert config.get("account.password_env") == "BENCH_PASSWORD"
    assert config.app("outlook-classic")["launch"][0].startswith("C:/Program Files/")
    assert config.group_apps("C3") == ["parula-jmap", "outlook-classic", "outlook-new"]
    assert config.group_apps("C4") == config.group_apps("C3")
    assert config.scenario_dir == ROOT / "windows" / "scenarios"
    from benchlib.scenario import ScenarioLibrary
    scenario = ScenarioLibrary(config.scenario_dir).get("T1")
    assert set(scenario.apps) == {"parula-jmap", "outlook-classic", "outlook-new"}


class FakeFolder:
    def __init__(self, path):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self.manifest = {}

    def write_manifest(self, **sections):
        self.manifest.update(sections)

    def run_dir(self, app_id, task, run_id):
        return self.path / "runs" / app_id / task / run_id


class FakeCore:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path

    def result_folder(self, parent):
        return FakeFolder(self.tmp_path / "results-windows-test")

    def check_account(self, repair):
        return {"ok": True}


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
    (tmp_path / "AppData/Local/Microsoft/Outlook").mkdir(parents=True)
    (tmp_path / "AppData/Roaming/Parula").mkdir()
    (tmp_path / "AppData/Roaming/Parula/settings.json").write_text("Ben's settings")
    resources = tmp_path / "Programs" / "parula" / "resources"
    resources.mkdir(parents=True)
    (resources / "app-update.yml").write_text("provider: github")
    return tmp_path


def make_session(tmp_path, commands):
    config, path = session_config(tmp_path)
    return WindowsSession(config, path, tmp_path, FakeSessionDesktop(), core=FakeCore(tmp_path),
                          progress=lambda m: None, password="s3cret-Pw", commands=commands)


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
    assert session.desktop.shown == [(77, True)]
    assert not (tmp_path / "AppData/Roaming/Parula").exists()
    assert not (tmp_path / "Programs/parula/resources/app-update.yml").exists()
    assert session.folder.manifest["corpus"]["inbox_messages"] == 30000
    done = session.cleanup()
    assert (tmp_path / "AppData/Roaming/Parula/settings.json").read_text() == "Ben's settings"
    assert (tmp_path / "Programs/parula/resources/app-update.yml").exists()
    assert ["powercfg", "/setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"] in commands.calls
    assert any("Parula: the user's profile is back" in line for line in done)
    assert session.state.get("settings_saved") is None
    assert session.desktop.shown == [(77, True), (77, False)]


def test_crash_recovery_by_a_new_session(windows_env):
    tmp_path = windows_env
    commands = FakeCommands({"powercfg /getactivescheme": "GUID: 381b4222-f694-41f0-9685-ff5bb260df2e",
                             "powercfg /list": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "cmdkey /list": ""})
    crashed = make_session(tmp_path, commands)
    WindowsSettings(crashed.state, commands).apply()
    crashed.adapters["parula-jmap"].before_session()
    crashed.adapters["outlook-classic"].before_session()
    crashed.adapters["outlook-classic"].reset()
    (tmp_path / "AppData/Roaming/Parula").mkdir()
    (tmp_path / "AppData/Roaming/Parula/bench.db").write_text("half a run")
    later = make_session(tmp_path, commands)
    later.cleanup()
    assert (tmp_path / "AppData/Roaming/Parula/settings.json").read_text() == "Ben's settings"
    assert not (tmp_path / "AppData/Roaming/Parula/bench.db").exists()
    assert not commands.registry
    assert later.state.get("parula_moved") == [] and later.state.get("outlook_profile") is None


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


def test_inbox_expectations_from_the_corpus_layout(tmp_path):
    config, _ = session_config(tmp_path)
    expected = InboxExpectations.compute(config)
    assert expected["inbox_messages"] == 30000 and expected["inbox_folder"] == "Inbox"
    assert 0 < expected["inbox_unread"] < 30000
    assert expected["inbox_oldest_subject"] and expected["inbox_newest_subject"]
    assert expected["inbox_oldest_subject"] != expected["inbox_newest_subject"]


def test_readme_first_names_the_zip_and_what_to_send(tmp_path):
    folder = tmp_path / "results-windows-20261019-0100"
    folder.mkdir()
    (folder / "capture.mkv").write_bytes(b"x" * 2_000_000)
    zip_path = tmp_path / "results-windows-20261019-0100.zip"
    zip_path.write_bytes(b"z" * 1_500_000)
    text = ReadmeFirst.write(folder, zip_path, True)
    assert "finished" in text and str(zip_path) in text and "2 MB" in text and "send the zip" in text
    assert (folder / "README-FIRST.txt").read_text() == text
    stopped = ReadmeFirst.write(folder, None, False, "stopped with Ctrl+C")
    assert "stopped before the end" in stopped and "Ctrl+C" in stopped


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


class PrereqCore:
    def __init__(self, report=None, error=None):
        self.report, self.error = report, error

    def check_account(self, repair):
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
    good = Prerequisites(config, PrereqDesktop(), PrereqCore(seeded), lambda m: None, prereq_commands).run(tmp_path)
    names = {c["name"]: c for c in good["checks"]}
    assert names["Parula installed"]["ok"] and names["Outlook (new) installed"]["ok"]
    assert not names["Outlook (classic) installed"]["ok"]
    assert "Microsoft 365" in names["Outlook (classic) installed"]["fix"]
    assert names["ffmpeg with ddagrab and libx264rgb"]["ok"] and names["Mail account seeded"]["ok"]
    assert good["display"]["ok"] and not good["ok"]

    unseeded = {"ok": False, "before": {"ok": False, "folders": {"Inbox": {"expected": 30000, "actual": 12}}}}
    bad = Prerequisites(config, PrereqDesktop(Rect(0, 0, 1280, 672), 150, on_ac=False, running={"olk.exe"}),
                        PrereqCore(unseeded), lambda m: None, prereq_commands).run(tmp_path)
    names = {c["name"]: c for c in bad["checks"]}
    assert not names["Display"]["ok"] and "100 %" in names["Display"]["fix"]
    assert not names["Power supply"]["ok"] and names["Power supply"]["fatal"]
    assert not names["The test apps are closed"]["ok"] and "olk.exe" in names["The test apps are closed"]["fix"]
    assert not names["Mail account seeded"]["ok"] and "Seeding is done once" in names["Mail account seeded"]["fix"]
    assert "Inbox 12/30000" in names["Mail account seeded"]["detail"]

    unreachable = Prerequisites(config, PrereqDesktop(), PrereqCore(error=OSError("connection refused")),
                                lambda m: None, prereq_commands).run(tmp_path)
    check = next(c for c in unreachable["checks"] if c["name"] == "Mail account reachable")
    assert not check["ok"] and "connection refused" in check["detail"]
