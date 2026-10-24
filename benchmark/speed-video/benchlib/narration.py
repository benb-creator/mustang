import copy
import json
import re
from pathlib import Path


class NarrationError(Exception):
    pass


class Condition:
    """`when` grammar: expr = term ("or" term)*; term = factor ("and" factor)*;
    factor = "not" factor | "(" expr ")" | "missing(" name ")" | operand op operand.
    A comparison that involves a missing value or a text value is false (as in the voice-over's validate.py)."""

    token_pattern = re.compile(r"\s*(missing\(|\(|\)|<=|>=|==|!=|<|>|and\b|or\b|not\b|-?\d+(?:\.\d+)?|"
                               r"[A-Za-z_][A-Za-z0-9_.]*)")

    def __init__(self, source: str):
        self.source = source
        self.tokens = self.tokenize(source)
        self.position = 0
        self.tree = self.expression()
        if self.position != len(self.tokens):
            raise NarrationError(f"Unexpected '{self.tokens[self.position]}' in condition '{source}'")

    def tokenize(self, source: str) -> list[str]:
        tokens, position = [], 0
        while position < len(source):
            if source[position:].strip() == "":
                break
            m = self.token_pattern.match(source, position)
            if not m:
                raise NarrationError(f"Can't parse condition '{source}' at '{source[position:]}'")
            tokens.append(m.group(1))
            position = m.end()
        return tokens

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None or (expected and token != expected):
            raise NarrationError(f"Expected '{expected or 'more'}' in condition '{self.source}'")
        self.position += 1
        return token

    def expression(self):
        node = self.term()
        while self.peek() == "or":
            self.take()
            node = ("or", node, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.peek() == "and":
            self.take()
            node = ("and", node, self.factor())
        return node

    def factor(self):
        token = self.peek()
        if token == "not":
            self.take()
            return ("not", self.factor())
        if token == "(":
            self.take()
            node = self.expression()
            self.take(")")
            return node
        if token == "missing(":
            self.take()
            name = self.take()
            self.take(")")
            return ("missing", name)
        left = self.operand()
        op = self.take()
        if op not in ("<", "<=", ">", ">=", "==", "!="):
            raise NarrationError(f"Expected a comparison operator, got '{op}' in '{self.source}'")
        return ("cmp", op, left, self.operand())

    def operand(self):
        token = self.take()
        if re.fullmatch(r"-?\d+(?:\.\d+)?", token):
            return ("num", float(token))
        return ("ref", token)

    def evaluate(self, values: dict, node=None) -> bool:
        node = self.tree if node is None else node
        kind = node[0]
        if kind == "or":
            return self.evaluate(values, node[1]) or self.evaluate(values, node[2])
        if kind == "and":
            return self.evaluate(values, node[1]) and self.evaluate(values, node[2])
        if kind == "not":
            return not self.evaluate(values, node[1])
        if kind == "missing":
            return values.get(node[1]) is None
        _, op, left, right = node
        a, b = (n[1] if n[0] == "num" else values.get(n[1]) for n in (left, right))
        if a is None or b is None or isinstance(a, str) or isinstance(b, str):
            return False
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b, "!=": a != b}[op]


class SpokenDuration:
    """Duration with unit, as spoken and shown at the hold (`time.*`); the same rules as the voice-over's
    validate.py: below 10 s one decimal, below 59.5 s whole seconds, below 10 min minutes and seconds, below
    59.5 min whole minutes, then hours and minutes."""

    units = {"en": {"second": ("second", "seconds"), "minute": ("minute", "minutes"), "hour": ("hour", "hours"),
                    "point": "."},
             "de": {"second": ("Sekunde", "Sekunden"), "minute": ("Minute", "Minuten"), "hour": ("Stunde", "Stunden"),
                    "point": ","}}

    @classmethod
    def unit(cls, language: str, name: str, count: int) -> str:
        singular, plural = cls.units[language][name]
        return singular if count == 1 else plural

    @classmethod
    def text(cls, seconds: float, language: str) -> str:
        language = language if language in cls.units else "en"
        if seconds < 9.95:
            return f"{seconds:.1f}".replace(".", cls.units[language]["point"]) + " " + cls.unit(language, "second", 2)
        if seconds < 59.5:
            whole = round(seconds)
            return f"{whole} {cls.unit(language, 'second', whole)}"
        if seconds < 599.5:
            minutes, rest = divmod(round(seconds), 60)
            out = f"{minutes} {cls.unit(language, 'minute', minutes)}"
            return out + (f" {rest}" if rest else "")
        if seconds < 3570:
            minutes = round(seconds / 60)
            return f"{minutes} {cls.unit(language, 'minute', minutes)}"
        hours, minutes = divmod(round(seconds / 60), 60)
        out = f"{hours} {cls.unit(language, 'hour', hours)}"
        return out + (f" {minutes} {cls.unit(language, 'minute', minutes)}" if minutes else "")


class NarrationValues:
    """Raw values (for conditions) and language-formatted texts (for placeholders)."""

    def __init__(self, language: str):
        self.language = language
        self.raw: dict = {}
        self.text: dict = {}

    def number(self, value: float, decimals: int) -> str:
        text = f"{value:,.{decimals}f}"
        if self.language == "de":
            text = text.replace(",", " ").replace(".", ",").replace(" ", ".")
        return text

    def recorded(self, value) -> str:
        """A recorded value as text; a number keeps its own decimals in the language's format ("1,07" in German)."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return str(value)
        decimals = str(value).partition(".")[2]
        return self.number(value, len(decimals) if decimals.isdigit() else 0)

    def seconds_text(self, seconds: float) -> str:
        decimals = 2 if seconds < 1 else 1 if seconds < 10 else 0
        return self.number(seconds, decimals)

    def set_seconds(self, name: str, seconds: float | None):
        self.raw[name] = seconds
        if seconds is not None:
            self.text[name] = self.seconds_text(seconds)

    def set_duration(self, name: str, seconds: float | None):
        self.raw[name] = seconds
        if seconds is not None:
            self.text[name] = SpokenDuration.text(seconds, self.language)

    def set_ratio(self, name: str, ratio: float | None):
        self.raw[name] = ratio
        if ratio is not None:
            self.text[name] = self.number(ratio, 1)

    def set_count(self, name: str, count: int | None):
        self.raw[name] = count
        if count is not None:
            self.text[name] = self.number(count, 0)

    def set_text(self, name: str, text: str | None, raw=None):
        self.raw[name] = raw if raw is not None else text
        if text is not None:
            self.text[name] = text

    def substitute(self, text: str, missing: str = "–") -> str:
        def lookup(m):
            name = m.group(1).strip()
            return self.text.get(name, missing)
        return re.sub(r"\{\{\s*([^}]*?)\s*\}\}", lookup, text)

    def missing_names(self, text: str) -> list[str]:
        return [n for n in re.findall(r"\{\{\s*([^}]*?)\s*\}\}", text) if n not in self.text
                and not n.startswith(("#if", "/if", "else"))]


class MethodTemplate:
    """Method texts: {{name}} placeholders and {{#if cond}}…{{else}}…{{/if}} blocks (not nested); conditions use the
    raw values, placeholders the formatted texts. The reference is the voice-over's validate.py `MethodTemplate`."""

    block = re.compile(r"\{\{#if (.+?)\}\}(.*?)(?:\{\{else\}\}(.*?))?\{\{/if\}\}", re.S)

    @classmethod
    def render(cls, text: str, values: NarrationValues, missing: str = "–") -> tuple[str, list[str]]:
        def choose(match):
            return match.group(2) if Condition(match.group(1)).evaluate(values.raw) else (match.group(3) or "")
        chosen = cls.block.sub(choose, text)
        return values.substitute(chosen, missing), sorted(set(values.missing_names(chosen)))


class Narration:
    """narration.<lang>.json: segments with the same id are alternatives; the first whose `when` holds is used."""

    text_fields = ("voice", "voice_before", "voice_during", "voice_after")

    def __init__(self, data: dict, path: Path | None = None):
        self.data = data
        self.path = path
        self.language = data.get("language", "en")
        self.words_per_minute = float(data.get("words_per_minute", 150))
        self.segments = data.get("segments") or []

    @classmethod
    def load(cls, path) -> "Narration":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f), Path(path))

    def resolve(self, values: NarrationValues, only: list[str] | None = None) -> list[dict]:
        order, groups = [], {}
        for segment in self.segments:
            if segment["id"] not in groups:
                order.append(segment["id"])
                groups[segment["id"]] = []
            groups[segment["id"]].append(segment)
        chosen = []
        for segment_id in (only or order):
            for candidate in groups.get(segment_id, []):
                condition = candidate.get("when")
                if condition is None or Condition(condition).evaluate(values.raw):
                    resolved = copy.deepcopy(candidate)
                    resolved["missing"] = {}
                    for field in self.text_fields:
                        if resolved.get(field):
                            missing = values.missing_names(resolved[field])
                            if missing:
                                resolved["missing"][field] = missing
                            resolved[field] = values.substitute(resolved[field])
                    supers = resolved.get("supers") or []
                    resolved["supers"] = [values.substitute(s) for s in ([supers] if isinstance(supers, str) else supers)]
                    chosen.append(resolved)
                    break
        return chosen

    def speech_seconds(self, text: str | None) -> float:
        if not text:
            return 0.0
        words = [w for w in text.split() if w.strip(".,:;!?\"'“”„()–—-·")]
        return len(words) * 60.0 / self.words_per_minute + 0.3
