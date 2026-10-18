import time

from .corpus import CorpusGenerator, CorpusSpec
from .imap import IMAPAccount
from .jmap import JMAPClient


class SeedError(Exception):
    pass


class Seeder:
    def __init__(self, config, progress):
        self.config = config
        self.progress = progress
        self.generator = CorpusGenerator(CorpusSpec.from_dict(config.get("corpus")))

    @property
    def username(self) -> str:
        return self.config.get("account.username") or self.config.require("account.email")

    def jmap(self) -> JMAPClient:
        return JMAPClient(self.config.require("server.jmap_session_url"), self.username,
                          self.config.secret("account.password_env"))

    def imap(self) -> IMAPAccount:
        return IMAPAccount(self.config.require("server.imap.host"), int(self.config.get("server.imap.port", 993)),
                           bool(self.config.get("server.imap.tls", True)), self.username,
                           self.config.secret("account.password_env"))

    def seed(self, protocol: str = "jmap", resume: bool = False):
        started = time.monotonic()
        if protocol == "jmap":
            self.seed_jmap(resume)
        elif protocol == "imap":
            self.seed_imap(resume)
        else:
            raise SeedError(f"Unknown import protocol '{protocol}'")
        self.progress(f"Imported {self.generator.expected()['total']} messages via {protocol.upper()} "
                      f"in {time.monotonic() - started:.0f} s")

    def seed_jmap(self, resume: bool):
        client = self.jmap()
        max_request = int(client.capability("urn:ietf:params:jmap:core").get("maxSizeRequest", 10_000_000))
        max_blob = int(client.capability("urn:ietf:params:jmap:blob").get("maxSizeBlobSet", 0) or 0)
        budget = int(max_request * 0.7 / 1.37)
        inline_limit = min(budget, max_blob) if max_blob else budget
        max_objects = min(200, int(client.capability("urn:ietf:params:jmap:core").get("maxObjectsInSet", 500)))
        for folder in self.generator.spec.folders:
            mailbox_id = client.ensure_mailbox(folder.name, folder.role)
            start = client.query_count({"inMailbox": mailbox_id}) if resume else 0
            batch, batch_bytes = [], 0
            done = start
            for msg in self.generator.folder_messages(folder.name, start):
                inline = len(msg.raw) <= inline_limit
                if batch and (len(batch) >= max_objects or (inline and batch_bytes + len(msg.raw) > budget)):
                    client.import_batch(batch, inline_limit)
                    if (done + len(batch)) // 1000 > done // 1000:
                        self.progress(f"  {folder.name}: {done + len(batch)}/{folder.count}")
                    done += len(batch)
                    batch, batch_bytes = [], 0
                batch.append({"raw": msg.raw, "mailbox_id": mailbox_id, "keywords": msg.keywords,
                              "received_at": msg.received_at})
                batch_bytes += len(msg.raw) if inline else 0
            if batch:
                client.import_batch(batch, inline_limit)
            self.progress(f"  {folder.name}: {folder.count} messages")

    def seed_imap(self, resume: bool):
        account = self.imap()
        try:
            for folder in self.generator.spec.folders:
                name = account.ensure_folder(folder.name, folder.role)
                start = account.status(name)["MESSAGES"] if resume else 0
                for msg in self.generator.folder_messages(folder.name, start):
                    account.append(name, msg.raw, msg.keywords, msg.received_at)
                    if (msg.index + 1) % 1000 == 0:
                        self.progress(f"  {folder.name}: {msg.index + 1}/{folder.count}")
                self.progress(f"  {folder.name}: {folder.count} messages")
        finally:
            account.close()

    def verify(self, protocol: str = "jmap", search_wait_s: float = 120) -> dict:
        expected = self.generator.expected()
        report = {"protocol": protocol, "folders": {}, "planted": {}, "ok": True}
        if protocol == "jmap":
            client = self.jmap()
            paths = client.mailbox_paths()
            by_role = {m.get("role"): m for m in paths.values() if m.get("role")}
            for folder in self.generator.spec.folders:
                box = by_role.get(folder.role) or paths.get(folder.name)
                actual = None if box is None else client.query_count({"inMailbox": box["id"]})
                report["folders"][folder.name] = {"expected": folder.count, "actual": actual}

            def planted_counts():
                counts = {}
                for term, info in expected["planted"].items():
                    key = "subject" if info["field"] == "subject" else "text"
                    counts[term] = client.query_count({key: term})
                return counts
        else:
            account = self.imap()
            for folder in self.generator.spec.folders:
                name = account.server_name(folder.name, folder.role)
                try:
                    actual = account.status(name)["MESSAGES"]
                except Exception:
                    actual = None
                report["folders"][folder.name] = {"expected": folder.count, "actual": actual, "server_name": name}

            def planted_counts():
                counts = {}
                for term, info in expected["planted"].items():
                    key = "SUBJECT" if info["field"] == "subject" else "TEXT"
                    counts[term] = sum(account.search_count(account.server_name(f.name, f.role), term, key)
                                       for f in self.generator.spec.folders if f.count)
                return counts

        deadline = time.monotonic() + search_wait_s
        while True:
            counts = planted_counts()
            if all(counts[t] == info["count"] for t, info in expected["planted"].items()) \
                    or time.monotonic() > deadline:
                break
            time.sleep(3)
        for term, info in expected["planted"].items():
            report["planted"][term] = {"expected": info["count"], "actual": counts[term], "field": info["field"]}
        if protocol != "jmap":
            account.close()
        report["ok"] = all(v["expected"] == v["actual"] for v in report["folders"].values()) and \
            all(v["expected"] == v["actual"] for v in report["planted"].values())
        return report

    def wipe(self):
        allowed = self.config.get("server.snapshot.wipe_allowed_for")
        if not allowed or allowed != self.username:
            raise SeedError(f"Refusing to wipe {self.username}: set server.snapshot.wipe_allowed_for to exactly "
                            f"this username to allow wiping the benchmark account")
        client = self.jmap()
        ids = client.query_ids()
        client.destroy_emails(ids)
        paths = client.mailbox_paths()
        custom = sorted((p for p, m in paths.items() if not m.get("role")), key=lambda p: -p.count("/"))
        for path in custom:
            client.destroy_mailboxes([paths[path]["id"]])
        self.progress(f"Wiped {len(ids)} messages and {len(custom)} folders of {self.username}")
