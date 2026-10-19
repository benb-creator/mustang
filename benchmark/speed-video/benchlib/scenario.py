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
    known_kinds = input_kinds + ("close", "sleep", "wait_settled", "wait_window", "focus", "wait_cloud_quiet")

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
            if "password" in text:
                return "type the password"
            names = {"${account.email}": "the e-mail address", "${account.name}": "the name",
                     "${account.username}": "the user name", "${server.jmap_url}": "the server's JMAP URL",
                     "${server.imap_host}": "the IMAP server's host name", "${server.imap_port}": "the IMAP port",
                     "${server.smtp_host}": "the SMTP server's host name", "${server.smtp_port}": "the SMTP port"}
            return f"type {names[text]}" if text in names else f"type “{text}”"
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
class RegionCheck:
    """A calibrated region (by name) whose content must match its reference image (made by `calibrate references`)."""
    region: str
    tolerance: float = 0.0
    pixel_threshold: int = 24

    @classmethod
    def parse(cls, raw) -> "RegionCheck":
        if isinstance(raw, str):
            return cls(raw)
        return cls(str(raw["region"]), float(raw.get("tolerance", 0.0)), int(raw.get("pixel_threshold", 24)))


@dataclass
class Verify:
    """A check after the measured end of a step (not waiting time, not a user action): actions, then within
    `within_s` the regions must match their references (e.g. End shows the corpus's oldest message)."""
    actions: list
    regions: list
    within_s: float = 5.0

    @classmethod
    def parse(cls, raw: dict | None) -> "Verify | None":
        if not raw:
            return None
        return cls([Action.parse(a) for a in raw.get("actions") or []],
                   [RegionCheck.parse(r) for r in raw.get("regions") or []], float(raw.get("within_s", 5.0)))


@dataclass
class Step:
    name: str
    actions: list
    measure: bool = True
    settle: dict = field(default_factory=dict)
    expect: str | None = "auto"
    timeout_s: float | None = None
    regions: list = field(default_factory=list)
    first_visible: RegionCheck | None = None
    verify: Verify | None = None
    after_end: str = "report"
    complete: str | dict | None = None
    verify_probe: bool = False
    first_visible_list: bool = False
    becomes_final: dict | None = None
    final_reached: bool = False

    @property
    def checks(self) -> dict:
        """What the analysis needs to know about a step that a flow created at run time (logged with step_start).
        `becomes_final`: {"pages": [...], "checks": {...}}: on one of these pages the step turns into the final
        step with those checks (logged as `step_final`)."""
        checks = {"complete": self.complete, "verify_probe": self.verify_probe, "after_end": self.after_end,
                  "first_visible_list": self.first_visible_list, "settle": self.settle,
                  "timeout_s": self.timeout_s, "expect": self.expect}
        if self.becomes_final:
            checks["becomes_final"] = self.becomes_final
        return checks

    @classmethod
    def from_checks(cls, name: str, checks: dict) -> "Step":
        return cls(name, [], True, dict(checks.get("settle") or {}), checks.get("expect", "none"),
                   checks.get("timeout_s"), after_end=str(checks.get("after_end", "report")),
                   complete=checks.get("complete"), verify_probe=bool(checks.get("verify_probe")),
                   first_visible_list=bool(checks.get("first_visible_list")),
                   becomes_final=checks.get("becomes_final"))

    def as_final(self) -> "Step":
        """The step with the final checks it turned into (`becomes_final`)."""
        final = dict((self.becomes_final or {}).get("checks") or {})
        return Step(self.name, self.actions, True, {**dict(final.get("settle") or {}), **self.settle}, self.expect,
                    self.timeout_s, after_end=str(final.get("after_end", "report")), complete=final.get("complete"),
                    verify_probe=bool(final.get("verify_probe")),
                    first_visible_list=bool(final.get("first_visible_list")), final_reached=True)

    @property
    def region_names(self) -> set[str]:
        names = {r.region for r in self.regions}
        if self.first_visible:
            names.add(self.first_visible.region)
        if self.verify:
            names |= {r.region for r in self.verify.regions}
        return names

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
    tail_s: float | None = None
    finish_required: bool = False
    opening_screen: RegionCheck | None = None
    flow: dict | None = None

    @property
    def user_action_count(self) -> int:
        return sum(s.user_action_count for s in self.steps)

    @property
    def action_list(self) -> list[str]:
        return [a.describe() for s in self.steps for a in s.actions if a.is_input]

    @property
    def region_names(self) -> set[str]:
        names = {name for s in self.steps for name in s.region_names}
        return names | ({self.opening_screen.region} if self.opening_screen else set())

    @property
    def point_names(self) -> set[str]:
        names = set()
        verify = [a for s in self.steps if s.verify for a in s.verify.actions]
        for action in self.prepare + [a for s in self.steps for a in s.actions] + verify + self.finish:
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
    timeout_s: float | None = None

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
                    regions=[RegionCheck.parse(r) for r in s.get("regions") or []],
                    first_visible=RegionCheck.parse(s["first_visible"]) if s.get("first_visible") else None,
                    verify=Verify.parse(s.get("verify")),
                    after_end=str(s.get("after_end", "report")),
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
                tail_s=spec.get("tail_s"),
                finish_required=bool(spec.get("finish_required", False)),
                opening_screen=RegionCheck.parse(spec["opening_screen"]) if spec.get("opening_screen") else None,
                flow=dict(spec["flow"]) if spec.get("flow") else None,
            )
        title = raw.get("title") or {}
        if isinstance(title, str):
            title = {"en": title}
        return cls(str(raw["id"]), title, str(raw.get("description", "")), dict(raw.get("start_state") or {}), apps,
                   Path(path), raw.get("timeout_s"))


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
