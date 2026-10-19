"""Evidence from the benchmark Stalwart server's log: who logged in from where, and what each source fetched.

The benchmark instance needs a log tracer for these events (Stalwart 0.16, checked on 0.16.26): `auth.success`,
`auth.failed`, `imap.connection-start`, `imap.connection-end`, `imap.select`, `imap.fetch`, `imap.logout`,
`pop3.connection-start`, `pop3.fetch`, `http.request-url`, `smtp.connection-start` (README: "Server log evidence").
`imap.fetch` names the fetched messages by Stalwart document id and the fetched items; Stalwart's JMAP email ids
encode the same document id, so message sizes come from one JMAP `Email/get`."""

import json
import math
import re
import secrets
import shlex
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .evidence import NetworkOwners


class ServerLogError(Exception):
    pass


@dataclass
class LogEvent:
    utc: float
    level: str
    event: str
    fields: dict

    line_pattern = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\s+(\w+)\s+.*?\(([a-z0-9]+\.[a-z0-9-]+)\)\s*(.*)$")
    key_pattern = re.compile(r"\s*(\w+) = ")
    next_key_pattern = re.compile(r", (?=\w+ = )")
    item_pattern = re.compile(r'"((?:[^"\\]|\\.)*)"|([^,\s\[\]]+)')

    @classmethod
    def parse(cls, line: str) -> "LogEvent | None":
        m = cls.line_pattern.match(line.strip())
        if not m:
            return None
        stamp, level, event, rest = m.groups()
        utc = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        return cls(utc, level, event, cls.parse_fields(rest))

    @classmethod
    def parse_fields(cls, rest: str) -> dict:
        fields, i = {}, 0
        while True:
            m = cls.key_pattern.match(rest, i)
            if not m:
                return fields
            key, i = m.group(1), m.end()
            if rest.startswith('"', i):
                end = cls.closing(rest, i, None)
            elif rest.startswith("[", i):
                end = cls.closing(rest, i, "]")
            else:
                found = cls.next_key_pattern.search(rest, i)
                end = found.start() if found else len(rest)
            fields[key] = cls.value(rest[i:end].strip())
            i = end + 2 if rest.startswith(", ", end) else end

    @staticmethod
    def closing(text: str, start: int, bracket: str | None) -> int:
        """End index (exclusive) of the quoted string or bracketed list starting at `start`."""
        in_string = bracket is None
        i = start + 1
        while i < len(text):
            ch = text[i]
            if in_string:
                if ch == "\\":
                    i += 1
                elif ch == '"':
                    in_string = False
                    if bracket is None:
                        return i + 1
            elif ch == '"':
                in_string = True
            elif ch == bracket:
                return i + 1
            i += 1
        return len(text)

    @classmethod
    def value(cls, raw: str):
        if raw.startswith('"'):
            return raw[1:-1].replace('\\"', '"')
        if raw.startswith("["):
            items = []
            for quoted, bare in cls.item_pattern.findall(raw[1:-1]):
                items.append(quoted.replace('\\"', '"') if quoted or not bare else
                             int(bare) if bare.isdigit() else bare)
            return items
        if raw.isdigit():
            return int(raw)
        return raw

    @property
    def source(self) -> str | None:
        return self.fields.get("remoteIp")

    @property
    def protocol(self) -> str:
        return str(self.fields.get("listenerId") or self.event.split(".")[0])


class StalwartIds:
    alphabet = "abcdefghijklmnopqrstuvwxyz792013"

    @classmethod
    def document_id(cls, jmap_id: str) -> int | None:
        value = 0
        for ch in jmap_id:
            index = cls.alphabet.find(ch)
            if index < 0:
                return None
            value = value * 32 + index
        return value & 0xFFFFFFFF


class FetchKinds:
    @staticmethod
    def full_content(details: list) -> bool:
        """BODY[] / BODY.PEEK[] without a section or partial range, or RFC822: the whole message."""
        for item in details or []:
            text = str(item)
            if text == "Rfc822" or (text.startswith("BodySection") and "sections: []" in text and
                                     "partial: None" in text):
                return True
        return False

    @staticmethod
    def headers(details: list) -> bool:
        """Header-type items: ENVELOPE, RFC822.HEADER, BODY[HEADER], BODY[HEADER.FIELDS (…)]."""
        for item in details or []:
            text = str(item)
            if text in ("Envelope", "Rfc822Header") or (text.startswith("BodySection") and "Header" in text):
                return True
        return False

    @staticmethod
    def any_body(details: list) -> bool:
        return any(str(item).startswith(("BodySection", "Rfc822", "Binary", "Body")) for item in details or [])


@dataclass
class SourceSummary:
    ip: str
    owner: dict
    kind: str
    logins: dict = field(default_factory=dict)
    failed_logins: int = 0
    accounts: set = field(default_factory=set)
    connections: int = 0
    fetch_commands: int = 0
    full_messages: set = field(default_factory=set)
    header_messages: set = field(default_factory=set)
    body_messages: set = field(default_factory=set)
    downloads: int = 0
    api_requests: int = 0
    addresses: int = 1

    def merge(self, other: "SourceSummary"):
        for protocol, count in other.logins.items():
            self.logins[protocol] = self.logins.get(protocol, 0) + count
        self.failed_logins += other.failed_logins
        self.accounts |= other.accounts
        self.connections += other.connections
        self.fetch_commands += other.fetch_commands
        self.full_messages |= other.full_messages
        self.header_messages |= other.header_messages
        self.body_messages |= other.body_messages
        self.downloads += other.downloads
        self.api_requests += other.api_requests
        self.addresses += other.addresses
        self.first_utc = min(x for x in (self.first_utc, other.first_utc) if x is not None)
        self.last_utc = max(x for x in (self.last_utc, other.last_utc) if x is not None)
    first_utc: float | None = None
    last_utc: float | None = None

    def to_dict(self, sizes: dict[int, int] | None, label: str) -> dict:
        full_bytes = None
        if sizes is not None:
            known = [sizes[d] for d in self.full_messages if d in sizes]
            full_bytes = sum(known) if len(known) == len(self.full_messages) else None
        return {"source": label, "kind": self.kind, "owner": self.owner.get("owner"), "asn": self.owner.get("asn"),
                "as_holder": self.owner.get("as_holder"), "prefix": self.owner.get("prefix"),
                "addresses": self.addresses, "logins": self.logins, "failed_logins": self.failed_logins,
                "accounts": sorted(self.accounts), "connections": self.connections,
                "fetch_commands": self.fetch_commands, "full_messages": len(self.full_messages),
                "full_bytes": full_bytes, "header_messages": len(self.header_messages),
                "messages_with_body_parts": len(self.body_messages), "downloads": self.downloads,
                "api_requests": self.api_requests,
                "first": ServerLog.iso(self.first_utc), "last": ServerLog.iso(self.last_utc)}


class ServerLog:
    """Reads the benchmark server's evidence log (locally or over the snapshot SSH access) and summarizes it."""

    def __init__(self, config, runner, progress=print):
        self.config = config
        spec = config.get("server.log") or {}
        self.spec = spec
        self.runner = runner
        self.progress = progress
        self.path_glob = spec.get("path")
        self.account = str(config.get("account.username") or config.get("account.email") or "")
        self.cloud_asns = {f"AS{str(a).upper().removeprefix('AS')}" for a in spec.get("cloud_asns", [8075])}
        self.cloud_owner = re.compile(spec.get("cloud_owner_pattern", "Microsoft"), re.I)
        self.owners = NetworkOwners(config.workdir / "evidence" / "ip-owners.json")
        self.configured_ips = set(spec.get("benchmark_ips") or [])
        self.probe_file = config.workdir / "evidence" / "benchmark-ips.json"
        self.probed_ips: set[str] = set(json.loads(self.probe_file.read_text())) if self.probe_file.exists() else set()
        self.write_delay_s = float(spec.get("write_delay_s", 3))

    @property
    def enabled(self) -> bool:
        return bool(self.path_glob)

    @staticmethod
    def iso(utc: float | None) -> str | None:
        return None if utc is None else datetime.fromtimestamp(utc, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def lines(self, since_utc: float, until_utc: float) -> list[str]:
        since, until = shlex.quote(self.iso(since_utc - 1)), shlex.quote(self.iso(until_utc + 1))
        script = (f"for f in {self.path_glob}; do [ -f \"$f\" ] && cat \"$f\"; done | "
                  f"awk -v s={since} -v u={until} '$1 >= s && $1 <= u'")
        return self.runner.run(script, timeout=600).splitlines()

    def events(self, since_utc: float, until_utc: float) -> list[LogEvent]:
        return [e for e in (LogEvent.parse(line) for line in self.lines(since_utc, until_utc)) if e]

    def probe(self) -> set[str]:
        """Finds the benchmark computer's address as the server sees it: one HTTP request with a unique path."""
        nonce = secrets.token_hex(8)
        url = self.config.require("server.jmap_session_url")
        base = url.split("/", 3)
        probe_url = f"{base[0]}//{base[2]}/.well-known/bench-probe-{nonce}"
        started = time.time()
        try:
            urllib.request.urlopen(probe_url, timeout=15).close()
        except urllib.error.HTTPError:
            pass
        time.sleep(self.write_delay_s)
        found = {e.source for e in self.events(started - 2, time.time())
                 if e.event == "http.request-url" and nonce in str(e.fields.get("url", "")) and e.source}
        if not found:
            raise ServerLogError(f"The probe request {probe_url} isn't in the server log ({self.path_glob}); is the "
                                 f"evidence tracer with http.request-url set up?")
        self.probed_ips |= found
        self.probe_file.parent.mkdir(parents=True, exist_ok=True)
        self.probe_file.write_text(json.dumps(sorted(self.probed_ips)))
        return found

    @property
    def benchmark_ips(self) -> set[str]:
        return self.configured_ips | self.probed_ips

    def kind_of(self, ip: str) -> tuple[str, dict]:
        if ip in self.benchmark_ips:
            return "benchmark", {"owner": "benchmark computer"}
        owner = self.owners.lookup(ip)
        cloud = (owner.get("asn") in self.cloud_asns or
                 any(self.cloud_owner.search(str(owner.get(k) or "")) for k in ("owner", "as_holder")))
        return ("cloud" if cloud else "other"), owner

    def summarize(self, events: list[LogEvent]) -> dict[str, SourceSummary]:
        sources: dict[str, SourceSummary] = {}
        for e in events:
            ip = e.source
            if not ip:
                continue
            if ip not in sources:
                kind, owner = self.kind_of(ip)
                sources[ip] = SourceSummary(ip, owner, kind)
            s = sources[ip]
            s.first_utc = e.utc if s.first_utc is None else min(s.first_utc, e.utc)
            s.last_utc = e.utc if s.last_utc is None else max(s.last_utc, e.utc)
            if e.event == "auth.success":
                s.logins[e.protocol] = s.logins.get(e.protocol, 0) + 1
                s.accounts.add(str(e.fields.get("accountName")))
            elif e.event == "auth.failed":
                s.failed_logins += 1
            elif e.event == "http.request-url":
                url = str(e.fields.get("url", ""))
                s.downloads += "/download/" in url
                s.api_requests += url.rstrip("/").endswith("/jmap")
            elif e.event.endswith("connection-start"):
                s.connections += 1
            elif e.event in ("imap.fetch", "pop3.fetch"):
                s.fetch_commands += 1
                documents = e.fields.get("documentId") or []
                documents = documents if isinstance(documents, list) else [documents]
                details = e.fields.get("details") or []
                if e.event == "pop3.fetch" or FetchKinds.full_content(details):
                    s.full_messages.update(documents)
                if FetchKinds.headers(details):
                    s.header_messages.update(documents)
                if FetchKinds.any_body(details):
                    s.body_messages.update(documents)
        return sources

    def document_sizes(self) -> dict[int, int] | None:
        path = self.config.workdir / "evidence" / "document-sizes.json"
        if path.exists():
            return {int(k): v for k, v in json.loads(path.read_text()).items()}
        from .seed import Seeder
        try:
            sizes = {}
            for jmap_id, size in Seeder(self.config, self.progress).jmap().email_sizes().items():
                document = StalwartIds.document_id(jmap_id)
                if document is None:
                    return None
                sizes[document] = size
        except Exception as ex:
            self.progress(f"  message sizes not available ({type(ex).__name__}: {ex})")
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sizes))
        return sizes

    def report(self, events: list[LogEvent], sizes: dict[int, int] | None) -> dict:
        """Per source network: the benchmark computer (never its address), or the owner's network prefix (never
        single addresses); logins, failed logins, messages fetched in full and by headers, bytes."""
        grouped: dict[str, SourceSummary] = {}
        for ip, summary in sorted(self.summarize(events).items(), key=lambda x: x[1].first_utc or 0):
            label = "benchmark computer" if summary.kind == "benchmark" else \
                (summary.owner.get("prefix") or f"{summary.owner.get('owner') or 'unknown owner'}, unknown prefix")
            if label in grouped:
                grouped[label].merge(summary)
            else:
                grouped[label] = summary
        listed = [s.to_dict(sizes, label) for label, s in grouped.items()]
        kinds = ("benchmark", "cloud", "other")
        total = lambda kind, key: sum(d[key] or 0 for d in listed if d["kind"] == kind)
        return {"sources": listed,
                "logins": {k: sum(sum(d["logins"].values()) for d in listed if d["kind"] == k) for k in kinds},
                "failed_logins": {k: total(k, "failed_logins") for k in kinds},
                "full_messages": {k: total(k, "full_messages") for k in kinds},
                "header_messages": {k: total(k, "header_messages") for k in kinds},
                "full_bytes": {k: total(k, "full_bytes") for k in kinds}}

    def collect(self, run_dir: Path, since_utc: float, until_utc: float, marks: dict[str, float]) -> dict:
        """Writes the run's log lines and its evidence: for the whole run, until the account was removed (the
        `removal` mark: the first input of the finishing sequence), after its removal, and after the measured steps
        (`steps-done`). The log has whole seconds:
        an event in the second of a mark counts to the later window."""
        time.sleep(self.write_delay_s)
        lines = self.lines(since_utc, until_utc)
        (run_dir / "server-log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        events = [e for e in (LogEvent.parse(line) for line in lines) if e]
        sizes = self.document_sizes()
        second = math.floor
        finish = second(marks["removal"]) if marks.get("removal") else None
        steps_done = second(marks["steps-done"]) if marks.get("steps-done") else None
        start, end = second(since_utc), second(until_utc) + 1
        windows = {"total": (start, end), "until_removal": (start, finish or end)}
        if finish:
            windows["after_removal"] = (finish, end)
        if steps_done:
            windows["after_steps"] = (steps_done, finish or end)
        evidence = {"version": 1, "from": self.iso(since_utc), "to": self.iso(until_utc),
                    "benchmark_ip_count": len(self.benchmark_ips), "account": self.account,
                    "marks": {k: self.iso(v) for k, v in marks.items()},
                    "windows": {name: self.report([e for e in events if a <= e.utc < b], sizes)
                                for name, (a, b) in windows.items()}}
        (run_dir / "server-evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return evidence

    def wait_quiet(self, quiet_s: float, timeout_s: float, watch: str = "logins", poll_s: float = 30) -> dict:
        """Waits until nobody outside the benchmark computer has logged in (or tried to; `watch: logins`) or fetched
        messages (`watch: fetches`) for `quiet_s`."""
        kinds = {"logins": ("auth.success", "auth.failed"), "fetches": ("imap.fetch", "pop3.fetch")}[watch]
        started = time.time()
        while True:
            now = time.time()
            outside = [e for e in self.events(started, now) if e.event in kinds and e.source and
                       e.source not in self.benchmark_ips]
            last = max((e.utc for e in outside), default=started)
            info = {"watch": watch, "watched_s": round(now - started), "events_outside": len(outside),
                    "last_event": self.iso(last if outside else None), "timeout_s": timeout_s}
            if now - last >= quiet_s:
                return {**info, "quiet": True}
            if now - started > timeout_s:
                return {**info, "quiet": False}
            time.sleep(min(poll_s, max(1.0, quiet_s - (now - last))))


class EvidenceSummary:
    """Turns the per-run evidence of one comparison into the facts the narration and the method text use."""

    def __init__(self, comparison_id: str, task_id: str, sides: dict, cloud_sides: set[str]):
        self.comparison_id = comparison_id
        self.task_id = task_id
        self.sides = sides
        self.cloud_sides = cloud_sides

    @staticmethod
    def window(run: dict, name: str) -> dict | None:
        evidence = run.get("server_evidence") or {}
        return (evidence.get("windows") or {}).get(name)

    def side(self, side_name: str, side: dict) -> dict:
        runs = [r for r in side["runs"] if r.get("server_evidence")]
        per_run = []
        for r in runs:
            until = self.window(r, "until_removal") or {}
            after = self.window(r, "after_removal") or {}
            after_steps = self.window(r, "after_steps") or {}
            per_run.append({
                "run": r["run"], "logins": until.get("logins", {}),
                "cloud_full_messages": (until.get("full_messages") or {}).get("cloud", 0),
                "cloud_header_messages": (until.get("header_messages") or {}).get("cloud", 0),
                "cloud_full_bytes": (until.get("full_bytes") or {}).get("cloud", 0),
                "cloud_logins_after_removal": ((after.get("logins") or {}).get("cloud", 0) +
                                               (after.get("failed_logins") or {}).get("cloud", 0)) if after else None,
                "after_steps_full_messages": sum((after_steps.get("full_messages") or {}).values()) if after_steps
                else None,
                "cloud_owners": sorted({s["owner"] or "" for s in until.get("sources", []) if s["kind"] == "cloud"}),
                "cloud_asns": sorted({s["asn"] or "" for s in until.get("sources", []) if s["kind"] == "cloud"}),
                "sources": until.get("sources", []),
                "other_sources": [s for s in until.get("sources", []) if s["kind"] == "other"]})
        complete = bool(runs) and len(runs) == len(side["runs"])
        direct = complete and all(sum(x["logins"].values()) > 0 and x["logins"].get("benchmark", 0) ==
                                  sum(x["logins"].values()) for x in per_run)
        out = {"runs_with_evidence": len(runs), "runs": per_run, "direct_only": 1 if direct else 0}
        if side_name in self.cloud_sides:
            cloud = complete and all(x["logins"].get("cloud", 0) > 0 for x in per_run)
            out["cloud_login_confirmed"] = 1 if cloud else 0
            if per_run:
                fewest = min(per_run, key=lambda x: x["cloud_full_messages"])
                out["cloud_fetched_messages"] = fewest["cloud_full_messages"]
                out["cloud_fetched_bytes"] = fewest["cloud_full_bytes"]
                out["cloud_fetched_headers"] = min(x["cloud_header_messages"] for x in per_run)
                owners = [o for x in per_run for o in x["cloud_owners"] if o]
                asns = [a for x in per_run for a in x["cloud_asns"] if a]
                out["cloud_ip_owner"] = max(set(owners), key=owners.count) if owners else None
                out["cloud_asn"] = max(set(asns), key=asns.count) if asns else None
                after = [x["cloud_logins_after_removal"] for x in per_run if x["cloud_logins_after_removal"] is not None]
                out["cloud_logins_after_removal"] = max(after) if after else None
        return out

    def compute(self) -> dict:
        result = {name: self.side(name, side) for name, side in self.sides.items()}
        values = {f"{name}_direct_only": data["direct_only"] for name, data in result.items()
                  if data["runs_with_evidence"]}
        for name in self.cloud_sides:
            data = result.get(name) or {}
            for key in ("cloud_login_confirmed", "cloud_fetched_messages", "cloud_fetched_headers", "cloud_ip_owner",
                        "cloud_asn", "cloud_logins_after_removal"):
                if data.get(key) is not None:
                    values[key] = data[key]
            if data.get("cloud_fetched_bytes") is not None:
                values["cloud_fetched_gb"] = round(data["cloud_fetched_bytes"] / 1e9, 2)
        return {"task": self.task_id, "sides": result, "values": values, "lines": self.lines(result)}

    def lines(self, result: dict) -> list[str]:
        out = []
        for name, data in result.items():
            app = self.sides[name]["name"]
            if not data["runs_with_evidence"]:
                out.append(f"{app}: no server log evidence")
                continue
            logins = [sum(x["logins"].values()) for x in data["runs"]]
            out.append(f"{app}: logins per measured run {logins}; all from the benchmark computer: "
                       f"{'yes' if data['direct_only'] else 'no'}")
            if "cloud_login_confirmed" in data:
                out.append(f"{app}: logins from {data.get('cloud_ip_owner')} ({data.get('cloud_asn')}) in every run: "
                           f"{'yes' if data['cloud_login_confirmed'] else 'no'}; fewest messages fetched in full by "
                           f"those addresses before the account was removed: {data.get('cloud_fetched_messages')}"
                           f" ({data.get('cloud_fetched_bytes')} bytes); most logins after a removal: "
                           f"{data.get('cloud_logins_after_removal')}")
            for x in data["runs"]:
                for other in x["other_sources"]:
                    out.append(f"{app} {x['run']}: login(s) from {other['source']} ({other['owner']}, {other['asn']})")
        return out
