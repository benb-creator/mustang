from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ScenarioError(Exception):
    pass


@dataclass
class Action:
    kind: str
    arg: object = None
    options: dict = field(default_factory=dict)

    input_kinds = ("launch", "key", "type", "click", "double_click", "right_click", "scroll", "drag")
    known_kinds = input_kinds + ("close", "sleep", "wait_settled", "wait_window", "focus")

    @property
    def is_input(self) -> bool:
        return self.kind in self.input_kinds

    @property
    def user_action_count(self) -> int:
        if not self.is_input:
            return 0
        return int(self.options.get("repeat", 1)) if self.kind == "key" else 1

    @classmethod
    def parse(cls, raw) -> "Action":
        if isinstance(raw, str):
            kind, arg, options = raw, None, {}
        elif isinstance(raw, dict) and len(raw) >= 1:
            kind = next(iter(raw))
            value = raw[kind]
            options = {k: v for k, v in raw.items() if k != kind}
            if isinstance(value, dict):
                options = {**value, **options}
                arg = options.pop("arg", None)
            else:
                arg = value
        else:
            raise ScenarioError(f"Can't parse action {raw!r}")
        if kind not in cls.known_kinds:
            raise ScenarioError(f"Unknown action '{kind}' in {raw!r}")
        return cls(kind, arg, options)

    def describe(self) -> str:
        if self.kind == "type":
            text = str(self.arg)
            return "type the password" if "password" in text else f"type “{text}”"
        if self.kind == "key":
            repeat = int(self.options.get("repeat", 1))
            return f"key {self.arg}" + (f" ×{repeat}" if repeat > 1 else "")
        if self.kind in ("click", "double_click", "right_click"):
            return f"{self.kind.replace('_', ' ')} {self.arg}"
        if self.kind == "launch":
            return "start the app"
        if self.kind == "scroll":
            return f"scroll {self.arg}"
        if self.kind == "drag":
            return f"drag {self.arg} to {self.options.get('to')}"
        return self.kind


@dataclass
class Step:
    name: str
    actions: list
    measure: bool = True
    settle: dict = field(default_factory=dict)
    expect: str | None = "auto"
    timeout_s: float | None = None

    @property
    def trigger_index(self) -> int:
        for i in range(len(self.actions) - 1, -1, -1):
            if self.actions[i].is_input:
                return i
        raise ScenarioError(f"Step '{self.name}' has no input action that could start its timer")

    @property
    def user_action_count(self) -> int:
        return sum(a.user_action_count for a in self.actions)


@dataclass
class AppScenario:
    app_id: str
    prepare: list
    steps: list
    finish: list
    masks: list
    settle: dict

    @property
    def user_action_count(self) -> int:
        return sum(s.user_action_count for s in self.steps)

    @property
    def action_list(self) -> list[str]:
        return [a.describe() for s in self.steps for a in s.actions if a.is_input]

    @property
    def point_names(self) -> set[str]:
        names = set()
        for action in self.prepare + [a for s in self.steps for a in s.actions] + self.finish:
            points = [action.arg] if action.kind in ("click", "double_click", "right_click", "scroll") else []
            if action.kind == "drag":
                points = [action.arg, action.options.get("to")]
            names.update(p for p in points if isinstance(p, str))
        return names


@dataclass
class Scenario:
    task_id: str
    title: dict
    description: str
    start_state: dict
    apps: dict
    path: Path

    def title_for(self, lang: str) -> str:
        return self.title.get(lang) or self.title.get("en") or self.task_id

    def for_app(self, app_id: str) -> AppScenario:
        if app_id not in self.apps:
            raise ScenarioError(f"Scenario {self.task_id} ({self.path.name}) has no actions for app '{app_id}'")
        return self.apps[app_id]

    @classmethod
    def load(cls, path: Path) -> "Scenario":
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        apps = {}
        for app_id, spec in (raw.get("apps") or {}).items():
            steps = []
            for s in spec.get("steps") or []:
                steps.append(Step(
                    name=s["name"],
                    actions=[Action.parse(a) for a in s.get("actions") or []],
                    measure=bool(s.get("measure", True)),
                    settle=dict(s.get("settle") or {}),
                    expect=s.get("expect", "auto"),
                    timeout_s=s.get("timeout_s"),
                ))
            for step in steps:
                if step.measure:
                    step.trigger_index
            apps[app_id] = AppScenario(
                app_id=app_id,
                prepare=[Action.parse(a) for a in spec.get("prepare") or []],
                steps=steps,
                finish=[Action.parse(a) for a in spec.get("finish") or []],
                masks=list(spec.get("masks") or []),
                settle=dict(spec.get("settle") or {}),
            )
        title = raw.get("title") or {}
        if isinstance(title, str):
            title = {"en": title}
        return cls(str(raw["id"]), title, str(raw.get("description", "")), dict(raw.get("start_state") or {}), apps,
                   Path(path))


class ScenarioLibrary:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self._cache: dict[str, Scenario] = {}

    def get(self, task_id: str) -> Scenario:
        if task_id not in self._cache:
            path = self.directory / f"{task_id}.yaml"
            if not path.exists():
                raise ScenarioError(f"No scenario file {path}")
            self._cache[task_id] = Scenario.load(path)
        return self._cache[task_id]
