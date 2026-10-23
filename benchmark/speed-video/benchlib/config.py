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
        config = cls(cls.environment_values(data), path.parent)
        for key, reason in cls.removed.items():
            if config.get(key) is not None:
                raise ConfigError(f"{path}: '{key}' is no longer used ({reason}); remove it")
        config.apply_server_defaults()
        return config

    @classmethod
    def environment_values(cls, value):
        """`${NAME}` (upper case) in a string value is replaced by the environment variable NAME, so the host and the
        account's address can come from the environment like the password (e.g. a secrets file)."""
        if isinstance(value, dict):
            return {k: cls.environment_values(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls.environment_values(v) for v in value]
        if isinstance(value, str) and "${" in value:
            def lookup(m):
                if m.group(1) not in os.environ:
                    raise ConfigError(f"Environment variable {m.group(1)} (used as ${{{m.group(1)}}}) is not set")
                return os.environ[m.group(1)]
            return re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", lookup, value)
        return value

    @classmethod
    def recorded(cls, manifest: dict, local: "Config") -> "Config":
        """The config a result folder's session ran with (manifest.json, secrets removed), to analyze its results
        again on another computer: this computer's paths and the analysis rules come from `local`."""
        data = copy.deepcopy(manifest.get("config") or {})
        if not data:
            raise ConfigError("The result folder's manifest.json records no config")
        for key in ("workdir", "tools", "scenario_dir", "compose", "publish", "translations", "speech", "encode"):
            data.pop(key, None)
            if key in local.data:
                data[key] = copy.deepcopy(local.data[key])
        for dotted in ("evidence.microsoft_asns", "evidence.proxy_ports", "runs.max_cpu_pressure_pct"):
            section, name = dotted.split(".")
            if local.get(dotted) is not None:
                data.setdefault(section, {})[name] = copy.deepcopy(local.get(dotted))
        return cls(data, local.base_dir)

    def apply_server_defaults(self):
        """In account mode only the host name is needed; the endpoints follow from it unless set."""
        server = self.data.get("server")
        if not isinstance(server, dict) or not server.get("host"):
            return
        host = str(server["host"])
        server.setdefault("jmap_session_url", f"https://{host}/.well-known/jmap")
        server.setdefault("imap", {})
        server["imap"].setdefault("host", host)
        server["imap"].setdefault("port", 993)
        server["imap"].setdefault("tls", True)
        server.setdefault("smtp", {})
        server["smtp"].setdefault("host", host)
        server["smtp"].setdefault("port", 465)

    secret_keys = ("password", "secret", "token", "api_key")

    def redacted(self) -> dict:
        """The config for the manifest: no secrets (they only ever come from the environment anyway) and the
        test account's address reduced to its domain."""
        def clean(value, key=""):
            if isinstance(value, dict):
                return {k: clean(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [clean(v, key) for v in value]
            if isinstance(value, str) and any(s in key.lower() for s in self.secret_keys) and not key.endswith("_env"):
                return "<redacted>"
            return value
        data = clean(copy.deepcopy(self.data))
        account = data.get("account")
        if isinstance(account, dict):
            for key in ("email", "username"):
                if account.get(key):
                    account[key] = "<redacted>@" + str(account[key]).rpartition("@")[2]
        return data

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
