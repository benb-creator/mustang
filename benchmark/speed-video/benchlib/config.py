import copy
import os
import re
from pathlib import Path

import yaml


class ConfigError(Exception):
    pass


class Config:
    def __init__(self, data: dict, base_dir: Path):
        self.data = data
        self.base_dir = base_dir

    removed = {"settle.live_quiet_s": "the live gate now uses settle.quiet_s, like the analysis",
               "compose.countdown_s": "the short-video settings come from the voice-over's variants/compose.json",
               "compose.timelapse_threshold_s": "time-lapse follows the race budget in variants/compose.json",
               "compose.timelapse_max_compressed_s": "time-lapse follows the race budget in variants/compose.json"}

    @classmethod
    def load(cls, path) -> "Config":
        path = Path(path).resolve()
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        config = cls(data, path.parent)
        for key, reason in cls.removed.items():
            if config.get(key) is not None:
                raise ConfigError(f"{path}: '{key}' is no longer used ({reason}); remove it")
        return config

    def get(self, dotted: str, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, dotted: str):
        value = self.get(dotted)
        if value is None:
            raise ConfigError(f"Missing config value '{dotted}'")
        return value

    def path(self, value) -> Path:
        p = Path(os.path.expanduser(str(value)))
        return p if p.is_absolute() else (self.base_dir / p).resolve()

    @property
    def workdir(self) -> Path:
        return self.path(self.get("workdir", "work"))

    @property
    def scenario_dir(self) -> Path:
        return self.path(self.get("scenario_dir", Path(__file__).resolve().parent.parent / "scenarios"))

    def tool(self, name: str) -> str:
        return str(self.get(f"tools.{name}", name))

    def secret(self, dotted_env_key: str) -> str:
        env_name = self.require(dotted_env_key)
        value = os.environ.get(env_name)
        if value is None:
            raise ConfigError(f"Environment variable {env_name} (from '{dotted_env_key}') is not set")
        return value

    def app(self, app_id: str) -> dict:
        apps = self.get("apps", {})
        if app_id not in apps:
            raise ConfigError(f"Unknown app '{app_id}'. Known: {', '.join(apps)}")
        return copy.deepcopy(apps[app_id])

    def comparison(self, comparison_id: str) -> dict:
        comparisons = self.get("comparisons", {})
        if comparison_id not in comparisons:
            raise ConfigError(f"Unknown comparison '{comparison_id}'. Known: {', '.join(comparisons)}")
        return comparisons[comparison_id]

    def run_group(self, comparison_id: str) -> str:
        """The recording session of a comparison: its own, or a session shared by the comparisons of one computer
        (`sessions`), whose apps are interleaved in one series, so both comparisons use the same Parula runs."""
        return str((self.get("comparisons", {}).get(comparison_id) or {}).get("session") or comparison_id)

    def group_apps(self, comparison_id: str) -> list[str]:
        group = self.run_group(comparison_id)
        if group == comparison_id:
            spec = self.comparison(comparison_id)
            return [spec["left"], spec["right"]]
        sessions = self.get("sessions") or {}
        if group not in sessions:
            raise ConfigError(f"Comparison {comparison_id} names session '{group}', which isn't in `sessions`")
        return list(sessions[group]["apps"])

    def group_comparisons(self, comparison_id: str) -> list[str]:
        group = self.run_group(comparison_id)
        return [c for c in self.get("comparisons", {}) if self.run_group(c) == group]

    def profile_dir(self, app_id: str) -> Path:
        return self.workdir / "profiles" / app_id

    def expand(self, value, app_id: str | None = None, extra: dict | None = None):
        """Replaces {workdir}, {profile}, {config_dir}, {home} and `extra` keys in strings, lists and dicts."""
        variables = {
            "workdir": str(self.workdir),
            "config_dir": str(self.base_dir),
            "home": os.path.expanduser("~"),
        }
        if app_id:
            variables["profile"] = str(self.profile_dir(app_id))
        variables.update(extra or {})

        def substitute(text: str) -> str:
            return re.sub(r"\{(\w+)\}", lambda m: variables.get(m.group(1), m.group(0)), text)

        if isinstance(value, str):
            return substitute(value)
        if isinstance(value, list):
            return [self.expand(v, app_id, extra) for v in value]
        if isinstance(value, dict):
            return {self.expand(k, app_id, extra): self.expand(v, app_id, extra) for k, v in value.items()}
        return value
