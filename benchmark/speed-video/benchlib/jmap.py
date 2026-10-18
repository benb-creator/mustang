import base64
import json
import time
import urllib.error
import urllib.request


class JMAPError(Exception):
    pass


class JMAPClient:
    using = ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail", "urn:ietf:params:jmap:blob"]

    def __init__(self, session_url: str, username: str, password: str, timeout: float = 120):
        self.session_url = session_url
        self.timeout = timeout
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}"}
        self._session = None

    def request(self, url: str, data: bytes | None = None, content_type: str = "application/json") -> dict:
        headers = dict(self.headers)
        if data is not None:
            headers["Content-Type"] = content_type
        for attempt in range(6):
            req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as ex:
                body = ex.read().decode(errors="replace")
                if ex.code in (429, 503) and attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise JMAPError(f"HTTP {ex.code} from {url}: {body[:500]}") from ex

    @property
    def session(self) -> dict:
        if self._session is None:
            self._session = self.request(self.session_url)
            if not self._session.get("primaryAccounts"):
                raise JMAPError("JMAP session has no accounts: wrong username or password?")
        return self._session

    @property
    def account_id(self) -> str:
        return self.session["primaryAccounts"]["urn:ietf:params:jmap:mail"]

    def capability(self, name: str) -> dict:
        return self.session["capabilities"].get(name, {})

    def call(self, method_calls: list) -> list:
        response = self.request(self.session["apiUrl"], json.dumps({"using": self.using,
                                                                   "methodCalls": method_calls}).encode())
        for name, args, tag in response["methodResponses"]:
            if name == "error" and not (args.get("type") == "invalidResultReference" and any(
                    r[0] == "Blob/upload" and r[1].get("notCreated") for r in response["methodResponses"])):
                raise JMAPError(f"{tag}: {args}")
        return response["methodResponses"]

    def one(self, method: str, args: dict) -> dict:
        return self.call([[method, {"accountId": self.account_id, **args}, "0"]])[0][1]

    def upload(self, data: bytes, content_type: str = "message/rfc822") -> str:
        url = self.session["uploadUrl"].replace("{accountId}", self.account_id)
        return self.request(url, data, content_type)["blobId"]

    def folders(self) -> list[dict]:
        return self.one("Mailbox/get", {"ids": None, "properties": ["id", "name", "parentId", "role",
                                                                    "totalEmails", "unreadEmails"]})["list"]

    def folder_paths(self) -> dict[str, dict]:
        boxes = {m["id"]: m for m in self.folders()}

        def path(m):
            return m["name"] if not m.get("parentId") else f"{path(boxes[m['parentId']])}/{m['name']}"
        return {path(m): m for m in boxes.values()}

    def ensure_folder(self, path: str, role: str | None) -> str:
        existing = self.folder_paths()
        if role:
            for m in existing.values():
                if m.get("role") == role:
                    return m["id"]
        if path in existing:
            return existing[path]["id"]
        parent_id = None
        if "/" in path:
            parent_id = self.ensure_folder(path.rsplit("/", 1)[0], None)
        create = {"name": path.rsplit("/", 1)[-1], "parentId": parent_id}
        if role:
            create["role"] = role
        result = self.one("Mailbox/set", {"create": {"m": create}})
        if "m" not in (result.get("created") or {}):
            raise JMAPError(f"Can't create folder {path}: {result.get('notCreated')}")
        return result["created"]["m"]["id"]

    def import_batch(self, items: list[dict], inline_limit: int) -> list[str]:
        """items: {raw, folder_id, keywords, received_at}; small messages go inline via Blob/upload."""
        calls = []
        uploads = {}
        emails = {}
        for n, item in enumerate(items):
            cid = f"e{n}"
            if len(item["raw"]) <= inline_limit:
                uploads[cid] = {"data": [{"data:asBase64": base64.b64encode(item["raw"]).decode()}],
                                "type": "message/rfc822"}
                blob_id = f"#{cid}"
            else:
                blob_id = self.upload(item["raw"])
            emails[cid] = {"blobId": blob_id, "mailboxIds": {item["folder_id"]: True},
                           "keywords": {k: True for k in item["keywords"]},
                           "receivedAt": item["received_at"].strftime("%Y-%m-%dT%H:%M:%SZ")}
        if uploads:
            calls.append(["Blob/upload", {"accountId": self.account_id, "create": uploads}, "u"])
        calls.append(["Email/import", {"accountId": self.account_id, "emails": emails}, "i"])
        responses = self.call(calls)
        if uploads and responses[0][1].get("notCreated"):
            errors = responses[0][1]["notCreated"]
            hint = ""
            if any(e.get("type") == "overQuota" for e in errors.values()):
                hint = (" — the server limits uploads per user and hour; on the dedicated benchmark instance raise "
                        "the JMAP uploadQuota and maxUploadCount (see README), or seed with --protocol imap")
            raise JMAPError(f"Blob/upload failed{hint}: {json.dumps(errors)[:500]}")
        result = responses[-1][1]
        if result.get("notCreated"):
            raise JMAPError(f"Email/import failed: {json.dumps(result['notCreated'])[:800]}")
        return [result["created"][f"e{n}"]["id"] for n in range(len(items))]

    def query_count(self, filter: dict) -> int:
        return int(self.one("Email/query", {"filter": filter, "calculateTotal": True, "limit": 1})["total"])

    def query_ids(self, filter: dict | None = None, page: int = 1000) -> list[str]:
        ids, position = [], 0
        while True:
            result = self.one("Email/query", {"filter": filter or {}, "position": position, "limit": page,
                                              "sort": [{"property": "receivedAt", "isAscending": True}]})
            ids += result["ids"]
            if len(result["ids"]) < page:
                return ids
            position += page

    def email_sizes(self, page: int = 500) -> dict[str, int]:
        sizes = {}
        ids = self.query_ids()
        for i in range(0, len(ids), page):
            for email in self.one("Email/get", {"ids": ids[i:i + page], "properties": ["id", "size"]})["list"]:
                sizes[email["id"]] = int(email["size"])
        return sizes

    def destroy_emails(self, ids: list[str], batch: int = 500):
        for i in range(0, len(ids), batch):
            self.one("Email/set", {"destroy": ids[i:i + batch]})

    def destroy_folders(self, ids: list[str]):
        if ids:
            self.one("Mailbox/set", {"destroy": ids, "onDestroyRemoveEmails": True})
