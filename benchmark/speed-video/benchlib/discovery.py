"""Before a session: the mail configuration that the test address's domain publishes, asked the way the apps ask
and without any credentials, so the setup flows know whether an app can find another server than the account's."""

import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import quote, urlparse


class HttpAnswer:
    def __init__(self, status: int | None, text: str = "", location: str | None = None, error: str | None = None,
                 final_url: str | None = None):
        self.status = status
        self.text = text
        self.location = location
        self.error = error
        self.final_url = final_url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class WebClient:
    """GET (following redirects, like the apps) and POST (not following them: Autodiscover's redirect is an answer
    that names its target), without credentials or cookies."""

    def __init__(self, timeout_s: float = 15):
        self.timeout_s = timeout_s
        self.follow = urllib.request.build_opener()
        self.stay = urllib.request.build_opener(NoRedirect)

    def request(self, url: str, body: str | None = None, content_type: str | None = None) -> HttpAnswer:
        headers = {"User-Agent": "parula-speed-benchmark"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=body.encode() if body is not None else None, headers=headers,
                                         method="POST" if body is not None else "GET")
        opener = self.stay if body is not None else self.follow
        try:
            with opener.open(request, timeout=self.timeout_s) as response:
                final = response.geturl()
                return HttpAnswer(response.status, response.read(1_000_000).decode("utf-8", "replace"),
                                  final_url=final if final != url else None)
        except urllib.error.HTTPError as ex:
            return HttpAnswer(ex.code, location=ex.headers.get("Location") if 300 <= ex.code < 400 else None)
        except (urllib.error.URLError, OSError, ValueError) as ex:
            return HttpAnswer(None, error=str(getattr(ex, "reason", ex)))


class DnsOverHttps:
    """DNS records through public DNS-over-HTTPS resolvers (JSON API), the same on Linux and Windows without a DNS
    library. `None` when no resolver answered."""

    resolvers = ("https://dns.google/resolve", "https://cloudflare-dns.com/dns-query")

    def __init__(self, timeout_s: float = 15):
        self.timeout_s = timeout_s
        self.used = None

    def records(self, name: str, kind: str) -> list[str] | None:
        for resolver in self.resolvers:
            request = urllib.request.Request(f"{resolver}?name={quote(name)}&type={kind}",
                                             headers={"Accept": "application/dns-json",
                                                      "User-Agent": "parula-speed-benchmark"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                    answer = json.loads(response.read())
            except (urllib.error.URLError, OSError, ValueError):
                continue
            self.used = urlparse(resolver).hostname
            if answer.get("Status") not in (0, 3):
                return None
            return [str(record["data"]) for record in answer.get("Answer") or []
                    if record.get("type") == {"SRV": 33, "MX": 15}[kind]]
        return None


class PublishedConfig:
    """The configuration sources that Parula, Thunderbird and the Outlooks consult for an address: autoconfig
    (autoconfig.<domain> over HTTPS and HTTP, the domain's .well-known URL), the ISPDBs of Thunderbird and Parula,
    Exchange Autodiscover (POX at autodiscover.<domain> and at the domain, JSON v1.0), the DNS SRV records (RFC 6186,
    RFC 8314, Outlook's _autodiscover), and autoconfig and the ISPDBs of the MX host's domain when it differs. The
    address goes only where the apps send it, to the domain's own autoconfig and Autodiscover; the record shows it
    as {address}. Each source's answer is kept with the host names it gives a mail client."""

    def __init__(self, email: str, server_hosts: set[str], web: WebClient | None = None,
                 dns: DnsOverHttps | None = None):
        self.email = email
        self.domain = email.rpartition("@")[2].lower()
        self.server_hosts = {self.host_name(h) for h in server_hosts if h}
        self.web = web or WebClient()
        self.dns = dns or DnsOverHttps()

    @staticmethod
    def host_name(value: str) -> str:
        return str(value).strip().rstrip(".").lower()

    def shown(self, url: str) -> str:
        return url.replace(quote(self.email, safe=""), "{address}").replace(self.email, "{address}")

    def check(self) -> dict:
        domain, address = self.domain, quote(self.email, safe="")
        pox = (f'<?xml version="1.0" encoding="utf-8"?><Autodiscover xmlns="http://schemas.microsoft.com/exchange/'
               f'autodiscover/outlook/requestschema/2006"><Request><EMailAddress>{self.email}</EMailAddress>'
               f'<AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/'
               f'2006a</AcceptableResponseSchema></Request></Autodiscover>')
        web = [("autoconfig", f"https://autoconfig.{domain}/mail/config-v1.1.xml?emailaddress={address}", None),
               ("autoconfig (HTTP)", f"http://autoconfig.{domain}/mail/config-v1.1.xml?emailaddress={address}", None),
               ("autoconfig (.well-known)",
                f"https://{domain}/.well-known/autoconfig/mail/config-v1.1.xml?emailaddress={address}", None),
               ("ISPDB (Thunderbird)", f"https://autoconfig.thunderbird.net/v1.1/{domain}", None),
               ("ISPDB (Parula)", f"https://v1.ispdb.net/{domain}", None),
               ("Autodiscover (POX)", f"https://autodiscover.{domain}/autodiscover/autodiscover.xml", pox),
               ("Autodiscover (POX, domain)", f"https://{domain}/autodiscover/autodiscover.xml", pox),
               ("Autodiscover (JSON)", f"https://autodiscover.{domain}/autodiscover/autodiscover.json/v1.0/{address}"
                                       f"?Protocol=AutodiscoverV1", None)]
        srv = ["_imaps._tcp", "_imap._tcp", "_submissions._tcp", "_submission._tcp", "_autodiscover._tcp"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            mx = pool.submit(self.dns.records, domain, "MX")
            answers = [pool.submit(self.web_source, *source) for source in web]
            answers += [pool.submit(self.srv_source, f"{name}.{domain}") for name in srv]
            mx_hosts = mx.result()
            mx_domain = self.mx_domain(mx_hosts)
            if mx_domain and mx_domain != domain:
                answers += [pool.submit(self.web_source, f"{name} (MX domain {mx_domain})", url, None) for name, url in (
                    ("autoconfig", f"https://autoconfig.{mx_domain}/mail/config-v1.1.xml"),
                    ("ISPDB (Thunderbird)", f"https://autoconfig.thunderbird.net/v1.1/{mx_domain}"),
                    ("ISPDB (Parula)", f"https://v1.ispdb.net/{mx_domain}"))]
            sources = [answer.result() for answer in answers]
        other = sorted({h for s in sources for h in s.get("hosts", []) if h not in self.server_hosts})
        unchecked = [s["source"] for s in sources if s.get("unchecked")]
        if mx_hosts is None:
            unchecked.append("MX")
        return {"version": 1, "checked_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "domain": domain, "server_hosts": sorted(self.server_hosts),
                "mx": sorted({self.host_name(r.split()[-1]) for r in mx_hosts or []}), "dns": self.dns.used,
                "sources": sources, "other_hosts": other,
                "other_sources": [s["source"] for s in sources if set(s.get("hosts", [])) - self.server_hosts],
                "unchecked": unchecked, "guarded": bool(other or unchecked)}

    def mx_domain(self, records: list[str] | None) -> str | None:
        """The domain of the first MX host (e.g. "example.net" for "mx1.example.net"), as Thunderbird and Parula
        derive it."""
        hosts = sorted((r.split() for r in records or [] if len(r.split()) == 2), key=lambda r: int(r[0]))
        if not hosts:
            return None
        labels = self.host_name(hosts[0][1]).split(".")
        return ".".join(labels[1:]) if len(labels) > 2 else ".".join(labels)

    def web_source(self, name: str, url: str, body: str | None) -> dict:
        answer = self.web.request(url, body, "text/xml" if body else None)
        entry = {"source": name, "url": self.shown(url), "status": answer.status}
        if answer.error:
            entry["error"] = self.shown(answer.error)
        if answer.final_url:
            entry["redirected_to"] = self.shown(answer.final_url)
        hosts = []
        if answer.location:
            entry["redirect"] = self.shown(answer.location)
            hosts.append(urlparse(answer.location).hostname or "")
        elif answer.status == 200:
            try:
                hosts += self.hosts_in(answer.text)
            except (ElementTree.ParseError, ValueError):
                entry["error"] = "not a configuration"
        entry["hosts"] = sorted({self.host_name(h) for h in hosts if h})
        return entry

    def hosts_in(self, text: str) -> list[str]:
        """The servers a configuration names: autoconfig's incoming and outgoing host names, Autodiscover POX's
        servers and redirects, Autodiscover JSON's URL."""
        if text.lstrip().startswith("{"):
            url = json.loads(text).get("Url")
            return [urlparse(url).hostname or ""] if url else []
        root = ElementTree.fromstring(text)
        hosts = [(server.findtext("hostname") or "").replace("%EMAILDOMAIN%", self.domain)
                 for kind in ("incomingServer", "outgoingServer") for server in root.iter(kind)]
        for element in root.iter():
            tag = element.tag.rpartition("}")[2]
            value = (element.text or "").strip()
            if tag == "Server":
                hosts.append(value)
            elif tag == "RedirectUrl":
                hosts.append(urlparse(value).hostname or "")
            elif tag == "RedirectAddr":
                hosts.append(value.rpartition("@")[2])
        return hosts

    def srv_source(self, name: str) -> dict:
        records = self.dns.records(name, "SRV")
        entry = {"source": f"SRV {name.removesuffix('.' + self.domain)}", "name": name}
        if records is None:
            entry.update(unchecked=True, error="no DNS-over-HTTPS resolver answered", hosts=[])
            return entry
        targets = [r.split()[-1] for r in records if len(r.split()) == 4]
        entry["hosts"] = sorted({self.host_name(t) for t in targets if self.host_name(t)})
        return entry
