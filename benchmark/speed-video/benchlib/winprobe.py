import re
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .probe import AppProbe, Element, ProbeError
from .uia import ElementInfo, ElementQuery, UiTree
from .winnet import ProcessTable


class CountText:
    @staticmethod
    def parse(text: str | None) -> int | None:
        """A count as an app shows it: "30,000", "30.000", "30 000" (also with no-break spaces)."""
        if text is None:
            return None
        digits = re.sub(r"[\s.,  ']", "", text)
        return int(digits) if digits.isdigit() else None


class UiaAppMap:
    """One app's section of windows/uia-elements.yaml: element queries, the pages they identify, and how to check
    the Inbox listing."""

    def __init__(self, kind: str, raw: dict):
        self.kind = kind
        self.process_names = [n.lower() for n in raw.get("process_names") or []]
        self.elements = {name: ElementQuery.parse(spec) for name, spec in (raw.get("elements") or {}).items()}
        self.near = {name: spec["near"] for name, spec in (raw.get("elements") or {}).items() if spec.get("near")}
        self.sources = {name: spec.get("source", "assumed") for name, spec in (raw.get("elements") or {}).items()}
        self.pages = {name: list(required) for name, required in (raw.get("pages") or {}).items()}
        self.inbox_listed = dict(raw.get("inbox_listed") or {})
        self.server_fields = list(raw.get("server_fields") or [])
        self.verify = dict(raw.get("verify") or {})
        self.interruptions = {}
        for name, spec in (raw.get("interruptions") or {}).items():
            self.interruptions[name] = {"require": [ElementQuery.parse(q) for q in spec.get("require") or []],
                                        "click": spec.get("click")}
        for page, required in self.pages.items():
            missing = [e for e in required if e not in self.elements]
            if missing:
                raise ProbeError(f"{kind}: page '{page}' names unknown elements {missing}")
        missing = [e for e in self.server_fields if e not in self.elements]
        if missing:
            raise ProbeError(f"{kind}: server_fields names unknown elements {missing}")

    @classmethod
    def load(cls, path: Path, kind: str) -> "UiaAppMap":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if kind not in data:
            raise ProbeError(f"{path} has no section '{kind}'")
        return cls(kind, data[kind])

    def query(self, element: str) -> ElementQuery:
        if element not in self.elements:
            raise ProbeError(f"{self.kind}: no element '{element}' in the UI Automation map")
        return self.elements[element]


class UiaProbe(AppProbe):
    """The Windows implementation of the shared `AppProbe` interface (benchlib/probe.py): finds an app's elements
    with UI Automation, tells which page is shown, checks the Inbox listing, verifies after the measured end.
    `inputs` (set by the driver for the check after the measured end) sends and logs its inputs: `click(x, y)`,
    `key(combo)`. `values` fills an element's `near` (e.g. the test account's row)."""

    method = "uia"

    def __init__(self, app_map: UiaAppMap, backend_factory=None, process_table=None, tree_factory=UiTree,
                 sleep=time.sleep, clock=time.monotonic):
        self.map = app_map
        self.backend_factory = backend_factory
        self.process_table = process_table or ProcessTable()
        self.tree_factory = tree_factory
        self.sleep = sleep
        self.clock = clock
        self.app = None
        self.tree: UiTree | None = None
        self.inputs = None
        self.values: dict[str, str] = {}
        self.cached: dict[str, ElementInfo] = {}

    def process_ids(self) -> set[int]:
        roots = {self.app.process.pid} if self.app is not None and self.app.process is not None else set()
        return set(ProcessTable.tree(self.process_table.snapshot(), roots, set(self.map.process_names)))

    def attach(self, app, timeout_s: float = 120):
        self.app = app
        if self.tree is None:
            if self.backend_factory is None:
                from .uia import UiaBackend
                self.backend_factory = UiaBackend
            self.tree = self.tree_factory(self.backend_factory(), self.process_ids)
        deadline = self.clock() + timeout_s
        while not self.tree.windows():
            if self.clock() > deadline:
                raise ProbeError(f"{self.map.kind}: no window of {', '.join(self.map.process_names)} in the UI "
                                 f"Automation tree within {timeout_s:.0f} s")
            self.sleep(0.5)

    @property
    def language(self) -> str | None:
        return self.tree.language if self.tree else None

    def snapshot(self) -> list[ElementInfo]:
        return self.tree.elements()

    def element(self, element: str, timeout_s: float = 10, elements: list[ElementInfo] | None = None,
                enabled: bool = True) -> ElementInfo | None:
        query = self.map.query(element)
        near = self.map.near.get(element)
        deadline = self.clock() + timeout_s
        while True:
            if near and self.values.get(near):
                found = self.nearest(query, self.values[near], elements)
            else:
                found = self.tree.find(query, elements)
            if found is not None and (found.enabled or not enabled):
                return found
            if elements is not None or self.clock() >= deadline:
                return None
            self.sleep(0.25)

    def nearest(self, query: ElementQuery, text: str, elements: list[ElementInfo] | None) -> ElementInfo | None:
        """Of the elements the query matches, the one in the same row as the visible element that names `text`."""
        elements = self.snapshot() if elements is None else elements
        anchor = next((e for e in elements if text.lower() in (e.name or "").lower() and e.visible), None)
        matched = self.tree.find_all(query, elements)
        if anchor is None or not matched:
            return None
        return min(matched, key=lambda e: abs(e.center[1] - anchor.center[1]))

    @staticmethod
    def as_element(info: ElementInfo) -> Element:
        rect = info.rect
        return Element(x=rect.x, y=rect.y, w=rect.width, h=rect.height, enabled=info.enabled, text=info.name,
                       value=None if info.is_password else info.value, focused=info.focused,
                       checked=None if info.toggle_state is None else info.toggle_state == 1)

    def find(self, name: str) -> Element | None:
        found = self.element(name, timeout_s=0, enabled=False)
        return self.as_element(found) if found is not None and found.rect is not None else None

    def focused(self, name: str) -> bool:
        found = self.find(name)
        return bool(found and found.get("focused"))

    def page(self, elements: list[ElementInfo] | None = None) -> str:
        elements = self.snapshot() if elements is None else elements
        for page, required in self.map.pages.items():
            if all(self.tree.find(self.map.query(e), elements) is not None for e in required):
                return page
        return "unknown"

    def wait_page(self, pages: set[str] | None, timeout_s: float = 60, on_interruption=None,
                  poll_s: float = 0.5) -> str:
        """Waits until one of the pages is shown (any known page when None); a first-run dialog of the map's
        `interruptions` is handed to `on_interruption(element)`, which clicks it."""
        deadline = self.clock() + timeout_s
        while True:
            elements = self.snapshot()
            page = self.page(elements)
            if page != "unknown" and (pages is None or page in pages):
                return page
            dismiss = self.interruption(elements) if on_interruption is not None else None
            if dismiss:
                on_interruption(dismiss)
                continue
            if self.clock() >= deadline:
                raise ProbeError(f"Expected one of the pages {sorted(pages or [])} within {timeout_s:.0f} s, but "
                                 f"{self.map.kind} shows '{page}'")
            self.sleep(poll_s)

    def interruption(self, elements: list[ElementInfo] | None = None) -> str | None:
        elements = self.snapshot() if elements is None else elements
        for spec in self.map.interruptions.values():
            if spec["click"] and all(self.tree.find(q, elements) is not None for q in spec["require"]) and \
                    self.tree.find(self.map.query(spec["click"]), elements) is not None:
                return spec["click"]
        return None

    def page_text(self) -> str:
        return " | ".join(e.name for e in self.snapshot() if e.name and e.visible)[:4000]

    def found_hosts(self) -> list[str]:
        """The host names in the map's `server_fields` as shown; empty when one of them isn't shown or is empty."""
        hosts = []
        for name in self.map.server_fields:
            found = self.find(name)
            host = re.sub(r"\s+", "", (found or {}).get("value") or "").lower()
            if not host:
                return []
            hosts.append(host)
        return hosts

    def cached_element(self, element: str) -> ElementInfo | None:
        """A probe element read again cheaply (one element) after the first search, which reads many."""
        query = self.map.query(element)
        known = self.cached.get(element)
        if known is not None:
            try:
                fresh = self.tree.backend.refresh(known)
                if query.matches(fresh, self.tree.ordered_languages()):
                    return fresh
            except Exception:
                pass
        found = self.tree.find(query)
        if found is not None:
            self.cached[element] = found
        return found

    def count_of(self, element: str) -> tuple[int | None, str | None]:
        found = self.cached_element(element)
        if found is None:
            return None, None
        matched = self.map.query(element).name_match(found.name, self.tree.ordered_languages())
        if matched and matched[1] is not None and matched[1].groups():
            return CountText.parse(matched[1].group(1)), found.name
        first = re.search(r"\d[\d.,\u00a0\u202f']*", found.name)
        return CountText.parse(first.group(0) if first else None), found.name

    def inbox_listed(self, expected: dict) -> dict:
        strategy = self.map.inbox_listed
        expected_count = expected.get("inbox_messages")
        result = {"complete": False, "listed": None, "expected": expected_count, "method": "uia"}
        if strategy.get("count"):
            listed, text = self.count_of(strategy["count"])
            result.update(listed=listed, count_text=text)
        if strategy.get("idle"):
            result["idle"] = self.cached_element(strategy["idle"]) is not None
        if strategy.get("set_size"):
            items = self.tree.find_all(self.map.query(strategy["set_size"]))
            sizes = [i.size_of_set for i in items if i.size_of_set]
            if sizes:
                result.update(listed=max(sizes), listed_from="size_of_set")
        if strategy.get("unread"):
            unread, text = self.count_of(strategy["unread"])
            result.update(unread=unread, unread_text=text, expected_unread=expected.get("inbox_unread"))
        if result["listed"] is not None and expected_count is not None:
            result["complete"] = result["listed"] >= expected_count
        elif result.get("unread") is not None and expected.get("inbox_unread") is not None:
            result["complete"] = result["unread"] >= expected["inbox_unread"]
        return result

    def subject_element(self, subject: str | None) -> ElementInfo | None:
        if not subject:
            return None
        needle = subject[:40].lower()
        for info in self.tree.elements():
            if needle in (info.name or "").lower() and info.visible:
                return info
        return None

    def verify(self, expected: dict) -> dict:
        """After the measured end (not timed, not user actions): select the newest message, jump to the end of the
        list, and look for the corpus's oldest subject; a lazily loading list gets the end key again every
        `repeat_s` while it grows."""
        spec = self.map.verify
        keys = list(spec.get("keys") or ["End"])
        within_s = float(spec.get("within_s", 15))
        repeat_s = float(spec.get("repeat_s", 0) or 0)
        newest = self.subject_element(expected.get("inbox_newest_subject"))
        started = self.clock()
        if newest is not None and self.inputs is not None:
            self.inputs.click(*newest.center)
            self.sleep(0.5)
        for key in keys:
            if self.inputs is not None:
                self.inputs.key(key)
        oldest = None
        last_key = self.clock()
        while self.clock() - started < within_s:
            oldest = self.subject_element(expected.get("inbox_oldest_subject"))
            if oldest is not None:
                break
            if repeat_s and self.clock() - last_key >= repeat_s and self.inputs is not None:
                self.inputs.key(keys[-1])
                last_key = self.clock()
            self.sleep(0.5)
        listed = self.inbox_listed(expected)
        if listed["listed"] is not None:
            count_ok, basis = listed["listed"] == expected.get("inbox_messages"), "count"
        elif listed.get("unread") is not None:
            count_ok, basis = bool(listed["complete"]), "unread count"
        else:
            count_ok, basis = True, "oldest message only"
        def screen_rect(name: str | None) -> dict | None:
            found = self.cached_element(name) if name else None
            r = found.rect if found is not None else None
            return {"x": r.x, "y": r.y, "w": r.width, "h": r.height} if r else None

        return {"version": 1, "method": "uia", "inbox_complete": oldest is not None and count_ok, "basis": basis,
                "listed": listed["listed"], "listed_text": listed.get("count_text") or listed.get("unread_text"),
                "expected": expected.get("inbox_messages"),
                "oldest_subject": expected.get("inbox_oldest_subject"), "oldest_visible": oldest is not None,
                "newest_subject": expected.get("inbox_newest_subject"), "newest_visible": newest is not None,
                "list_rect": screen_rect(self.map.inbox_listed.get("list")),
                "count_rect": screen_rect(self.map.inbox_listed.get("count") or self.map.inbox_listed.get("unread")),
                "checked_utc": datetime.now(timezone.utc).isoformat(),
                "details": {"listed": listed, "seconds": round(self.clock() - started, 2), "keys": keys,
                            "language": self.language}}

    def dump(self, path: Path) -> None:
        if self.tree is None:
            Path(path).write_text("not attached to the app yet\n")
            return
        self.tree.dump(path, redact=self.redact)

    def close(self):
        self.cached.clear()
        self.app = None
