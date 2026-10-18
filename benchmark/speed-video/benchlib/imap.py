import imaplib
import re
import ssl


class IMAPError(Exception):
    pass


class IMAPAccount:
    special_use = {"inbox": None, "sent": "\\Sent", "archive": "\\Archive", "drafts": "\\Drafts",
                   "trash": "\\Trash", "junk": "\\Junk"}

    def __init__(self, host: str, port: int, tls: bool, username: str, password: str):
        if tls:
            self.conn = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context())
        else:
            self.conn = imaplib.IMAP4(host, port)
        self.check(self.conn.login(username, password))
        self._delimiter = None

    @staticmethod
    def check(result):
        status, data = result
        if status != "OK":
            raise IMAPError(f"IMAP error: {data}")
        return data

    def close(self):
        try:
            self.conn.logout()
        except (imaplib.IMAP4.error, OSError):
            pass

    @staticmethod
    def quote(name: str) -> str:
        return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def folders(self) -> list[tuple[str, str]]:
        """(flags, name) per folder."""
        out = []
        for line in self.check(self.conn.list()):
            text = line.decode() if isinstance(line, bytes) else str(line)
            m = re.match(r'\((?P<flags>[^)]*)\) (?P<delim>"[^"]*"|NIL) (?P<name>.+)$', text)
            if not m:
                continue
            delim = m.group("delim").strip('"')
            self._delimiter = self._delimiter or delim
            name = m.group("name").strip()
            if name.startswith('"'):
                name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            out.append((m.group("flags"), name))
        return out

    @property
    def delimiter(self) -> str:
        if self._delimiter is None:
            self.folders()
        return self._delimiter or "/"

    def server_name(self, path: str, role: str | None) -> str:
        if role == "inbox":
            return "INBOX"
        attr = self.special_use.get(role or "")
        if attr:
            for flags, name in self.folders():
                if attr.lower() in flags.lower():
                    return name
        return path.replace("/", self.delimiter)

    def ensure_folder(self, path: str, role: str | None) -> str:
        name = self.server_name(path, role)
        existing = {n for _, n in self.folders()}
        if name not in existing and name.upper() != "INBOX":
            parts = name.split(self.delimiter)
            for i in range(1, len(parts) + 1):
                partial = self.delimiter.join(parts[:i])
                if partial in existing:
                    continue
                attr = self.special_use.get(role or "") if i == len(parts) else None
                if attr and "CREATE-SPECIAL-USE" in self.conn.capabilities:
                    self.check(self.conn._simple_command("CREATE", self.quote(partial), f"(USE ({attr}))"))
                else:
                    self.check(self.conn.create(self.quote(partial)))
                existing.add(partial)
        return name

    def append(self, folder: str, raw: bytes, keywords: list[str], received_at):
        flag_map = {"$seen": "\\Seen", "$flagged": "\\Flagged", "$answered": "\\Answered", "$draft": "\\Draft"}
        flags = "(" + " ".join(flag_map.get(k, k) for k in keywords) + ")"
        date = imaplib.Time2Internaldate(received_at.timestamp())
        self.check(self.conn.append(self.quote(folder), flags, date, raw))

    def status(self, folder: str) -> dict:
        data = self.check(self.conn.status(self.quote(folder), "(MESSAGES UIDVALIDITY UIDNEXT UNSEEN)"))
        text = data[0].decode()
        return {k: int(v) for k, v in re.findall(r"(MESSAGES|UIDVALIDITY|UIDNEXT|UNSEEN) (\d+)", text)}

    def uids(self, folder: str) -> list[int]:
        self.check(self.conn.select(self.quote(folder), readonly=True))
        data = self.check(self.conn.uid("SEARCH", None, "ALL"))
        return [int(u) for u in data[0].split()]

    def search_count(self, folder: str, term: str, key: str = "TEXT") -> int:
        self.check(self.conn.select(self.quote(folder), readonly=True))
        data = self.check(self.conn.uid("SEARCH", "CHARSET", "UTF-8", key, self.quote(term)))
        return len(data[0].split())

    def delete_all(self, folder: str):
        count = self.status(folder)["MESSAGES"]
        self.check(self.conn.select(self.quote(folder)))
        if count:
            self.check(self.conn.store("1:*", "+FLAGS.SILENT", "(\\Deleted)"))
            self.check(self.conn.expunge())

    def delete_folder(self, folder: str):
        self.check(self.conn.delete(self.quote(folder)))
