"""Client-side network evidence (spec v4): which processes of each app connected where, summarized per run and per
session. Raw addresses stay in each run's network.jsonl; the summaries publish owner, ASN and prefix only."""

import ipaddress
import json
import math
import socket
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .driver import EventLog
from .netwatch import NetworkLog


class NetworkOwners:
    """Owner and network of an IP address: RDAP (rdap.org) for the registrant, RIPEstat for the origin AS; cached."""

    def __init__(self, cache_path: Path, timeout_s: float = 20):
        self.cache_path = Path(cache_path)
        self.timeout_s = timeout_s
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}

    def fetch_json(self, url: str) -> dict:
        request = urllib.request.Request(url, headers={"Accept": "application/json, application/rdap+json",
                                                       "User-Agent": "parula-speed-benchmark"})
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            return json.loads(response.read())

    def lookup(self, ip: str) -> dict:
        if ip in self.cache:
            return self.cache[ip]
        address = ipaddress.ip_address(ip)
        if address.is_loopback:
            info = {"ip": ip, "owner": "this computer (loopback)", "asn": None, "as_holder": None, "prefix": None,
                    "source": "address range"}
        elif address.is_private or address.is_link_local:
            info = {"ip": ip, "owner": "private network", "asn": None, "as_holder": None, "prefix": None,
                    "source": "address range"}
        else:
            info = {"ip": ip, "owner": None, "asn": None, "as_holder": None, "prefix": None, "source": "RDAP, RIPEstat",
                    "looked_up": datetime.now(timezone.utc).isoformat()}
            try:
                rdap = self.fetch_json(f"https://rdap.org/ip/{ip}")
                info["network_name"] = rdap.get("name")
                info["owner"] = self.registrant(rdap) or rdap.get("name")
            except (urllib.error.URLError, OSError, ValueError) as ex:
                info["rdap_error"] = str(ex)
            try:
                network = self.fetch_json(f"https://stat.ripe.net/data/network-info/data.json?resource={ip}")["data"]
                asns = network.get("asns") or []
                info["prefix"] = network.get("prefix")
                if asns:
                    info["asn"] = f"AS{asns[0]}"
                    overview = self.fetch_json(f"https://stat.ripe.net/data/as-overview/data.json?resource=AS{asns[0]}")
                    info["as_holder"] = overview["data"].get("holder")
            except (urllib.error.URLError, OSError, ValueError, KeyError) as ex:
                info["ripestat_error"] = str(ex)
        self.cache[ip] = info
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=2))
        return info

    @staticmethod
    def registrant(rdap: dict) -> str | None:
        for entity in rdap.get("entities") or []:
            if "registrant" in (entity.get("roles") or []):
                for item in (entity.get("vcardArray") or [None, []])[1]:
                    if item and item[0] == "fn":
                        return item[3]
        return None


class MailServerAddresses:
    """The mail server's addresses as this computer resolves them at run time, and the ports that count as mail
    connections (the standard ones plus the account's configured endpoints)."""

    standard_ports = {993, 143, 465, 587, 443}
    mail_only_ports = {993, 143, 465, 587, 25, 110, 995}

    @staticmethod
    def resolve(hostnames: set[str], ports: set[int] | None = None) -> dict:
        hosts = {}
        for host in sorted(hostnames):
            try:
                hosts[host] = sorted({info[4][0] for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
            except OSError as ex:
                hosts[host] = []
                hosts[f"{host} (error)"] = [str(ex)]
        addresses = sorted({a for host, values in hosts.items() if not host.endswith("(error)") for a in values})
        return {"hosts": hosts, "addresses": addresses,
                "ports": sorted(MailServerAddresses.standard_ports | set(ports or ())),
                "mail_only_ports": sorted(MailServerAddresses.mail_only_ports | set(ports or ()) - {443}),
                "utc": datetime.now(timezone.utc).isoformat()}

    @staticmethod
    def for_server(server) -> dict:
        url = urlparse(server.jmap_session_url)
        ports = {server.imap_settings["port"], server.smtp_settings["port"], url.port or 443}
        return MailServerAddresses.resolve(server.mail_hostnames(), ports)


class MicrosoftNetworks:
    """Which networks count as registered to Microsoft (spec v5, v6): the origin AS is in the configured list
    (`evidence.microsoft_asns`), or the RDAP registrant or the AS holder starts with "Microsoft". Never a fact a
    person sets; the rule is published in manifest.json `evidence_rules`."""

    def __init__(self, asns: list | None = None):
        default = ["AS8075", "AS8068", "AS8069", "AS8070", "AS8071", "AS8072", "AS8073", "AS8074", "AS3598",
                   "AS6584", "AS12076"]
        self.asns = sorted({f"AS{str(a).upper().removeprefix('AS')}" for a in (asns or default)})

    @classmethod
    def from_config(cls, config) -> "MicrosoftNetworks":
        return cls(config.get("evidence.microsoft_asns"))

    def registered(self, owner: str | None, asn: str | None, as_holder: str | None = None) -> bool:
        if asn and str(asn).upper() in self.asns:
            return True
        return any(str(name or "").casefold().startswith("microsoft") for name in (owner, as_holder))

    def describe(self) -> dict:
        return {"microsoft_asns": self.asns,
                "microsoft_names": "RDAP registrant or AS holder starting with \"Microsoft\""}


class RunEvidence:
    """evidence.json of one run, from its network.jsonl, driver.jsonl (the app's launch), analysis.json and
    verify.json. `protocol` is the app's (JMAP or IMAP), `endpoints` the account's server endpoints (manifest.json
    `server.endpoints`): together they give the app's own mail endpoint."""

    def __init__(self, run_dir: Path, owners: NetworkOwners | None, proxy_ports: set[int] | None = None,
                 probe_bytes: int = 65536, protocol: str | None = None, endpoints: dict | None = None,
                 microsoft: MicrosoftNetworks | None = None):
        self.run_dir = Path(run_dir)
        self.owners = owners
        self.proxy_ports = set(proxy_ports or {1080, 3128})
        self.probe_bytes = probe_bytes
        self.protocol = str(protocol).split()[0].upper() if protocol else None
        self.endpoints = endpoints or {}
        self.microsoft = microsoft or MicrosoftNetworks()

    def window(self) -> dict | None:
        analysis_path = self.run_dir / "analysis.json"
        if not analysis_path.exists():
            return None
        analysis = json.loads(analysis_path.read_text())
        return analysis.get("measured_window")

    def launch_t(self) -> float | None:
        """When the test script started the app (driver clock), from driver.jsonl."""
        path = self.run_dir / "driver.jsonl"
        if not path.exists():
            return None
        launch = next((e for e in EventLog.read(path) if e["type"] == "input" and e.get("action") == "launch"), None)
        return None if launch is None else launch.get("t_before", launch["t"])

    def endpoint_port(self) -> int | None:
        """The port of the app's own mail endpoint: the IMAP port for IMAP apps, the JMAP URL's port for JMAP."""
        if self.protocol == "JMAP":
            url = urlparse(str(self.endpoints.get("jmap_session_url") or ""))
            return url.port or {"https": 443, "http": 80}.get(url.scheme)
        if self.protocol == "IMAP":
            port = (self.endpoints.get("imap") or {}).get("port")
            return int(port) if port else None
        return None

    def connections(self, events: list[dict]) -> list[dict]:
        """One entry per connection: opened/closed times (driver clock), process, last byte counters."""
        open_now: dict[tuple, dict] = {}
        done = []
        for e in events:
            if e["type"] not in ("open", "close", "bytes", "state"):
                continue
            key = (e.get("local"), e.get("remote"), e.get("remote_port"))
            if e["type"] == "open":
                entry = {"remote": e["remote"], "remote_port": e["remote_port"], "local": e["local"],
                         "pid": e.get("pid"), "process": e.get("process"), "opened_t": e["t"], "closed_t": None,
                         "received": None, "sent": None, "received_at": []}
                open_now[key] = entry
                done.append(entry)
            elif key in open_now:
                entry = open_now[key]
                if e["type"] == "bytes":
                    entry["received"], entry["sent"] = e.get("received"), e.get("sent")
                    entry["received_at"].append((e["t"], e.get("received") or 0))
                elif e["type"] == "close":
                    entry["closed_t"] = e["t"]
                    del open_now[key]
        return done

    @staticmethod
    def outside_tree(events: list[dict], server_addresses: set[str], launch_t: float | None,
                     script_pid: int | None) -> tuple[list[dict], dict]:
        """Connections of processes outside the app's tree to the mail server's addresses (Windows
        `open_outside_tree` lines) that count: first seen after the app's launch, in SYN_SENT, ESTABLISHED or a
        later closing state; not counted: TIME_WAIT rows (leftovers, on Windows with pid 0), rows seen before the
        launch, and the test script's own process."""
        counted, ignored = [], Counter()
        for e in events:
            if e["type"] != "open_outside_tree" or e.get("remote") not in server_addresses:
                continue
            if e.get("state") in ("TIME_WAIT", "CLOSED", "DELETE_TCB"):
                ignored[str(e.get("state"))] += 1
            elif launch_t is None or e["t"] < launch_t:
                ignored["before the app's launch"] += 1
            elif script_pid is not None and e.get("pid") == script_pid:
                ignored["the test script"] += 1
            else:
                counted.append({k: e.get(k) for k in ("t", "pid", "process", "remote_port", "state")})
        return counted, dict(ignored)

    def carries_data(self, conn: dict, last_t: float) -> bool:
        """A connection that received more than a probe's few bytes, or whose byte count is unknown although it
        stayed open long enough to be read (a guessing app's probes are short and small)."""
        if conn["received"] is not None:
            return conn["received"] > self.probe_bytes
        closed = conn["closed_t"] if conn["closed_t"] is not None else last_t
        return closed - conn["opened_t"] > 5.0

    @staticmethod
    def overlaps(conn: dict, window: dict | None) -> bool:
        if not window:
            return True
        closed = conn["closed_t"] if conn["closed_t"] is not None else float("inf")
        return conn["opened_t"] <= window["to_t"] and closed >= window["from_t"]

    @staticmethod
    def received_until(conn: dict, t: float) -> int:
        values = [v for when, v in conn["received_at"] if when <= t]
        return values[-1] if values else 0

    @staticmethod
    def inbox(verify: dict | None) -> tuple[bool | None, str | None]:
        """Completeness and its basis: "count" (the app's own count of the folder), "unread count" or "oldest
        message only" (nothing about the number was observed, so not complete). The Linux probes read the count."""
        if verify is None:
            return None, None
        basis = verify.get("basis") or ("count" if verify.get("listed") is not None else None)
        if basis == "oldest message only":
            return None, basis
        return verify.get("inbox_complete"), basis

    @staticmethod
    def logged_server(events: list[dict]) -> dict:
        """The mail server's addresses and ports as the run's network log recorded them at its start."""
        resolved = [e for e in events if e["type"] == "resolve"]
        logged = next((e for e in events if e["type"] == "mail_server"), {})
        addresses = sorted(set(logged.get("addresses") or []) | {a for e in resolved for a in e.get("addresses", [])})
        return {"hosts": {e["host"]: e.get("addresses", []) for e in resolved}, "addresses": addresses,
                "ports": logged.get("ports") or sorted(MailServerAddresses.standard_ports),
                "mail_only_ports": logged.get("mail_only_ports") or sorted(MailServerAddresses.mail_only_ports)}

    def mail_elsewhere(self) -> list[dict]:
        """The app's connections on mail ports to other addresses than the mail server's: where else its mail
        connections went (the check after every run)."""
        events = NetworkLog.read(self.run_dir / "network.jsonl")
        server = self.logged_server(events)
        addresses, mail_only = set(server["addresses"]), set(server["mail_only_ports"])
        return [c for c in self.connections(events) if c["remote"] not in addresses and c["remote_port"] in mail_only
                and not ipaddress.ip_address(c["remote"]).is_loopback]

    def summarize(self, mail_server: dict | None = None) -> dict:
        events = NetworkLog.read(self.run_dir / "network.jsonl")
        header = next((e for e in events if e["type"] == "header"), {})
        if mail_server is None:
            mail_server = self.logged_server(events)
        server_addresses = set(mail_server.get("addresses") or [])
        ports = set(mail_server.get("ports") or MailServerAddresses.standard_ports)
        mail_only = set(mail_server.get("mail_only_ports") or MailServerAddresses.mail_only_ports)
        window = self.window()
        connections = self.connections(events)
        last_t = max((e["t"] for e in events), default=0.0)
        direct, other_ports, elsewhere, proxies, loopback, unrelated = [], [], [], [], [], []
        for conn in connections:
            remote = conn["remote"]
            if remote in server_addresses and conn["remote_port"] in ports:
                direct.append(conn)
            elif remote in server_addresses:
                other_ports.append(conn)
            elif ipaddress.ip_address(remote).is_loopback:
                loopback.append(conn)
            elif conn["remote_port"] in mail_only:
                elsewhere.append(conn)
            elif conn["remote_port"] in self.proxy_ports:
                proxies.append(conn)
            else:
                unrelated.append(conn)
        endpoint = self.endpoint_port()
        direct_mail = [c for c in direct if c["remote_port"] == endpoint and self.carries_data(c, last_t)]
        launch_t = self.launch_t()
        outside, outside_ignored = self.outside_tree(events, server_addresses, launch_t, header.get("script_pid"))
        networks: dict[tuple, dict] = {}
        for conn in unrelated + elsewhere + proxies:
            info = self.owners.lookup(conn["remote"]) if self.owners else {}
            key = (info.get("owner"), info.get("asn"), info.get("prefix"))
            entry = networks.setdefault(key, {
                "owner": key[0], "asn": key[1], "prefix": key[2], "as_holder": info.get("as_holder"),
                "microsoft": self.microsoft.registered(key[0], key[1], info.get("as_holder")), "connections": 0,
                "connections_measured": 0, "ports": set(), "processes": set(), "bytes_received": 0})
            entry["connections"] += 1
            entry["connections_measured"] += self.overlaps(conn, window)
            entry["ports"].add(conn["remote_port"])
            entry["processes"].add(conn.get("process") or "?")
            entry["bytes_received"] += conn["received"] or 0
        for entry in networks.values():
            entry["ports"] = sorted(entry["ports"])
            entry["processes"] = sorted(entry["processes"])
        measured_total = sum(self.overlaps(c, window) for c in connections if c not in loopback)
        measured_microsoft = sum(n["connections_measured"] for n in networks.values() if n["microsoft"])
        verify_path = self.run_dir / "verify.json"
        verify = json.loads(verify_path.read_text()) if verify_path.exists() else None
        inbox_complete, inbox_basis = self.inbox(verify)
        direct_bytes = sum(c["received"] or 0 for c in direct) if any(c["received"] is not None for c in direct) else None
        after_end = None
        if window and direct_bytes is not None:
            after_end = direct_bytes - sum(self.received_until(c, window["to_t"]) for c in direct)
        summary = {
            "version": 2, "run": self.run_dir.name, "app": header.get("app"), "source": header.get("source"),
            "poll_hz": header.get("poll_hz"),
            "mail_server": {"hosts": mail_server.get("hosts"), "addresses": sorted(server_addresses),
                            "ports": sorted(ports)},
            "window": window, "launch_t": launch_t,
            "direct_connections": len(direct),
            "direct_connections_measured": sum(self.overlaps(c, window) for c in direct),
            "direct_ports": dict(Counter(str(c["remote_port"]) for c in direct)),
            "direct_processes": sorted({c.get("process") or "?" for c in direct}),
            "direct_bytes_received": direct_bytes,
            "direct_bytes_after_measured_end": after_end,
            "mail_endpoint": {"protocol": self.protocol, "port": endpoint},
            "direct_mail_connections": len(direct_mail),
            "server_other_port_connections": len(other_ports),
            "outside_tree_connections": len(outside),
            "outside_tree_counted": outside,
            "outside_tree_not_counted": outside_ignored,
            "server_connections": len(direct) + len(other_ports) + len(outside),
            "mail_port_elsewhere": len(elsewhere),
            "mail_data_elsewhere": sum(1 for c in elsewhere if self.carries_data(c, last_t)),
            "proxy_connections": len(proxies),
            "loopback_connections": len(loopback),
            "remote_networks": sorted(networks.values(), key=lambda n: (-n["connections"], str(n["owner"]))),
            "connections_measured": measured_total,
            "remote_microsoft_share": (100 * measured_microsoft) // measured_total if measured_total else None,
            "inbox_complete": inbox_complete,
            "inbox_basis": inbox_basis,
            "direct_only": bool(direct_mail) and not proxies and not any(self.carries_data(c, last_t)
                                                                         for c in elsewhere),
        }
        (self.run_dir / "evidence.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        return summary


class SessionEvidence:
    """The per-comparison evidence facts of a result folder (the `env.<C>.*` narration values) and the session's
    evidence.json. Positive facts (connected directly for its mail) need every completed run, the warm-up
    included; negative ones (never connected to the mail server, no mail ports elsewhere) take every run with a
    network log, re-recorded attempts included, and are missing unless every completed run has one."""

    def __init__(self, comparisons: dict, cloud_apps: set[str], microsoft: MicrosoftNetworks | None = None):
        self.comparisons = comparisons
        self.cloud_apps = cloud_apps
        self.microsoft = microsoft or MicrosoftNetworks()

    @staticmethod
    def run_facts(run: dict, kind: str) -> dict:
        evidence = run.get("evidence") or {}
        return {"run": run["run"], "kind": kind, "logged": bool(evidence), **{k: evidence.get(k) for k in (
            "direct_connections", "direct_connections_measured", "direct_mail_connections", "server_connections",
            "outside_tree_connections", "direct_bytes_received", "direct_bytes_after_measured_end",
            "mail_port_elsewhere", "proxy_connections", "direct_only", "inbox_complete", "inbox_basis",
            "remote_microsoft_share")}, "remote_networks": [
            {k: n.get(k) for k in ("owner", "asn", "as_holder", "prefix", "microsoft", "connections",
                                   "connections_measured", "ports", "bytes_received")}
            for n in evidence.get("remote_networks", [])]}

    def side(self, side: dict) -> dict:
        done = ("ok", "timeout", "wrong-result")
        measured = [self.run_facts(r, "measured") for r in side["runs"] if r.get("status") in done]
        warmups = [self.run_facts(r, "warm-up") for r in side.get("warmups", []) if r.get("status") in done]
        others = [self.run_facts(r, "warm-up") for r in side.get("warmups", []) if r.get("status") not in done] + \
            [self.run_facts(r, "measured") for r in side["runs"] if r.get("status") not in done] + \
            [self.run_facts(r, "attempt") for r in side.get("failed_attempts", [])]
        completed = warmups + measured
        logged = [x for x in completed + others if x["logged"]]
        all_logged = bool(measured) and all(x["logged"] for x in completed)
        out = {"runs_with_evidence": sum(1 for x in measured if x["logged"]), "measured_runs": len(measured),
               "logged_runs": sum(1 for x in completed if x["logged"]), "all_runs_logged": all_logged,
               "runs": [x for x in completed + others if x["logged"]],
               "direct_only": 1 if all_logged and all(x["direct_only"] for x in completed) else 0,
               "direct_connections_max": max((x["direct_connections"] or 0 for x in logged), default=None),
               "server_connections_max": max((x["server_connections"] if x["server_connections"] is not None
                                              else x["direct_connections"] or 0 for x in logged), default=None)
               if all_logged else None,
               "mail_port_elsewhere_max": max((x["mail_port_elsewhere"] or 0 for x in logged), default=None)
               if all_logged else None,
               "inbox_complete": 1 if measured and all(x["inbox_complete"] for x in measured) else 0,
               "inbox_counted": 1 if measured and all(x["inbox_basis"] == "count" for x in measured) else 0}
        shares = [x["remote_microsoft_share"] for x in measured]
        if measured and None not in shares:
            out["remote_microsoft_share"] = min(shares)
        weights: Counter = Counter()
        holders = {}
        for x in measured:
            for n in x["remote_networks"]:
                if n["owner"] and n["connections_measured"]:
                    weights[(n["owner"], n["asn"])] += n["bytes_received"] or n["connections_measured"]
                    holders[(n["owner"], n["asn"])] = n.get("as_holder")
        if weights:
            (owner, asn), _ = weights.most_common(1)[0]
            out["remote_owner"], out["remote_asn"] = owner, asn
            out["remote_microsoft"] = int(self.microsoft.registered(owner, asn, holders.get((owner, asn))))
        return out

    @staticmethod
    def cpu_pressure(task: dict | None) -> float | None:
        """`env.<C>.cpu_pressure`: the highest CPU stall share (%, rounded up to 0.1) of the measured runs of both
        sides (run cpu-pressure.json, Linux); missing unless every measured run has one."""
        if task is None:
            return None
        runs = [r for name in ("left", "right") for r in task[name]["runs"]
                if r.get("status") in ("ok", "timeout", "wrong-result")]
        values = [(r.get("cpu_pressure") or {}).get("pct") for r in runs]
        if not runs or None in values:
            return None
        return math.ceil(max(values) * 10 - 1e-9) / 10

    def comparison(self, comparison_id: str, comparison: dict, task_id: str) -> dict:
        task = comparison["tasks"][task_id]
        sides = {name: self.side(task[name]) for name in ("left", "right")}
        values = {}
        for name, data in sides.items():
            if data["runs_with_evidence"]:
                values[f"{name}_direct_only"] = data["direct_only"]
            if task[name]["app"] in self.cloud_apps and data["runs_with_evidence"]:
                values[f"{name}_direct_connections"] = data["server_connections_max"]
                values[f"{name}_mail_port_elsewhere"] = data["mail_port_elsewhere_max"]
                values[f"{name}_logged_runs"] = data["logged_runs"] if data["all_runs_logged"] else None
                values[f"{name}_inbox_complete"] = data["inbox_complete"]
                values[f"{name}_inbox_counted"] = data["inbox_counted"]
                values[f"{name}_remote_microsoft"] = data.get("remote_microsoft", 0)
                values[f"{name}_remote_microsoft_share"] = data.get("remote_microsoft_share")
                if data.get("remote_owner"):
                    values[f"{name}_remote_owner"] = data["remote_owner"]
                    values[f"{name}_remote_asn"] = data["remote_asn"]
        return {"kind": "client", "task": task_id, "sides": sides,
                "values": {k: v for k, v in values.items() if v is not None},
                "rules": self.microsoft.describe(), "lines": self.lines(task, sides)}

    @staticmethod
    def lines(task: dict, sides: dict) -> list[str]:
        out = []
        for name, data in sides.items():
            app = task[name]["name"]
            if not data["runs_with_evidence"]:
                out.append(f"{app}: no network evidence")
                continue
            counts = [f"{x['run']} {x['server_connections'] if x['server_connections'] is not None else x['direct_connections']}"
                      for x in data["runs"]]
            out.append(f"{app}: connections to the mail server per run ({', '.join(counts)}); runs with a network "
                       f"log: {data['logged_runs']} (warm-up included){'' if data['all_runs_logged'] else ', not all'}; "
                       f"connected directly for its mail in every run: {'yes' if data['direct_only'] else 'no'}; "
                       f"Inbox complete in every measured run: {'yes' if data['inbox_complete'] else 'no'} (counted: "
                       f"{'yes' if data['inbox_counted'] else 'no'})")
            if data.get("remote_microsoft_share") is not None:
                out.append(f"{app}: share of its connections in the measured window to Microsoft's networks, lowest "
                           f"run: {data['remote_microsoft_share']} %")
            networks = Counter()
            for x in data["runs"]:
                for n in x["remote_networks"]:
                    networks[(n["owner"], n["asn"], n["prefix"])] += n["connections"]
            for (owner, asn, prefix), count in networks.most_common():
                out.append(f"{app}: also {count} connection(s) to {owner or 'unknown owner'} ({asn or '–'}, "
                           f"{prefix or '–'})")
        return out

    def summarize(self, task_id: str = "T1") -> dict:
        out = {"version": 2, "generated": datetime.now(timezone.utc).isoformat(), "comparisons": {}, "env": {}}
        for comparison_id, comparison in self.comparisons.items():
            if task_id not in comparison["tasks"]:
                continue
            result = self.comparison(comparison_id, comparison, task_id)
            out["comparisons"][comparison_id] = result
            for key, value in result["values"].items():
                out["env"][f"{comparison_id}.{key}"] = value
        return out
