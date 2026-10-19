"""App instrumentation: finds UI elements on screen and checks completeness after the measured end. Never a
timing source: the live gate asks `inbox_listed()` only while the screen is quiet, and the measured end is always
the last screen change in the recording (README, "Instrumentation")."""

import json
import re
import time
from pathlib import Path

from .cdp import CdpClient, CdpError
from .marionette import MarionetteClient, MarionetteError


class ProbeError(Exception):
    pass


class Element(dict):
    """Screen rectangle (x, y, w, h in screen pixels) of a UI element, plus `enabled` and `text`."""

    @property
    def center(self) -> tuple[int, int]:
        return int(self["x"] + self["w"] / 2), int(self["y"] + self["h"] / 2)


class AppProbe:
    method = "none"

    def attach(self, app, timeout_s: float = 60):
        pass

    def find(self, name: str) -> Element | None:
        raise ProbeError(f"{type(self).__name__} doesn't know element '{name}'")

    def wait_for(self, name: str, timeout_s: float = 30, enabled: bool = True) -> Element:
        deadline = time.monotonic() + timeout_s
        while True:
            element = self.find(name)
            if element is not None and (element.get("enabled", True) or not enabled):
                return element
            if time.monotonic() > deadline:
                raise ProbeError(f"Element '{name}' not found within {timeout_s:.0f} s (page: {self.page()})")
            time.sleep(0.1)

    def page(self) -> str:
        return "unknown"

    def wait_page(self, pages: set[str], timeout_s: float = 60) -> str:
        deadline = time.monotonic() + timeout_s
        while True:
            page = self.page()
            if page in pages:
                return page
            if time.monotonic() > deadline:
                raise ProbeError(f"Expected page {sorted(pages)} within {timeout_s:.0f} s, but it shows '{page}': "
                                 f"{self.page_text()[:300]}")
            time.sleep(0.1)

    def page_text(self) -> str:
        return ""

    def inbox_listed(self, expected: dict) -> dict:
        return {"complete": True, "listed": None}

    def verify(self, expected: dict) -> dict:
        return {"method": self.method, "inbox_complete": None}

    def prepare(self, server) -> list[str]:
        return []

    def dump(self, path: Path):
        pass

    def close(self):
        pass

    @staticmethod
    def count_in(text: str | None) -> int | None:
        if not text:
            return None
        match = re.search(r"\d[\d,.  ']*", text)
        return int(re.sub(r"\D", "", match.group(0))) if match else None

    @staticmethod
    def same_subject(a: str | None, b: str | None) -> bool:
        def norm(s):
            return re.sub(r"\s+", " ", s or "").strip().casefold()
        return bool(a) and norm(a) == norm(b)


class ParulaProbe(AppProbe):
    """Parula (Electron) through the Chrome DevTools Protocol of its renderer (`--remote-debugging-port`)."""

    method = "cdp"

    def __init__(self, port: int):
        self.port = port
        self.client: CdpClient | None = None
        self.values = {}

    def attach(self, app, timeout_s: float = 60):
        self.client = CdpClient.connect(self.port, timeout_s, "index.html")

    def evaluate(self, expression: str):
        if self.client is None:
            raise ProbeError("Parula's DevTools aren't attached")
        try:
            return self.client.evaluate(expression)
        except CdpError as ex:
            raise ProbeError(str(ex)) from ex

    def find(self, name: str) -> Element | None:
        find_script = r"""
    (spec, values) => {
      const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.visibility != 'hidden' && s.display != 'none'; };
      let found = [...document.querySelectorAll(spec.css)].filter(visible);
      const text = el => (el.innerText || el.value || el.getAttribute('title') || '').trim();
      if (spec.text) found = found.filter(el => spec.text.includes(text(el)));
      if (spec.text_contains) { const needle = spec.text_contains.replace('{protocol}', values.protocol || '').toLowerCase();
        found = found.filter(el => text(el).toLowerCase().includes(needle)); }
      if (!found.length) return null;
      const el = found[spec.index === undefined ? 0 : (spec.index < 0 ? found.length + spec.index : spec.index)];
      if (!el) return null;
      const r = el.getBoundingClientRect();
      const box = el.matches('input') ? el : el.querySelector('input[type=radio], input[type=checkbox]');
      const d = window.devicePixelRatio || 1;
      return {x: (window.screenX + r.x) * d, y: (window.screenY + r.y) * d, w: r.width * d, h: r.height * d,
              enabled: !el.disabled && !el.classList.contains('disabled'), text: text(el).slice(0, 200),
              value: el.value === undefined ? null : (el.type == 'password' ? null : el.value),
              checked: box && (box.type == 'radio' || box.type == 'checkbox') ? box.checked : null};
    }"""
        elements = {
            "setup.add_email": {"css": "button", "text": ["Add email address", "E-Mail-Adresse hinzufügen"]},
            "setup.pause_video": {"css": "button.pause"},
            "setup.email": {"css": "input[type=email]"},
            "setup.password": {"css": ".page-box input[type=password]"},
            "setup.next": {"css": ".page-box button.filled.large"},
            "setup.manual": {"css": ".page-box button.secondary", "text": ["Manual setup", "Manuelle Einrichtung"]},
            "found.option": {"css": ".page-box .alt label.protocol", "text_contains": "{protocol}"},
            "manual.protocol": {"css": "select.protocol"},
            "manual.url": {"css": ".page-box input[type=url]"},
            "manual.incoming_host": {"css": ".manual-config input[type=text]", "index": 0},
            "manual.outgoing_host": {"css": ".manual-config input[type=text]", "index": -1},
            "manual.incoming_port": {"css": ".manual-config input[type=number]", "index": 0},
            "manual.outgoing_port": {"css": ".manual-config input[type=number]", "index": 1},
            "mail.list": {"css": ".message-list .fast-list"},
        }
        spec = elements.get(name)
        if spec is None:
            return super().find(name)
        found = self.evaluate(f"({find_script})({json.dumps(spec)}, {json.dumps(self.values)})")
        return Element(found) if found else None

    def state(self) -> dict:
        state_script = r"""
    (() => {
      const box = document.querySelector('.page-box');
      const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      const headings = [...document.querySelectorAll('h1, h2')].filter(visible).map(e => e.innerText.trim());
      const error = [...document.querySelectorAll('.page-box .error')].filter(visible).map(e => e.innerText.trim()).join(' ');
      return {hash: location.hash, headings, text: box ? box.innerText.slice(0, 3000) : document.body.innerText.slice(0, 1000),
              error: error || null, radios: box ? box.querySelectorAll('input[type=radio]').length : 0,
              expanded: !!(box && box.querySelector('.manual-config input[type=password]')),
              counts: [...document.querySelectorAll('.msg-count')].filter(visible).map(e => e.innerText.trim())};
    })()"""
        return self.evaluate(state_script)

    def page(self) -> str:
        """The page shown; "error:<page>" while the setup shows an error message."""
        state = self.state()
        page = self.base_page(state)
        return f"error:{page}" if state.get("error") and page not in ("mail", "initial") else page

    @staticmethod
    def base_page(state: dict) -> str:
        hash_, text = state["hash"], state["text"]
        if "/setup/initial" in hash_:
            return "initial"
        if hash_.startswith("#/mail"):
            return "mail"
        if "Verifying that the configuration works" in text:
            return "checking"
        if "We are looking for the configuration" in text:
            return "finding"
        if "is working and ready" in text:
            return "finalize"
        if "Manual configuration" in state["headings"]:
            return "manual-full" if state["expanded"] else "manual"
        if state["radios"] or re.search(r"We (found|received|guessed) (a|the) configuration", text):
            return "found"
        if "/setup/mail" in hash_:
            return "email"
        return f"unknown:{hash_}"

    def page_text(self) -> str:
        state = self.state()
        return f"{state['hash']} {state.get('error') or ''} {state['text']}"

    def error_text(self) -> str | None:
        return self.state().get("error")

    def inbox_listed(self, expected: dict) -> dict:
        state = self.state()
        counts = [self.count_in(c) for c in state["counts"]]
        listed = counts[0] if counts else None
        return {"complete": state["hash"].startswith("#/mail") and listed == expected["inbox_messages"],
                "listed": listed, "text": state["counts"][0] if state["counts"] else None}

    def scroll(self, where: str):
        self.evaluate("(() => { const l = document.querySelector('.message-list .fast-list'); "
                      f"l.scrollTop = {'l.scrollHeight' if where == 'end' else '0'}; return l.scrollTop; }})()")

    def visible_rows(self, settle_s: float = 1.5) -> dict:
        rows_script = r"""
    (() => {
      const list = document.querySelector('.message-list .fast-list');
      if (!list) return null;
      const box = list.getBoundingClientRect();
      const rows = [...list.querySelectorAll('.row')].map(row => { const subject = row.querySelector('.subject');
        const r = (row.querySelector('.message') || subject || row).getBoundingClientRect();
        return {top: r.top, bottom: r.bottom, subject: subject ? subject.innerText.trim() : null}; })
        .filter(r => r.subject !== null && r.bottom > box.top + 1 && r.top < box.bottom - 1)
        .sort((a, b) => a.top - b.top);
      const d = window.devicePixelRatio || 1;
      const screen = r => ({x: (window.screenX + r.x) * d, y: (window.screenY + r.y) * d, w: r.width * d, h: r.height * d});
      const count = [...document.querySelectorAll('.msg-count')].find(e => e.getBoundingClientRect().width > 0);
      const c = count ? count.getBoundingClientRect() : null;
      return {rows, scrollTop: list.scrollTop, scrollHeight: list.scrollHeight, clientHeight: list.clientHeight,
              rect: screen(box), count_rect: c ? screen(c) : null};
    })()"""
        deadline = time.monotonic() + settle_s
        rows = self.evaluate(rows_script)
        while time.monotonic() < deadline:
            time.sleep(0.25)
            again = self.evaluate(rows_script)
            if again == rows:
                break
            rows = again
        return rows or {"rows": []}

    def verify(self, expected: dict) -> dict:
        listed = self.inbox_listed(expected)
        top = self.visible_rows()
        self.scroll("end")
        bottom = self.visible_rows(3.0)
        self.scroll("top")
        self.visible_rows()
        oldest = expected.get("inbox_oldest_subject")
        newest = expected.get("inbox_newest_subject")
        oldest_visible = any(self.same_subject(r["subject"], oldest) for r in bottom.get("rows", [])[-3:])
        newest_visible = any(self.same_subject(r["subject"], newest) for r in top.get("rows", [])[:3])
        return {"version": 1, "method": self.method, "listed": listed["listed"], "listed_text": listed.get("text"),
                "expected": expected["inbox_messages"], "oldest_subject": oldest, "oldest_visible": oldest_visible,
                "newest_subject": newest, "newest_visible": newest_visible,
                "inbox_complete": listed["complete"] and oldest_visible,
                "list_rect": top.get("rect"), "count_rect": top.get("count_rect"), "checked_utc": time.time(),
                "details": {"top_rows": [r["subject"] for r in top.get("rows", [])[:5]],
                            "bottom_rows": [r["subject"] for r in bottom.get("rows", [])[-5:]],
                            "scroll_height": bottom.get("scrollHeight"),
                            "how": "DevTools: read the folder's message count, scroll the list to its end and back"}}

    def dump(self, path: Path):
        try:
            Path(path).write_text(json.dumps({"state": self.state(), "page": self.page()}, indent=2,
                                             ensure_ascii=False))
        except ProbeError as ex:
            Path(path).write_text(f"dump failed: {ex}")

    def close(self):
        if self.client:
            self.client.close()
            self.client = None


class ThunderbirdProbe(AppProbe):
    """Thunderbird through Marionette in the chrome context of its main window."""

    method = "marionette"

    helpers = r"""
const deep = (root, out = []) => { for (const el of root.querySelectorAll('*')) { out.push(el);
  if (el.shadowRoot) deep(el.shadowRoot, out); } return out; };
const shown = el => { if (!el.checkVisibility || !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}))
  return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
const screenRect = (el, offset) => { const r = el.getBoundingClientRect();
  return {x: window.mozInnerScreenX + (offset ? offset.x : 0) + r.x, y: window.mozInnerScreenY + (offset ? offset.y : 0) + r.y,
          w: r.width, h: r.height}; };
const hub = () => document.querySelector('account-hub-container');
const tabmail = document.getElementById('tabmail');
const pane = () => tabmail && tabmail.currentAbout3Pane;
"""

    def __init__(self, port: int):
        self.port = port
        self.client: MarionetteClient | None = None

    def attach(self, app, timeout_s: float = 60):
        self.client = MarionetteClient.connect(self.port, timeout_s)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            handles = self.client.command("WebDriver:GetWindowHandles")
            for handle in handles if isinstance(handles, list) else handles.get("value", []):
                self.client.command("WebDriver:SwitchToWindow", {"handle": handle})
                if "messenger.xhtml" in self.execute("return document.location.href;"):
                    return
            time.sleep(0.5)
        raise ProbeError("Thunderbird's main window didn't open")

    def execute(self, script: str, args: list | None = None):
        if self.client is None:
            raise ProbeError("Thunderbird's Marionette isn't attached")
        try:
            return self.client.execute(script, args)
        except MarionetteError as ex:
            raise ProbeError(str(ex)) from ex

    def find(self, name: str) -> Element | None:
        find_script = self.helpers + r"""
    const name = arguments[0];
    const ids = {'hub.realName': 'realName', 'hub.email': 'email', 'hub.forward': 'forward', 'hub.back': 'back',
      'hub.manual': 'manualConfiguration', 'hub.password': 'password', 'hub.custom': 'custom',
      'manual.incoming_host': 'manualIncomingHostnameInput', 'manual.incoming_port': 'manualIncomingPortInput',
      'manual.outgoing_host': 'manualOutgoingHostnameInput', 'manual.outgoing_port': 'manualOutgoingPortInput'};
    if (name in ids) {
      const h = hub(); if (!h) return null;
      const el = deep(h.shadowRoot || h).concat(deep(h)).find(e => e.id == ids[name] && shown(e));
      if (!el) return null;
      const r = screenRect(el);
      const c = {x: r.x + r.w / 2 - window.mozInnerScreenX, y: r.y + r.h / 2 - window.mozInnerScreenY};
      let top = document.elementFromPoint(c.x, c.y);
      while (top && top.shadowRoot && top.shadowRoot.elementFromPoint(c.x, c.y) && top.shadowRoot.elementFromPoint(c.x, c.y) != top)
        top = top.shadowRoot.elementFromPoint(c.x, c.y);
      return {...r, enabled: !el.disabled, text: (el.textContent || el.value || '').trim().slice(0, 200),
              value: el.value === undefined || el.type == 'password' ? null : String(el.value),
              hit: !!top && (top == el || el.contains(top) || top.contains(el))};
    }
    if (name == 'folder.inbox') {
      const w = pane(); if (!w) return null;
      const offset = tabmail.currentTabInfo.chromeBrowser.getBoundingClientRect();
      const row = [...w.document.querySelectorAll('#folderTree li')].find(li => li.uri && /^imap:.*\/INBOX$/.test(li.uri));
      if (!row) return null;
      const el = row.querySelector('.container') || row;
      return {...screenRect(el, offset), enabled: true, text: row.uri};
    }
    if (name == 'mail.count') {
      const w = pane(); if (!w) return null;
      const offset = tabmail.currentTabInfo.chromeBrowser.getBoundingClientRect();
      const label = w.document.getElementById('threadPaneFolderCount');
      return label && shown(label) ? {...screenRect(label, offset), enabled: true, text: label.textContent.trim()} : null;
    }
    if (name == 'mail.list') {
      const w = pane(); if (!w) return null;
      const offset = tabmail.currentTabInfo.chromeBrowser.getBoundingClientRect();
      const tree = w.document.getElementById('threadTree');
      return tree && shown(tree) ? {...screenRect(tree, offset), enabled: true, text: ''} : null;
    }
    return null;"""
        found = self.execute(find_script, [name])
        return Element(found) if found else None

    def state(self) -> dict:
        state_script = self.helpers + r"""
    const h = hub();
    let view = null, notification = null;
    if (h) {
      const inside = deep(h.shadowRoot || h).concat(deep(h));
      const forms = inside.filter(e => e.localName && e.localName.startsWith('email-') && shown(e));
      if (forms.length) {
        view = forms[forms.length - 1].localName;
        const summary = inside.find(e => e.id == 'emailFormNotificationSummary' && shown(e));
        notification = summary ? summary.textContent.trim().replace(/\s+/g, ' ') : null;
      }
    }
    const w = pane();
    let folder = null, count = null, total = null;
    if (w && w.gFolder) {
      folder = w.gFolder.URI;
      total = w.gFolder.getTotalMessages(false);
      const label = w.document.getElementById('threadPaneFolderCount');
      count = label && !label.hidden ? label.textContent.trim() : null;
    }
    let notificationType = null;
    if (h) {
      const box = deep(h.shadowRoot || h).concat(deep(h)).find(e => e.id == 'emailFormNotification' && shown(e));
      if (box) notificationType = ['error', 'warning', 'success', 'info'].find(c => box.classList.contains(c)) || null;
    }
    let focused = document.activeElement;
    while (focused && focused.shadowRoot && focused.shadowRoot.activeElement) focused = focused.shadowRoot.activeElement;
    return {view, notification, notificationType, folder, count, total,
            focused: focused ? focused.id || focused.localName : null,
            tabs: tabmail ? tabmail.tabInfo.map(t => t.mode.name) : []};"""
        return self.execute(state_script)

    def page(self) -> str:
        """The Account Hub's view ("busy:<view>" while it works, "error:<view>" with an error notification,
        "manual:<type>" for the manual form with a notification), else "mail" or "inbox"."""
        state = self.state()
        view = state["view"]
        note = (state.get("notification") or "").lower()
        if view:
            if any(word in note for word in ("looking up", "re-testing", "creating account", "discovering")):
                return f"busy:{view}"
            page = {"email-auto-form": "email", "email-protocol-select-form": "protocol-select",
                    "email-manual-config-form": "manual", "email-config-found": "found",
                    "email-password-form": "password", "email-sync-accounts-form": "sync",
                    "email-added-success": "success"}.get(view, view)
            kind = state.get("notificationType")
            if kind == "error":
                return f"error:{page}"
            return f"{page}:{kind}" if kind and page == "manual" else page
        if state.get("folder"):
            return "inbox" if state["folder"].endswith("/INBOX") else "mail"
        return "mail" if "mail3PaneTab" in state.get("tabs", []) else "unknown"

    def page_text(self) -> str:
        state = self.state()
        return f"{state.get('view')}: {state.get('notification')} (folder {state.get('folder')})"

    def notification(self) -> str | None:
        return self.state().get("notification")

    def focused(self, name: str) -> bool:
        element_ids = {"manual.incoming_host": "manualIncomingHostnameInput", "manual.incoming_port": "manualIncomingPortInput",
                       "manual.outgoing_host": "manualOutgoingHostnameInput", "manual.outgoing_port": "manualOutgoingPortInput"}
        return self.state().get("focused") == element_ids.get(name, name)

    def inbox_listed(self, expected: dict) -> dict:
        state = self.state()
        listed = self.count_in(state.get("count"))
        return {"complete": (state.get("folder") or "").endswith("/INBOX") and listed == expected["inbox_messages"]
                and state.get("total") == expected["inbox_messages"],
                "listed": listed, "text": state.get("count"), "folder_total": state.get("total")}

    def verify(self, expected: dict) -> dict:
        row_script = self.helpers + r"""
    const w = pane();
    const index = arguments[0];
    const row = w.threadTree.getRowAtIndex(index);
    if (!row) return null;
    const offset = tabmail.currentTabInfo.chromeBrowser.getBoundingClientRect();
    const cell = row.querySelector('.subjectcol-column, .thread-card-subject-container .subject, .subject');
    const r = screenRect(row, offset);
    const tree = screenRect(w.threadTree, offset);
    const middle = r.y + r.h / 2;
    return {subject: (cell || row).textContent.replace(/\s+/g, ' ').trim(), row_text: row.textContent.replace(/\s+/g, ' ').trim(),
            visible: middle >= tree.y && middle <= tree.y + tree.h};"""
        reach_script = self.helpers + r"""
    const w = pane();
    const id = arguments[0];
    const hdr = w.gFolder.msgDatabase.getMsgHdrForMessageID(id);
    if (!hdr) return {found: false};
    const index = w.gDBView.findIndexOfMsgHdr(hdr, true);
    if (index < 0) return {found: true, index};
    w.threadTree.scrollToIndex(index, true);
    return {found: true, index, rows: w.gDBView.rowCount};"""
        listed = self.inbox_listed(expected)
        rect = self.find("mail.list")
        count = self.find("mail.count")
        result = {}
        for which in ("oldest", "newest"):
            message_id = (expected.get(f"inbox_{which}_message_id") or "").strip("<>")
            subject = expected.get(f"inbox_{which}_subject")
            reach = self.execute(reach_script, [message_id]) if message_id else {"found": False}
            row = None
            if reach.get("found") and reach.get("index", -1) >= 0:
                time.sleep(1.0)
                row = self.execute(row_script, [reach["index"]])
            shown = " ".join(str((row or {}).get(k) or "") for k in ("subject", "row_text"))
            result[which] = {"reach": reach, "row": row,
                             "visible": bool(row and row.get("visible") and subject and
                                             " ".join(subject.split()).casefold() in shown.casefold())}
        return {"version": 1, "method": self.method, "listed": listed["listed"], "listed_text": listed.get("text"),
                "expected": expected["inbox_messages"], "oldest_subject": expected.get("inbox_oldest_subject"),
                "oldest_visible": result["oldest"]["visible"], "newest_subject": expected.get("inbox_newest_subject"),
                "newest_visible": result["newest"]["visible"],
                "inbox_complete": listed["complete"] and result["oldest"]["visible"],
                "list_rect": dict(rect) if rect else None, "count_rect": dict(count) if count else None,
                "checked_utc": time.time(),
                "details": {**result, "folder_total": listed.get("folder_total"),
                            "how": "Marionette: read the thread pane's message count, find the message by its "
                                   "Message-ID in the list (expanding its thread) and scroll to it"}}

    def prepare(self, server) -> list[str]:
        if not getattr(server, "ca_file", None):
            return []
        lines = [line for line in Path(server.ca_file).read_text().splitlines() if line and "-----" not in line]
        subject = self.execute("""
const db = Cc["@mozilla.org/security/x509certdb;1"].getService(Ci.nsIX509CertDB);
return db.addCertFromBase64(arguments[0], "C,C,C").subjectName;""", ["".join(lines)])
        return [f"trusted the local test server's CA ({subject}) in the Thunderbird profile"]

    def dump(self, path: Path):
        try:
            Path(path).write_text(json.dumps({"state": self.state(), "page": self.page()}, indent=2,
                                             ensure_ascii=False))
        except ProbeError as ex:
            Path(path).write_text(f"dump failed: {ex}")

    def close(self):
        if self.client:
            self.client.close()
            self.client = None


class Probes:
    @staticmethod
    def create(spec: dict | None) -> AppProbe:
        spec = dict(spec or {})
        kind = spec.get("type", "none")
        if kind == "cdp":
            return ParulaProbe(int(spec.get("port", 29222)))
        if kind == "marionette":
            return ThunderbirdProbe(int(spec.get("port", 28828)))
        if kind == "none":
            return AppProbe()
        raise ProbeError(f"Unknown probe type '{kind}'")
