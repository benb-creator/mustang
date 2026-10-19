import imaplib
import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .corpus import CorpusGenerator


class AccountError(Exception):
    pass


class AccountServer:
    """The test account on an existing mail server. Inputs: host name, e-mail address, password; the endpoints
    follow from the host (each can be overridden in the config). Nothing but this one account is ever touched."""

    def __init__(self, host: str, email: str, password: str, settings: dict | None = None, username: str | None = None,
                 ca_file: str | None = None):
        self.host = host
        self.email = email
        self.password = password
        self.settings = dict(settings or {})
        self.username = username or email
        self.ca_file = ca_file

    @classmethod
    def from_config(cls, config) -> "AccountServer":
        ca_file = config.get("server.ca_file")
        return cls(str(config.require("server.host")), str(config.require("account.email")),
                   config.secret("account.password_env"), config.get("server") or {},
                   config.get("account.username"), str(config.path(ca_file)) if ca_file else None)

    def ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context()
        if self.ca_file:
            context.load_verify_locations(cafile=self.ca_file)
        return context

    @property
    def imap_settings(self) -> dict:
        imap = dict(self.settings.get("imap") or {})
        return {"host": str(imap.get("host") or self.host), "port": int(imap.get("port", 993)),
                "tls": bool(imap.get("tls", True))}

    @property
    def smtp_settings(self) -> dict:
        smtp = dict(self.settings.get("smtp") or {})
        return {"host": str(smtp.get("host") or self.host), "port": int(smtp.get("port", 465))}

    @property
    def jmap_session_url(self) -> str:
        return str(self.settings.get("jmap_session_url") or f"https://{self.host}/.well-known/jmap")

    def endpoints(self) -> dict:
        return {"host": self.host, "jmap_session_url": self.jmap_session_url, "imap": self.imap_settings,
                "smtp": self.smtp_settings}

    def mail_hostnames(self) -> set[str]:
        from urllib.parse import urlparse
        names = {self.host, self.imap_settings["host"], self.smtp_settings["host"]}
        names.add(urlparse(self.jmap_session_url).hostname or self.host)
        names.update(str(h) for h in self.settings.get("extra_hostnames") or [])
        return {n for n in names if n}

    def imap(self) -> "ImapSession":
        return ImapSession(self.imap_settings, self.username, self.password, self.ssl_context())

    @property
    def email_domain(self) -> str:
        return self.email.rsplit("@", 1)[-1]


class ImapSession:
    def __init__(self, settings: dict, username: str, password: str, context: ssl.SSLContext):
        self.settings = settings
        self.username = username
        self.password = password
        self.context = context
        if settings["tls"]:
            self.conn = imaplib.IMAP4_SSL(settings["host"], settings["port"], ssl_context=context, timeout=120)
        else:
            self.conn = imaplib.IMAP4(settings["host"], settings["port"], timeout=120)
        self.check(self.conn.login(username, password))
        self.capabilities = set(self.check(self.conn.capability())[0].decode().upper().split())

    @staticmethod
    def check(result):
        status, data = result
        if status != "OK":
            raise AccountError(f"IMAP: {status} {data}")
        return data

    @staticmethod
    def quote(name: str) -> str:
        return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def close(self):
        try:
            self.conn.logout()
        except (imaplib.IMAP4.error, OSError):
            pass

    def folders(self) -> list[dict]:
        out = []
        for line in self.check(self.conn.list()):
            if line is None:
                continue
            text = line.decode() if isinstance(line, bytes) else str(line)
            m = re.match(r'\((?P<flags>[^)]*)\) (?P<delim>"[^"]*"|NIL) (?P<name>.+)$', text)
            if not m:
                continue
            name = m.group("name").strip()
            if name.startswith('"'):
                name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            flags = {f.lower() for f in m.group("flags").split()}
            special_use = {"\\sent", "\\drafts", "\\trash", "\\junk", "\\archive", "\\all", "\\flagged", "\\important"}
            out.append({"name": name, "flags": flags, "delimiter": m.group("delim").strip('"'),
                        "special_use": next((f for f in flags if f in special_use), None)})
        return out

    def foreign_prefixes(self) -> list[str]:
        """Prefixes of the other users' and the shared namespaces (RFC 2342): folders there aren't this account's."""
        if "NAMESPACE" not in self.capabilities:
            return []
        text = b" ".join(x for x in self.check(self.conn.namespace()) if isinstance(x, bytes)).decode(errors="replace")
        groups, depth, begin = [], 0, 0
        for i, char in enumerate(text):
            if char == "(":
                begin = i if depth == 0 else begin
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    groups.append(text[begin:i + 1])
            elif depth == 0 and text.startswith("NIL", i):
                groups.append("NIL")
        return [prefix for group in groups[1:3] for prefix in re.findall(r'\("([^"]*)"', group) if prefix]

    def messages(self, folder: str, batch: int = 5000) -> list[dict]:
        """uid, message_id, flags and size of every message in the folder."""
        status = self.check(self.conn.status(self.quote(folder), "(MESSAGES UIDNEXT)"))[0].decode()
        values = dict((k, int(v)) for k, v in re.findall(r"(MESSAGES|UIDNEXT) (\d+)", status))
        if not values.get("MESSAGES"):
            return []
        self.check(self.conn.select(self.quote(folder), readonly=True))
        out = []
        for low in range(1, max(values.get("UIDNEXT", 1), 2), batch):
            data = self.check(self.conn.uid("FETCH", f"{low}:{low + batch - 1}",
                                            "(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])"))
            for item in data:
                if not isinstance(item, tuple):
                    continue
                head = item[0].decode(errors="replace")
                uid = re.search(r"UID (\d+)", head)
                if not uid:
                    continue
                flags = re.search(r"FLAGS \(([^)]*)\)", head)
                size = re.search(r"RFC822\.SIZE (\d+)", head)
                message_id = re.search(rb"(?im)^message-id:\s*(<[^>\r\n]*>)", item[1] or b"")
                out.append({"uid": int(uid.group(1)), "flags": set((flags.group(1) if flags else "").split()),
                            "size": int(size.group(1)) if size else None,
                            "message_id": message_id.group(1).decode() if message_id else None})
        self.conn.unselect() if "UNSELECT" in self.capabilities else self.conn.close()
        return out

    def store_flags(self, folder: str, changes: list[tuple[int, set, set]]):
        """changes: (uid, flags to add, flags to remove)."""
        if not changes:
            return
        self.check(self.conn.select(self.quote(folder)))
        groups: dict[tuple, list[int]] = {}
        for uid, add, remove in changes:
            groups.setdefault((tuple(sorted(add)), tuple(sorted(remove))), []).append(uid)
        for (add, remove), uids in groups.items():
            for chunk in Chunks.of(uids, 500):
                uid_set = ",".join(str(u) for u in chunk)
                if add:
                    self.check(self.conn.uid("STORE", uid_set, "+FLAGS.SILENT", "(" + " ".join(add) + ")"))
                if remove:
                    self.check(self.conn.uid("STORE", uid_set, "-FLAGS.SILENT", "(" + " ".join(remove) + ")"))
        self.unselect()

    def delete_uids(self, folder: str, uids: list[int]):
        if not uids:
            return
        self.check(self.conn.select(self.quote(folder)))
        for chunk in Chunks.of(uids, 500):
            uid_set = ",".join(str(u) for u in chunk)
            self.check(self.conn.uid("STORE", uid_set, "+FLAGS.SILENT", "(\\Deleted)"))
            if "UIDPLUS" in self.capabilities:
                self.check(self.conn.uid("EXPUNGE", uid_set))
            else:
                self.check(self.conn.expunge())
        self.unselect()

    def move_uids(self, folder: str, uids: list[int], target: str):
        if not uids:
            return
        self.check(self.conn.select(self.quote(folder)))
        for chunk in Chunks.of(uids, 500):
            uid_set = ",".join(str(u) for u in chunk)
            if "MOVE" in self.capabilities:
                self.check(self.conn.uid("MOVE", uid_set, self.quote(target)))
            else:
                self.check(self.conn.uid("COPY", uid_set, self.quote(target)))
                self.check(self.conn.uid("STORE", uid_set, "+FLAGS.SILENT", "(\\Deleted)"))
                self.check(self.conn.expunge())
        self.unselect()

    def create_folder(self, name: str, special_use: str | None):
        if special_use and "CREATE-SPECIAL-USE" in self.capabilities:
            self.check(self.conn._simple_command("CREATE", self.quote(name), f"(USE ({SpecialUse.label(special_use)}))"))
        else:
            self.check(self.conn.create(self.quote(name)))

    def delete_folder(self, name: str):
        self.check(self.conn.delete(self.quote(name)))

    def unselect(self):
        if "UNSELECT" in self.capabilities:
            self.conn.unselect()
        else:
            self.conn.close()

    @staticmethod
    def flags_for(keywords: list[str]) -> set[str]:
        flag_of_keyword = {"$seen": "\\Seen", "$flagged": "\\Flagged", "$answered": "\\Answered", "$draft": "\\Draft"}
        return {flag_of_keyword.get(k, k) for k in keywords}


class SpecialUse:
    of_role = {"sent": "\\sent", "drafts": "\\drafts", "trash": "\\trash", "junk": "\\junk", "archive": "\\archive"}

    @staticmethod
    def label(attribute: str) -> str:
        return "\\" + attribute.lstrip("\\").capitalize()


class Chunks:
    @staticmethod
    def of(items: list, size: int):
        for i in range(0, len(items), size):
            yield items[i:i + size]


@dataclass
class ExpectedMessage:
    folder: str
    index: int
    message_id: str
    flags: set


@dataclass
class AccountState:
    """What the account holds, compared with the corpus."""
    folders: dict = field(default_factory=dict)
    corpus_folder_names: dict = field(default_factory=dict)
    missing: list = field(default_factory=list)
    duplicates: dict = field(default_factory=dict)
    misplaced: dict = field(default_factory=dict)
    foreign: dict = field(default_factory=dict)
    flag_changes: dict = field(default_factory=dict)
    extra_folders: list = field(default_factory=list)
    missing_folders: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.duplicates or self.misplaced or self.foreign or self.flag_changes
                    or self.extra_folders or self.missing_folders)

    def summary(self, expected_counts: dict) -> dict:
        def count(by_folder: dict) -> int:
            return sum(len(v) for v in by_folder.values())
        return {"ok": self.ok,
                "folders": {name: {"expected": expected_counts.get(name, 0), "actual": self.counts.get(name, 0),
                                   "server_name": self.corpus_folder_names.get(name)} for name in expected_counts},
                "missing_messages": len(self.missing), "duplicate_messages": count(self.duplicates),
                "misplaced_messages": count(self.misplaced), "foreign_messages": count(self.foreign),
                "flag_differences": count(self.flag_changes), "extra_folders": list(self.extra_folders),
                "missing_folders": list(self.missing_folders)}


class AccountCheck:
    """Compares the account with the corpus over IMAP (every message by its Message-ID, its folder and its flags)
    and repairs differences over the protocol: missing messages appended again, duplicates and messages that
    aren't from the corpus deleted, moved messages moved back, flags restored, folders an app created removed."""

    def __init__(self, server: AccountServer, generator: CorpusGenerator, progress=print):
        self.server = server
        self.generator = generator
        self.progress = progress
        self._expected = None

    def expected(self) -> dict[str, ExpectedMessage]:
        if self._expected is None:
            self._expected = {}
            for folder in self.generator.spec.folders:
                for i in range(folder.count):
                    message_id = self.generator.message_id(folder.name, i)
                    self._expected[message_id] = ExpectedMessage(
                        folder.name, i, message_id, ImapSession.flags_for(self.generator.keywords(folder.name, i)))
        return self._expected

    def expected_counts(self) -> dict[str, int]:
        return {f.name: f.count for f in self.generator.spec.folders}

    def corpus_folder_names(self, folders: list[dict]) -> dict[str, str | None]:
        """Server folder name of each corpus folder: Inbox → INBOX, the others by their special-use role."""
        names = {}
        by_use = {f["special_use"]: f["name"] for f in folders if f["special_use"]}
        existing = {f["name"] for f in folders}
        for folder in self.generator.spec.folders:
            if folder.role == "inbox":
                names[folder.name] = "INBOX"
            elif folder.role in SpecialUse.of_role and SpecialUse.of_role[folder.role] in by_use:
                names[folder.name] = by_use[SpecialUse.of_role[folder.role]]
            else:
                delimiter = folders[0]["delimiter"] if folders else "/"
                name = folder.name.replace("/", delimiter)
                names[folder.name] = name if name in existing else None
        return names

    @staticmethod
    def comparable(flags: set) -> set:
        return {f for f in flags if f.lower() != "\\recent"}

    def inspect(self, imap: ImapSession) -> AccountState:
        state = AccountState()
        folders = imap.folders()
        state.corpus_folder_names = self.corpus_folder_names(folders)
        state.missing_folders = [name for name, server_name in state.corpus_folder_names.items() if server_name is None]
        corpus_names = {n for n in state.corpus_folder_names.values() if n}
        expected = self.expected()
        seen: dict[str, tuple[str, int]] = {}
        foreign_prefixes = imap.foreign_prefixes()
        for folder in folders:
            name = folder["name"]
            if "\\noselect" in folder["flags"] or "\\nonexistent" in folder["flags"] or \
                    any(name.startswith(prefix) for prefix in foreign_prefixes):
                continue
            is_corpus = name in corpus_names or name.upper() == "INBOX"
            if not is_corpus and not folder["special_use"]:
                state.extra_folders.append(name)
            corpus_name = next((c for c, s in state.corpus_folder_names.items() if s == name), None)
            messages = imap.messages(name)
            state.folders[name] = messages
            state.counts[corpus_name or name] = len(messages)
            for message in messages:
                info = expected.get(message["message_id"] or "")
                if info is None:
                    state.foreign.setdefault(name, []).append(message["uid"])
                    continue
                if message["message_id"] in seen:
                    state.duplicates.setdefault(name, []).append(message["uid"])
                    continue
                seen[message["message_id"]] = (name, message["uid"])
                if state.corpus_folder_names.get(info.folder) != name:
                    state.misplaced.setdefault(name, []).append((message["uid"], info.folder))
                    continue
                actual = self.comparable(message["flags"])
                if actual != info.flags:
                    state.flag_changes.setdefault(name, []).append((message["uid"], info.flags - actual,
                                                                    actual - info.flags))
        state.missing = [info for message_id, info in expected.items() if message_id not in seen]
        return state

    def run(self, repair: bool = True, allow_foreign: bool = True) -> dict:
        started = time.monotonic()
        imap = self.server.imap()
        try:
            state = self.inspect(imap)
            report = {"version": 1, "checked_utc": datetime.now(timezone.utc).isoformat(), "protocol": "imap",
                      "before": state.summary(self.expected_counts()), "repairs": [], "after": None}
            if not state.ok and repair:
                if state.foreign and not allow_foreign:
                    raise AccountError(
                        f"The account holds {sum(len(v) for v in state.foreign.values())} messages that aren't from "
                        f"the benchmark corpus. It must be a dedicated test account; pass --delete-foreign to "
                        f"delete them")
                report["repairs"] = self.repair(imap, state)
                state = self.inspect(imap)
                report["after"] = state.summary(self.expected_counts())
            report["ok"] = state.ok
            report["seconds"] = round(time.monotonic() - started, 1)
            return report
        finally:
            imap.close()

    def repair(self, imap: ImapSession, state: AccountState) -> list[dict]:
        repairs = []
        for name in state.missing_folders:
            role = next(f.role for f in self.generator.spec.folders if f.name == name)
            imap.create_folder(name, SpecialUse.of_role.get(role or ""))
            repairs.append({"what": "folder created", "folder": name})
        if state.missing_folders:
            state.corpus_folder_names = self.corpus_folder_names(imap.folders())
        for name, entries in state.misplaced.items():
            by_target: dict[str, list[int]] = {}
            for uid, corpus_folder in entries:
                by_target.setdefault(state.corpus_folder_names[corpus_folder], []).append(uid)
            for target, uids in by_target.items():
                imap.move_uids(name, uids, target)
                repairs.append({"what": "messages moved back", "from": name, "to": target, "count": len(uids)})
        for name, uids in state.duplicates.items():
            imap.delete_uids(name, uids)
            repairs.append({"what": "duplicates deleted", "folder": name, "count": len(uids)})
        for name, uids in state.foreign.items():
            imap.delete_uids(name, uids)
            repairs.append({"what": "messages not from the corpus deleted", "folder": name, "count": len(uids)})
        for name, changes in state.flag_changes.items():
            imap.store_flags(name, changes)
            repairs.append({"what": "flags restored", "folder": name, "count": len(changes)})
        for name in sorted(state.extra_folders, key=lambda n: -n.count("/")):
            imap.delete_folder(name)
            repairs.append({"what": "folder deleted", "folder": name})
        if state.missing:
            appender = PipelinedAppender(self.server)
            try:
                count = appender.append_all(self.missing_messages(state), self.progress)
            finally:
                appender.close()
            repairs.append({"what": "messages appended", "count": count})
        return repairs

    def missing_messages(self, state: AccountState):
        for info in sorted(state.missing, key=lambda m: (m.folder, m.index)):
            message = self.generator.generate(info.folder, info.index)
            yield state.corpus_folder_names[info.folder], message


class PipelinedAppender:
    """IMAP APPEND with non-synchronizing literals (LITERAL+), many commands in flight on one connection: the
    normal user path of every IMAP server, fast enough for 30,000 messages."""

    def __init__(self, server: AccountServer, window: int = 32, window_bytes: int = 16_000_000):
        settings = server.imap_settings
        raw = socket.create_connection((settings["host"], settings["port"]), timeout=120)
        self.sock = server.ssl_context().wrap_socket(raw, server_hostname=settings["host"]) if settings["tls"] else raw
        self.file = self.sock.makefile("rb")
        self.window = window
        self.window_bytes = window_bytes
        self.tag = 0
        self.read_line()
        capabilities = self.command(b"CAPABILITY")
        self.literal_plus = any(b"LITERAL+" in line.upper() for line in capabilities)
        self.login(server.username, server.password)

    def read_line(self) -> bytes:
        line = self.file.readline()
        if not line:
            raise AccountError("IMAP connection closed by the server")
        return line

    def next_tag(self) -> bytes:
        self.tag += 1
        return b"P%d" % self.tag

    def command(self, text: bytes) -> list[bytes]:
        tag = self.next_tag()
        self.sock.sendall(tag + b" " + text + b"\r\n")
        lines = []
        while True:
            line = self.read_line()
            if line.startswith(tag + b" "):
                if not line[len(tag) + 1:].upper().startswith(b"OK"):
                    raise AccountError(f"IMAP {text.split()[0].decode()}: {line.decode(errors='replace').strip()}")
                return lines
            lines.append(line)

    def login(self, username: str, password: str):
        def literal(value: str) -> bytes:
            data = value.encode()
            return b"{%d+}\r\n" % len(data) + data
        if not self.literal_plus:
            quoted = '"' + password.replace("\\", "\\\\").replace('"', '\\"') + '"'
            self.command(b"LOGIN " + ImapSession.quote(username).encode() + b" " + quoted.encode())
            return
        self.command(b"LOGIN " + literal(username) + b" " + literal(password))

    def append_all(self, messages, progress=None) -> int:
        """messages: (server folder name, CorpusMessage); returns the number appended."""
        if not self.literal_plus:
            return self.append_one_by_one(messages, progress)
        in_flight: dict[bytes, int] = {}
        done = 0
        started = time.monotonic()
        for folder, message in messages:
            while in_flight and (len(in_flight) >= self.window or sum(in_flight.values()) > self.window_bytes):
                self.collect(in_flight)
                done += 1
                self.report(progress, done, started)
            tag = self.next_tag()
            flags = " ".join(sorted(ImapSession.flags_for(message.keywords)))
            date = imaplib.Time2Internaldate(message.received_at.timestamp())
            header = b"%s APPEND %s (%s) %s {%d+}\r\n" % (tag, ImapSession.quote(folder).encode(), flags.encode(),
                                                          date.encode(), len(message.raw))
            self.sock.sendall(header + message.raw + b"\r\n")
            in_flight[tag] = len(message.raw)
        while in_flight:
            self.collect(in_flight)
            done += 1
            self.report(progress, done, started)
        return done

    def collect(self, in_flight: dict[bytes, int]):
        while True:
            line = self.read_line()
            tag = line.split(b" ", 1)[0]
            if tag in in_flight:
                del in_flight[tag]
                if not line[len(tag) + 1:].upper().startswith(b"OK"):
                    raise AccountError(f"IMAP APPEND: {line.decode(errors='replace').strip()}")
                return

    def append_one_by_one(self, messages, progress=None) -> int:
        done = 0
        started = time.monotonic()
        for folder, message in messages:
            tag = self.next_tag()
            flags = " ".join(sorted(ImapSession.flags_for(message.keywords)))
            date = imaplib.Time2Internaldate(message.received_at.timestamp())
            self.sock.sendall(b"%s APPEND %s (%s) %s {%d}\r\n" % (tag, ImapSession.quote(folder).encode(),
                                                                  flags.encode(), date.encode(), len(message.raw)))
            line = self.read_line()
            if not line.startswith(b"+"):
                raise AccountError(f"IMAP APPEND: {line.decode(errors='replace').strip()}")
            self.sock.sendall(message.raw + b"\r\n")
            self.collect({tag: len(message.raw)})
            done += 1
            self.report(progress, done, started)
        return done

    @staticmethod
    def report(progress, done: int, started: float):
        if progress and done % 1000 == 0:
            progress(f"  appended {done} messages ({done / max(time.monotonic() - started, 0.001):.0f}/s)")

    def close(self):
        try:
            self.command(b"LOGOUT")
        except (AccountError, OSError):
            pass
        self.sock.close()


class AccountSeeder:
    """Seeds the corpus once over the network (IMAP APPEND, pipelined). Idempotent and resumable: every pass reads
    which corpus messages the account already holds (by Message-ID) and appends only the missing ones, so an
    interrupted run continues where it stopped and never duplicates."""

    def __init__(self, server: AccountServer, generator: CorpusGenerator, progress=print):
        self.check = AccountCheck(server, generator, progress)
        self.progress = progress

    def seed(self, allow_foreign: bool = False, passes: int = 3) -> dict:
        started = time.monotonic()
        imap = self.check.server.imap()
        try:
            state = self.check.inspect(imap)
        finally:
            imap.close()
        foreign = sum(len(v) for v in state.foreign.values())
        if foreign and not allow_foreign:
            raise AccountError(f"The account holds {foreign} messages that aren't from the benchmark corpus. It must "
                               f"be a dedicated test account; pass --delete-foreign to delete them")
        self.progress(f"  the account holds {sum(state.counts.values())} messages, {len(state.missing)} of the corpus "
                      f"are missing")
        report = None
        for attempt in range(passes):
            try:
                report = self.check.run(repair=True)
            except (AccountError, OSError, imaplib.IMAP4.error) as ex:
                if attempt + 1 == passes:
                    raise
                self.progress(f"  pass {attempt + 1} stopped ({ex}); continuing")
                time.sleep(5)
                continue
            if report["ok"]:
                break
        report["seed_seconds"] = round(time.monotonic() - started, 1)
        return report


class AccountSession:
    """What a run needs from the account: the check/repair before it, what the probes expect, and the mail
    server's addresses at run time."""

    def __init__(self, server: AccountServer, generator: CorpusGenerator, progress=print):
        self.server = server
        self.generator = generator
        self.check = AccountCheck(server, generator, progress)
        self._expected = None

    @property
    def expected(self) -> dict:
        if self._expected is None:
            inbox = next(f for f in self.generator.spec.folders if f.role == "inbox")
            last = inbox.count - 1
            unread = sum(1 for i in range(inbox.count) if "$seen" not in self.generator.keywords(inbox.name, i))
            self._expected = {"inbox_messages": inbox.count, "inbox_unread": unread,
                              "inbox_oldest_subject": self.generator.subject(inbox.name, 0),
                              "inbox_oldest_message_id": self.generator.message_id(inbox.name, 0),
                              "inbox_newest_subject": self.generator.subject(inbox.name, last),
                              "inbox_newest_message_id": self.generator.message_id(inbox.name, last)}
        return self._expected

    def mail_server(self) -> dict:
        from .evidence import MailServerAddresses
        return MailServerAddresses.for_server(self.server)
