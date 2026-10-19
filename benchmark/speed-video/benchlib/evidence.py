"""Client-side network evidence (spec v4): which processes of each app connected where, summarized per run and per
session. Raw addresses stay in each run's network.jsonl; the summaries publish owner, ASN and prefix only."""

import ipaddress
import json
import socket
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

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
        from urllib.parse import urlparse
        url = urlparse(server.jmap_session_url)
        ports = {server.imap_settings["port"], server.smtp_settings["port"], url.port or 443}
        return MailServerAddresses.resolve(server.mail_hostnames(), ports)


class RunEvidence:
    """evidence.json of one run, from its network.jsonl, driver.jsonl window, analysis.json and verify.json."""

    def __init__(self, run_dir: Path, owners: NetworkOwners | None, proxy_ports: set[int] | None = None,
                 probe_bytes: int = 65536):
        self.run_dir = Path(run_dir)
        self.owners = owners
        self.proxy_ports = set(proxy_ports or {1080, 3128})
        self.probe_bytes = probe_bytes

    def window(self) -> dict | None:
        analysis_path = self.run_dir / "analysis.json"
        if not analysis_path.exists():
            return None
        analysis = json.loads(analysis_path.read_text())
        return analysis.get("measured_window")

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

    def carries_data(self, conn: dict, last_t: float) -> bool:
        """A connection on a mail port that received more than a probe's few bytes, or whose byte count is unknown
        although it stayed open long enough to be read (a guessing app's probes are short and small)."""
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

    def summarize(self, mail_server: dict | None = None) -> dict:
        events = NetworkLog.read(self.run_dir / "network.jsonl")
        header = next((e for e in events if e["type"] == "header"), {})
        resolved = [e for e in events if e["type"] == "resolve"]
        if mail_server is None:
            logged = next((e for e in events if e["type"] == "mail_server"), {})
            addresses = sorted(set(logged.get("addresses") or []) |
                               {a for e in resolved for a in e.get("addresses", [])})
            mail_server = {"hosts": {e["host"]: e.get("addresses", []) for e in resolved}, "addresses": addresses,
                           "ports": logged.get("ports") or sorted(MailServerAddresses.standard_ports),
                           "mail_only_ports": logged.get("mail_only_ports") or
                           sorted(MailServerAddresses.mail_only_ports)}
        server_addresses = set(mail_server.get("addresses") or [])
        ports = set(mail_server.get("ports") or MailServerAddresses.standard_ports)
        mail_only = set(mail_server.get("mail_only_ports") or MailServerAddresses.mail_only_ports)
        window = self.window()
        connections = self.connections(events)
        last_t = max((e["t"] for e in events), default=0.0)
        direct, elsewhere, proxies, loopback, unrelated = [], [], [], [], []
        for conn in connections:
            remote = conn["remote"]
            if remote in server_addresses and conn["remote_port"] in ports:
                direct.append(conn)
            elif ipaddress.ip_address(remote).is_loopback:
                loopback.append(conn)
            elif conn["remote_port"] in mail_only:
                elsewhere.append(conn)
            elif conn["remote_port"] in self.proxy_ports:
                proxies.append(conn)
            else:
                unrelated.append(conn)
        networks: dict[tuple, dict] = {}
        for conn in unrelated + elsewhere + proxies:
            info = self.owners.lookup(conn["remote"]) if self.owners else {}
            key = (info.get("owner"), info.get("asn"), info.get("prefix"))
            entry = networks.setdefault(key, {"owner": key[0], "asn": key[1], "prefix": key[2], "as_holder":
                                              info.get("as_holder"), "connections": 0, "connections_measured": 0,
                                              "ports": set(), "processes": set(), "bytes_received": 0})
            entry["connections"] += 1
            entry["connections_measured"] += self.overlaps(conn, window)
            entry["ports"].add(conn["remote_port"])
            entry["processes"].add(conn.get("process") or "?")
            entry["bytes_received"] += conn["received"] or 0
        for entry in networks.values():
            entry["ports"] = sorted(entry["ports"])
            entry["processes"] = sorted(entry["processes"])
        verify_path = self.run_dir / "verify.json"
        verify = json.loads(verify_path.read_text()) if verify_path.exists() else None
        direct_bytes = sum(c["received"] or 0 for c in direct) if any(c["received"] is not None for c in direct) else None
        after_end = None
        if window and direct_bytes is not None:
            after_end = direct_bytes - sum(self.received_until(c, window["to_t"]) for c in direct)
        summary = {
            "version": 1, "run": self.run_dir.name, "app": header.get("app"), "source": header.get("source"),
            "poll_hz": header.get("poll_hz"),
            "mail_server": {"hosts": mail_server.get("hosts"), "addresses": sorted(server_addresses),
                            "ports": sorted(ports)},
            "window": window,
            "direct_connections": len(direct),
            "direct_connections_measured": sum(self.overlaps(c, window) for c in direct),
            "direct_ports": dict(Counter(str(c["remote_port"]) for c in direct)),
            "direct_processes": sorted({c.get("process") or "?" for c in direct}),
            "direct_bytes_received": direct_bytes,
            "direct_bytes_after_measured_end": after_end,
            "mail_port_elsewhere": len(elsewhere),
            "mail_data_elsewhere": sum(1 for c in elsewhere if self.carries_data(c, last_t)),
            "proxy_connections": len(proxies),
            "loopback_connections": len(loopback),
            "remote_networks": sorted(networks.values(), key=lambda n: (-n["connections"], str(n["owner"]))),
            "inbox_complete": verify.get("inbox_complete") if verify else None,
            "direct_only": bool(direct) and not proxies and not any(self.carries_data(c, last_t) for c in elsewhere),
        }
        (self.run_dir / "evidence.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        return summary


class SessionEvidence:
    """The per-comparison evidence facts of a result folder (the `env.<C>.*` narration values) and the session's
    evidence.json."""

    def __init__(self, comparisons: dict, cloud_apps: set[str]):
        self.comparisons = comparisons
        self.cloud_apps = cloud_apps

    @staticmethod
    def side(side: dict) -> dict:
        runs = [r for r in side["runs"] if r.get("status") in ("ok", "timeout", "wrong-result")]
        per_run = [{"run": r["run"], **{k: (r.get("evidence") or {}).get(k) for k in (
            "direct_connections", "direct_connections_measured", "direct_bytes_received",
            "direct_bytes_after_measured_end", "mail_port_elsewhere", "proxy_connections", "direct_only",
            "inbox_complete")}, "remote_networks": [
            {k: n.get(k) for k in ("owner", "asn", "prefix", "connections", "connections_measured", "ports",
                                   "bytes_received")} for n in (r.get("evidence") or {}).get("remote_networks", [])]}
            for r in runs]
        complete = bool(runs) and all(r.get("evidence") for r in runs)
        out = {"runs_with_evidence": sum(1 for r in runs if r.get("evidence")), "measured_runs": len(runs),
               "runs": per_run,
               "direct_only": 1 if complete and all(x["direct_only"] for x in per_run) else 0,
               "direct_connections_max": max((x["direct_connections"] or 0 for x in per_run), default=None),
               "inbox_complete": 1 if complete and all(x["inbox_complete"] for x in per_run) else 0}
        weights: Counter = Counter()
        for x in per_run:
            for n in x["remote_networks"]:
                if n["owner"] and n["connections_measured"]:
                    weights[(n["owner"], n["asn"])] += n["bytes_received"] or n["connections_measured"]
        if weights:
            (owner, asn), _ = weights.most_common(1)[0]
            out["remote_owner"], out["remote_asn"] = owner, asn
        return out

    def comparison(self, comparison_id: str, comparison: dict, task_id: str) -> dict:
        task = comparison["tasks"][task_id]
        sides = {name: self.side(task[name]) for name in ("left", "right")}
        values = {}
        for name, data in sides.items():
            if data["runs_with_evidence"]:
                values[f"{name}_direct_only"] = data["direct_only"]
            if task[name]["app"] in self.cloud_apps and data["runs_with_evidence"]:
                values[f"{name}_direct_connections"] = data["direct_connections_max"]
                values[f"{name}_inbox_complete"] = data["inbox_complete"]
                if data.get("remote_owner"):
                    values[f"{name}_remote_owner"] = data["remote_owner"]
                    values[f"{name}_remote_asn"] = data["remote_asn"]
        return {"kind": "client", "task": task_id, "sides": sides, "values": values,
                "lines": self.lines(task, sides)}

    @staticmethod
    def lines(task: dict, sides: dict) -> list[str]:
        out = []
        for name, data in sides.items():
            app = task[name]["name"]
            if not data["runs_with_evidence"]:
                out.append(f"{app}: no network evidence")
                continue
            counts = [x["direct_connections"] for x in data["runs"]]
            out.append(f"{app}: connections to the mail server per measured run {counts}; connected only to the "
                       f"mail server for mail: {'yes' if data['direct_only'] else 'no'}; Inbox complete in every "
                       f"measured run: {'yes' if data['inbox_complete'] else 'no'}")
            networks = Counter()
            for x in data["runs"]:
                for n in x["remote_networks"]:
                    networks[(n["owner"], n["asn"], n["prefix"])] += n["connections"]
            for (owner, asn, prefix), count in networks.most_common():
                out.append(f"{app}: also {count} connection(s) to {owner} ({asn}, {prefix})")
        return out

    def summarize(self, task_id: str = "T1") -> dict:
        out = {"version": 1, "generated": datetime.now(timezone.utc).isoformat(), "comparisons": {}, "env": {}}
        for comparison_id, comparison in self.comparisons.items():
            if task_id not in comparison["tasks"]:
                continue
            result = self.comparison(comparison_id, comparison, task_id)
            out["comparisons"][comparison_id] = result
            for key, value in result["values"].items():
                out["env"][f"{comparison_id}.{key}"] = value
        return out
