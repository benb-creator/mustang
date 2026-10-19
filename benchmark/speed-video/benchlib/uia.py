import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .settle import Rect


class UiaError(Exception):
    pass


class ControlTypes:
    ids = {
        "Button": 50000, "Calendar": 50001, "CheckBox": 50002, "ComboBox": 50003, "Edit": 50004, "Hyperlink": 50005,
        "Image": 50006, "ListItem": 50007, "List": 50008, "Menu": 50009, "MenuBar": 50010, "MenuItem": 50011,
        "ProgressBar": 50012, "RadioButton": 50013, "ScrollBar": 50014, "Slider": 50015, "Spinner": 50016,
        "StatusBar": 50017, "Tab": 50018, "TabItem": 50019, "Text": 50020, "ToolBar": 50021, "ToolTip": 50022,
        "Tree": 50023, "TreeItem": 50024, "Custom": 50025, "Group": 50026, "Thumb": 50027, "DataGrid": 50028,
        "DataItem": 50029, "Document": 50030, "SplitButton": 50031, "Window": 50032, "Pane": 50033, "Header": 50034,
        "HeaderItem": 50035, "Table": 50036, "TitleBar": 50037, "Separator": 50038, "SemanticZoom": 50039,
        "AppBar": 50040,
    }
    names = {v: k for k, v in ids.items()}

    @classmethod
    def name(cls, type_id) -> str:
        return cls.names.get(type_id, str(type_id))


@dataclass
class ElementInfo:
    """A UI Automation element as read in one cached call; `handle` is the backend's element object."""
    name: str = ""
    automation_id: str = ""
    control_type: str = ""
    class_name: str = ""
    rect: Rect | None = None
    enabled: bool = True
    offscreen: bool = False
    process_id: int = 0
    is_password: bool = False
    focused: bool = False
    toggle_state: int | None = None
    selected: bool | None = None
    value: str | None = None
    size_of_set: int | None = None
    position_in_set: int | None = None
    framework: str = ""
    depth: int = 0
    handle: object = field(default=None, repr=False, compare=False)

    @property
    def center(self) -> tuple[int, int]:
        if self.rect is None:
            raise UiaError(f"Element '{self.name}' ({self.control_type}) has no screen rectangle")
        return self.rect.x + self.rect.width // 2, self.rect.y + self.rect.height // 2

    @property
    def visible(self) -> bool:
        return not self.offscreen and self.rect is not None and self.rect.width > 0 and self.rect.height > 0

    def to_dict(self) -> dict:
        out = {"name": self.name, "control_type": self.control_type, "automation_id": self.automation_id,
               "class_name": self.class_name, "rect": self.rect.to_dict() if self.rect else None,
               "enabled": self.enabled, "offscreen": self.offscreen, "process_id": self.process_id,
               "depth": self.depth}
        for key in ("is_password", "focused", "toggle_state", "selected", "size_of_set", "position_in_set",
                    "framework"):
            value = getattr(self, key)
            if value not in (None, False, ""):
                out[key] = value
        if self.value is not None and not self.is_password:
            out["value"] = self.value
        return out


class ElementQuery:
    """One UI element: control type, automation id, class name, and its name per UI language (regular expressions,
    matched against the whole name, case-insensitively)."""

    def __init__(self, control_type: str | list[str] | None = None, automation_id: str | None = None,
                 names: dict[str, list[str]] | None = None, class_name: str | None = None,
                 password: bool | None = None, visible: bool = True, index: int = 0, contains: bool = False):
        types = [control_type] if isinstance(control_type, str) else list(control_type or [])
        unknown = [t for t in types if t not in ControlTypes.ids]
        if unknown:
            raise UiaError(f"Unknown control type(s) {unknown}")
        self.control_types = types
        self.automation_id = automation_id
        self.names = {lang: [re.compile(p, re.IGNORECASE) for p in patterns] for lang, patterns in (names or {}).items()}
        self.class_name = class_name
        self.password = password
        self.visible = visible
        self.index = index
        self.contains = contains

    @classmethod
    def parse(cls, raw: dict) -> "ElementQuery":
        names = {lang: [value] if isinstance(value, str) else list(value)
                 for lang, value in (raw.get("names") or {}).items()}
        return cls(raw.get("control_type"), raw.get("automation_id"), names, raw.get("class_name"),
                   raw.get("password"), bool(raw.get("visible", True)), int(raw.get("index", 0)),
                   bool(raw.get("contains", False)))

    def name_match(self, name: str, languages: list[str] | None = None) -> tuple[str, re.Match | None] | None:
        """The UI language whose pattern matches the name, with the match; ("any", None) when the query has no
        names."""
        if not self.names:
            return "any", None
        for lang in languages or list(self.names):
            for pattern in self.names.get(lang, []):
                found = pattern.search(name) if self.contains else pattern.fullmatch(name.strip())
                if found:
                    return lang, found
        return None

    def name_language(self, name: str, languages: list[str] | None = None) -> str | None:
        matched = self.name_match(name, languages)
        return matched[0] if matched else None

    def matches(self, info: ElementInfo, languages: list[str] | None = None) -> str | None:
        if self.control_types and info.control_type not in self.control_types:
            return None
        if self.automation_id is not None and not re.fullmatch(self.automation_id, info.automation_id or ""):
            return None
        if self.class_name is not None and not re.fullmatch(self.class_name, info.class_name or ""):
            return None
        if self.password is not None and info.is_password != self.password:
            return None
        if self.visible and not info.visible:
            return None
        return self.name_language(info.name or "", languages)

    def describe(self) -> str:
        parts = []
        if self.control_types:
            parts.append("/".join(self.control_types))
        if self.automation_id:
            parts.append(f"id={self.automation_id}")
        if self.names:
            parts.append("name=" + " | ".join(f"{lang}:{p.pattern}" for lang, ps in self.names.items() for p in ps))
        return " ".join(parts) or "any element"


class UiaBackend:
    """Microsoft UI Automation (UIAutomationCore, the COM API) through comtypes. Every read is one cached call."""

    TreeScope_Element, TreeScope_Children, TreeScope_Descendants = 1, 2, 4
    properties = {
        "name": 30005, "automation_id": 30011, "control_type": 30003, "class_name": 30012, "rect": 30001,
        "enabled": 30010, "offscreen": 30022, "process_id": 30002, "is_password": 30019, "focused": 30008,
        "framework": 30024, "toggle_state": 30086, "selected": 30079, "value": 30045, "size_of_set": 30153,
        "position_in_set": 30152,
    }

    def __init__(self):
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as uia_client
        self.uia = uia_client
        self.automation = comtypes.client.CreateObject(uia_client.CUIAutomation, interface=uia_client.IUIAutomation)
        self.cache = self.automation.CreateCacheRequest()
        for property_id in self.properties.values():
            self.cache.AddProperty(property_id)
        self.true_condition = self.automation.CreateTrueCondition()
        self.walker = self.automation.ControlViewWalker

    def value(self, element, key: str):
        try:
            value = element.GetCachedPropertyValue(self.properties[key])
        except Exception:
            return None
        if isinstance(value, (bool, int, float, str, tuple, list)):
            return value
        return None

    def info(self, element, depth: int = 0) -> ElementInfo:
        rect_value = self.value(element, "rect")
        rect = None
        if isinstance(rect_value, (tuple, list)) and len(rect_value) == 4 and rect_value[2] and rect_value[3]:
            rect = Rect(int(rect_value[0]), int(rect_value[1]), int(rect_value[2]), int(rect_value[3]))
        size = self.value(element, "size_of_set")
        position = self.value(element, "position_in_set")
        toggle = self.value(element, "toggle_state")
        selected = self.value(element, "selected")
        value = self.value(element, "value")
        return ElementInfo(
            name=str(self.value(element, "name") or ""), automation_id=str(self.value(element, "automation_id") or ""),
            control_type=ControlTypes.name(self.value(element, "control_type")),
            class_name=str(self.value(element, "class_name") or ""), rect=rect,
            enabled=bool(self.value(element, "enabled")), offscreen=bool(self.value(element, "offscreen")),
            process_id=int(self.value(element, "process_id") or 0), is_password=bool(self.value(element, "is_password")),
            focused=bool(self.value(element, "focused")), toggle_state=toggle if isinstance(toggle, int) else None,
            selected=selected if isinstance(selected, bool) else None,
            value=value if isinstance(value, str) else None,
            size_of_set=size if isinstance(size, int) and size > 0 else None,
            position_in_set=position if isinstance(position, int) and position > 0 else None,
            framework=str(self.value(element, "framework") or ""), depth=depth, handle=element)

    def root(self) -> ElementInfo:
        return self.info(self.automation.GetRootElementBuildCache(self.cache))

    def from_handle(self, hwnd: int) -> ElementInfo:
        return self.info(self.automation.ElementFromHandleBuildCache(hwnd, self.cache))

    def collect(self, array) -> list[ElementInfo]:
        if not array:
            return []
        return [self.info(array.GetElement(i)) for i in range(array.Length)]

    def children(self, element: ElementInfo) -> list[ElementInfo]:
        return self.collect(element.handle.FindAllBuildCache(self.TreeScope_Children, self.true_condition, self.cache))

    def descendants(self, element: ElementInfo, control_types: list[str] | None = None) -> list[ElementInfo]:
        condition = self.true_condition
        if control_types:
            conditions = [self.automation.CreatePropertyCondition(self.properties["control_type"],
                                                                  ControlTypes.ids[t]) for t in control_types]
            condition = conditions[0]
            for extra in conditions[1:]:
                condition = self.automation.CreateOrCondition(condition, extra)
        return self.collect(element.handle.FindAllBuildCache(self.TreeScope_Descendants, condition, self.cache))

    def refresh(self, element: ElementInfo) -> ElementInfo:
        return self.info(element.handle.BuildUpdatedCache(self.cache), element.depth)

    def walk(self, element: ElementInfo, max_depth: int, max_elements: int) -> list[ElementInfo]:
        out = []

        def visit(handle, depth):
            if len(out) >= max_elements:
                return
            info = self.info(handle, depth)
            out.append(info)
            if depth >= max_depth:
                return
            try:
                child = self.walker.GetFirstChildElementBuildCache(handle, self.cache)
            except Exception:
                child = None
            while child and len(out) < max_elements:
                visit(child, depth + 1)
                try:
                    child = self.walker.GetNextSiblingElementBuildCache(child, self.cache)
                except Exception:
                    child = None

        visit(element.handle, element.depth)
        return out


class UiTree:
    """Finds the elements of one app: all top-level windows of its processes (process ids from a callable, so a
    process tree that grows, like new Outlook's WebView2 children, is followed)."""

    def __init__(self, backend, process_ids, languages: list[str] | None = None):
        self.backend = backend
        self.process_ids = process_ids
        self.languages = list(languages or ["en", "de"])
        self.language: str | None = None

    def windows(self) -> list[ElementInfo]:
        pids = set(self.process_ids())
        return [w for w in self.backend.children(self.backend.root()) if w.process_id in pids]

    def elements(self, control_types: list[str] | None = None) -> list[ElementInfo]:
        found = []
        for window in self.windows():
            if not control_types or window.control_type in control_types:
                found.append(window)
            found += self.backend.descendants(window, control_types)
        return found

    def ordered_languages(self) -> list[str]:
        if self.language:
            return [self.language] + [lang for lang in self.languages if lang != self.language]
        return self.languages

    def find_all(self, query: ElementQuery, elements: list[ElementInfo] | None = None) -> list[ElementInfo]:
        candidates = elements if elements is not None else self.elements(query.control_types or None)
        matched = []
        for info in candidates:
            lang = query.matches(info, self.ordered_languages())
            if lang is None:
                continue
            if lang != "any" and self.language is None:
                self.language = lang
            matched.append(info)
        return matched

    def find(self, query: ElementQuery, elements: list[ElementInfo] | None = None) -> ElementInfo | None:
        matched = self.find_all(query, elements)
        return matched[query.index] if len(matched) > query.index else None

    def wait(self, query: ElementQuery, timeout_s: float, poll_s: float = 0.25,
             enabled: bool = True) -> ElementInfo:
        deadline = time.monotonic() + timeout_s
        last = None
        while True:
            found = self.find(query)
            if found is not None and (found.enabled or not enabled):
                return found
            last = found
            if time.monotonic() >= deadline:
                state = "disabled" if last is not None else "not found"
                raise UiaError(f"Element {query.describe()} {state} within {timeout_s:.0f} s")
            time.sleep(poll_s)

    def dump(self, path: Path, max_depth: int = 40, max_elements: int = 20000, redact=None) -> dict:
        """The UI trees of the app's windows, as JSON (path) and as indented text (path with .txt); `redact`
        replaces secrets in both texts."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        windows = []
        lines = []
        for window in self.windows():
            elements = self.backend.walk(window, max_depth, max_elements)
            windows.append({"window": window.to_dict(), "elements": [e.to_dict() for e in elements]})
            for e in elements:
                rect = f"{e.rect.x},{e.rect.y} {e.rect.width}x{e.rect.height}" if e.rect else "-"
                extra = "".join(f" {k}={v}" for k, v in (("id", e.automation_id), ("class", e.class_name),
                                                          ("toggle", e.toggle_state), ("setsize", e.size_of_set))
                                if v not in (None, ""))
                flags = ("" if e.enabled else " disabled") + (" offscreen" if e.offscreen else "") + \
                    (" focused" if e.focused else "")
                lines.append(f"{'  ' * (e.depth - window.depth)}{e.control_type} \"{e.name}\"{extra} [{rect}]{flags}")
            lines.append("")
        data = {"version": 1, "taken_utc": time.time(), "language": self.language, "windows": windows}
        redact = redact or (lambda text: text)
        path.write_text(redact(json.dumps(data, indent=1, ensure_ascii=False)), encoding="utf-8")
        path.with_suffix(".txt").write_text(redact("\n".join(lines)), encoding="utf-8")
        return data
