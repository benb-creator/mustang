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

    @classmethod
    def load(cls, path) -> "Config":
        path = Path(path).resolve()
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(data, path.parent)

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
            return {k: self.expand(v, app_id, extra) for k, v in value.items()}
        return value
