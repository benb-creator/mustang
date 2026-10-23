import json
from pathlib import Path


class FactsError(Exception):
    pass


class PersonFacts:
    """`facts.json` next to results.json (README, "Facts set by a person"): only what a person sets after checking
    the recordings, never a measured value. The allowed keys are the voice-over's `compose.json`
    `person_set_facts` (top level, every comparison, per comparison); compose, method and encode refuse a file
    with any other key and name it. Keys starting with "_" are comments."""

    default_allowed = {"top_level": ["server_ours"], "every_comparison": ["right_protocol_default"],
                       "C4": ["cloud_sync_confirmed", "dialog_text", "microsoft_footage"]}

    def __init__(self, data: dict, allowed: dict | None = None, source: str = "facts.json"):
        self.data = data or {}
        self.allowed = allowed or self.default_allowed
        self.source = source

    @classmethod
    def template(cls, comparisons: list[str], allowed: dict | None = None) -> dict:
        allowed = allowed or cls.default_allowed
        out = {"_help": "Set by a person after checking the recordings; 1 = confirmed. Never filled in by the "
                        "pipeline, and never a measured value. See README, 'Facts set by a person'.",
               **{key: None for key in allowed.get("top_level", [])}}
        for comparison in comparisons:
            out[comparison] = {key: None for key in allowed.get("every_comparison", []) + allowed.get(comparison, [])}
        return out

    @classmethod
    def load(cls, folder: Path, comparisons: list[str], allowed: dict | None = None) -> "PersonFacts":
        """The folder's facts.json, created as a template where it is missing."""
        path = Path(folder) / "facts.json"
        if not path.exists():
            path.write_text(json.dumps(cls.template(comparisons, allowed), indent=2, ensure_ascii=False))
        return cls(json.loads(path.read_text()), allowed, str(path))

    def unknown_keys(self) -> list[str]:
        top = set(self.allowed.get("top_level", []))
        every = set(self.allowed.get("every_comparison", []))
        out = []
        for key, value in self.data.items():
            if key.startswith("_") or key in top:
                continue
            if not isinstance(value, dict):
                out.append(key)
                continue
            allowed = every | set(self.allowed.get(key, []))
            out += [f"{key}.{name}" for name in value if not name.startswith("_") and name not in allowed]
        return out

    def check(self) -> "PersonFacts":
        unknown = self.unknown_keys()
        if unknown:
            raise FactsError(f"{self.source} sets keys a person may not set: {', '.join(unknown)}. Only the keys in "
                             f"compose.json person_set_facts are allowed; measured values come from the result "
                             f"folder only")
        return self

    def env(self) -> dict:
        """`env.*` names (without the prefix) and values: top-level keys as `env.<key>`, the rest per comparison."""
        out = {}
        for key, value in self.data.items():
            if key.startswith("_"):
                continue
            if isinstance(value, dict):
                out.update({f"{key}.{name}": v for name, v in value.items() if not name.startswith("_")})
            else:
                out[key] = value
        return out

    @classmethod
    def merged(cls, files: list["PersonFacts"], allowed: dict | None = None) -> "PersonFacts":
        """Several result folders' facts: comparisons from each; a top-level fact set in two folders must agree."""
        data, sources = {}, []
        for facts in files:
            sources.append(facts.source)
            for key, value in facts.data.items():
                if isinstance(value, dict):
                    data[key] = {**data.get(key, {}), **value}
                elif value is not None:
                    if data.get(key) is not None and data[key] != value:
                        raise FactsError(f"'{key}' differs between {', '.join(sources)}: {data[key]!r} vs {value!r}")
                    data[key] = value
                else:
                    data.setdefault(key, None)
        return cls(data, allowed, " + ".join(sources) or "facts.json")
