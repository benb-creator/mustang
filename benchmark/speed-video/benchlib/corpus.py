import base64
import hashlib
import json
import math
import quopri
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Iterator

from .attachments import Attachment, SyntheticFiles
from .textgen import TextGenerator


@dataclass
class FolderSpec:
    name: str
    count: int
    role: str | None = None
    days_back_from: float = 3650
    days_back_to: float = 0
    seen_ratio: float = 0.95
    flagged_ratio: float = 0.02


@dataclass
class PlantedTerm:
    term: str
    count: int
    field: str = "body"


@dataclass
class CorpusSpec:
    """Named profiles: `inbox-30k` (default, the first videos: 30,000 messages in the Inbox, exactly 1 % of them with
    one attachment of exactly 1,000,000 bytes, the other standard folders empty) and `multi-folder` (T2–T7: ten years
    of mail in several folders, 15 % with 1–3 attachments of 20 KB–5 MB). Config keys override the profile."""

    profile: str = "inbox-30k"
    seed: int = 20261018
    owner_name: str = "Robin Sample"
    owner_address: str = "robin.sample@example.com"
    end_date: datetime = datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc)
    folders: list = field(default_factory=list)
    attachment_ratio: float = 0.15
    attachment_messages: int | None = None
    attachment_size: int = 1_000_000
    inline_image_ratio: float = 0.03
    html_ratio: float = 0.7
    attachment_min: int = 20_000
    attachment_max: int = 5_000_000
    large_from: int = 1_000_000
    large_share: float = 0.10
    planted: list = field(default_factory=list)

    profiles = {
        "inbox-30k": {"attachment_messages": 300, "attachment_size": 1_000_000, "inline_image_ratio": 0.0},
        "multi-folder": {},
    }

    @classmethod
    def default_folders(cls, profile: str) -> list[FolderSpec]:
        if profile == "inbox-30k":
            return [
                FolderSpec("Inbox", 30000, "inbox", 1095, 0, 0.9, 0.02),
                FolderSpec("Sent", 0, "sent"),
                FolderSpec("Drafts", 0, "drafts"),
                FolderSpec("Archive", 0, "archive"),
                FolderSpec("Junk", 0, "junk"),
                FolderSpec("Trash", 0, "trash"),
            ]
        return [
            FolderSpec("Inbox", 3000, "inbox", 90, 0, 0.8, 0.03),
            FolderSpec("Archive", 20000, "archive", 3650, 90, 0.98, 0.02),
            FolderSpec("Sent", 4000, "sent", 3650, 0, 1.0, 0.01),
            FolderSpec("Projects/Alpha", 800, None, 730, 0, 0.95, 0.03),
            FolderSpec("Projects/Beta", 600, None, 730, 0, 0.95, 0.03),
            FolderSpec("Projects/Gamma", 600, None, 730, 0, 0.95, 0.03),
            FolderSpec("Projects/Move-me", 1000, None, 365, 0, 0.9, 0.02),
            FolderSpec("Projects/Done", 0, None, 365, 0, 1.0, 0.0),
        ]

    @classmethod
    def from_dict(cls, d: dict | None) -> "CorpusSpec":
        d = dict(d or {})
        spec = cls()
        spec.profile = str(d.get("profile", spec.profile))
        if spec.profile not in cls.profiles:
            raise ValueError(f"Unknown corpus profile '{spec.profile}'. Known: {', '.join(cls.profiles)}")
        values = {**cls.profiles[spec.profile], **d}
        for key in ("seed", "owner_name", "owner_address", "attachment_ratio", "inline_image_ratio", "html_ratio",
                    "attachment_min", "attachment_max", "large_from", "large_share", "attachment_size"):
            if key in values:
                setattr(spec, key, type(getattr(spec, key))(values[key]))
        if values.get("attachment_messages") is not None:
            spec.attachment_messages = int(values["attachment_messages"])
        if "end_date" in values:
            spec.end_date = datetime.fromisoformat(str(values["end_date"])).astimezone(timezone.utc)
        spec.folders = [FolderSpec(**f) for f in values["folders"]] if "folders" in values else \
            cls.default_folders(spec.profile)
        spec.planted = [PlantedTerm(**p) for p in values["planted"]] if "planted" in values else [
            PlantedTerm("kumquat", 250, "body"), PlantedTerm("Zanzibar", 40, "subject")]
        return spec

    def to_dict(self) -> dict:
        return {
            "profile": self.profile, "seed": self.seed, "owner_name": self.owner_name,
            "owner_address": self.owner_address, "end_date": self.end_date.isoformat(),
            "attachment_ratio": self.attachment_ratio, "attachment_messages": self.attachment_messages,
            "attachment_size": self.attachment_size, "inline_image_ratio": self.inline_image_ratio,
            "html_ratio": self.html_ratio, "attachment_min": self.attachment_min,
            "attachment_max": self.attachment_max, "large_from": self.large_from, "large_share": self.large_share,
            "folders": [vars(f) for f in self.folders], "planted": [vars(p) for p in self.planted],
        }


@dataclass
class CorpusMessage:
    folder: str
    index: int
    message_id: str
    received_at: datetime
    keywords: list
    raw: bytes
    planted: list
    attachment_count: int

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()


@dataclass
class Envelope:
    sender_name: str
    sender_address: str
    date: datetime
    subject: str
    message_id: str
    parent: tuple | None
    thread_key: tuple


class CorpusGenerator:
    """Deterministic test mail corpus: the same spec (seed) always gives byte-identical messages."""

    def __init__(self, spec: CorpusSpec):
        self.spec = spec
        self.folders = {f.name: f for f in spec.folders}
        self.dates: dict[str, list[datetime]] = {}
        self.threads: dict[str, list[tuple]] = {}
        self.sent_slots: list[dict] = []
        self.answered: set[tuple] = set()
        self.planted_at: dict[tuple, list[PlantedTerm]] = {}
        self.with_attachment: set[tuple] = set()
        self.layout()

    def rng(self, *parts) -> random.Random:
        return random.Random(":".join(str(p) for p in (self.spec.seed, *parts)))

    def layout(self):
        for folder in self.spec.folders:
            if folder.role == "sent":
                continue
            start = self.spec.end_date - timedelta(days=folder.days_back_from)
            span = timedelta(days=folder.days_back_from - folder.days_back_to)
            r = self.rng(folder.name, "dates")
            self.dates[folder.name] = [start + span * ((i + r.random()) / max(folder.count, 1))
                                       for i in range(folder.count)]
            self.threads[folder.name] = self.thread_layout(folder)
        for folder in self.spec.folders:
            if folder.role == "sent":
                self.sent_layout(folder)
        self.plant_layout()
        self.attachment_layout()

    def thread_layout(self, folder: FolderSpec) -> list[tuple]:
        r = self.rng(folder.name, "threads")
        layout = []
        open_threads: list[list] = []
        next_thread = 0
        for i in range(folder.count):
            open_threads = [t for t in open_threads if t[1] > 0]
            if open_threads and r.random() < 0.45:
                thread = r.choice(open_threads)
                layout.append((thread[0], thread[2], thread[3]))
                thread[1] -= 1
                thread[2] = i
                thread[3] += 1
            else:
                length = r.choices((1, 2, 3, 4, 6, 9), weights=(55, 20, 10, 8, 5, 2))[0]
                layout.append((next_thread, None, 0))
                if length > 1:
                    open_threads.append([next_thread, length - 1, i, 1])
                next_thread += 1
        return layout

    def sent_layout(self, folder: FolderSpec):
        r = self.rng(folder.name, "slots")
        sources = [(name, i, d) for name, dates in self.dates.items()
                   if self.folders[name].role in ("inbox", "archive") for i, d in enumerate(dates)]
        start = self.spec.end_date - timedelta(days=folder.days_back_from)
        span = (self.spec.end_date - start).total_seconds()
        slots = []
        for j in range(folder.count):
            if sources and r.random() < 0.6:
                name, i, d = r.choice(sources)
                date = min(d + timedelta(minutes=r.uniform(8, 2880)), self.spec.end_date)
                slots.append({"date": date, "parent": (name, i), "slot": j})
                self.answered.add((name, i))
            else:
                slots.append({"date": start + timedelta(seconds=r.uniform(0, span)), "parent": None, "slot": j})
        slots.sort(key=lambda s: (s["date"], s["slot"]))
        self.sent_slots = slots
        self.dates[folder.name] = [s["date"] for s in slots]

    def plant_layout(self):
        everything = [(f.name, i) for f in self.spec.folders for i in range(f.count)]
        for term in self.spec.planted:
            if term.count > len(everything):
                raise ValueError(f"Can't plant '{term.term}' {term.count} times in {len(everything)} messages")
            for key in self.rng("plant", term.term).sample(everything, term.count):
                self.planted_at.setdefault(key, []).append(term)

    def attachment_layout(self):
        count = self.spec.attachment_messages
        if count is None:
            return
        everything = [(f.name, i) for f in self.spec.folders for i in range(f.count)]
        if count > len(everything):
            raise ValueError(f"Can't give {count} of {len(everything)} messages an attachment")
        self.with_attachment = set(self.rng("attachments").sample(everything, count))

    def message_id(self, folder: str, index: int) -> str:
        digest = hashlib.sha1(f"{self.spec.seed}:{folder}:{index}".encode()).hexdigest()
        return f"<{digest[:20]}.{index}@{TextGenerator.domains[int(digest[20:22], 16) % len(TextGenerator.domains)]}>"

    def thread_subject(self, folder: str, thread: int, year: int) -> str:
        return TextGenerator(self.rng(folder, "thread", thread)).subject(year)

    def thread_people(self, folder: str, thread: int) -> list[tuple[str, str]]:
        r = self.rng(folder, "people", thread)
        text = TextGenerator(r)
        return [text.person() for _ in range(r.randint(1, 3))]

    def envelope(self, folder: str, index: int) -> Envelope:
        spec = self.folders[folder]
        date = self.dates[folder][index]
        if spec.role == "sent":
            slot = self.sent_slots[index]
            parent = slot["parent"]
            if parent:
                parent_env = self.envelope(*parent)
                subject = parent_env.subject if parent_env.subject.startswith("Re: ") else "Re: " + parent_env.subject
                thread_key = parent_env.thread_key
            else:
                subject = TextGenerator(self.rng(folder, "subject", index)).subject(date.year)
                thread_key = (folder, index)
            return Envelope(self.spec.owner_name, self.spec.owner_address, date, subject,
                            self.message_id(folder, index), parent, thread_key)
        thread, parent_index, position = self.threads[folder][index]
        first_index = index
        while self.threads[folder][first_index][1] is not None:
            first_index = self.threads[folder][first_index][1]
        subject = self.thread_subject(folder, thread, self.dates[folder][first_index].year)
        if position:
            subject = "Re: " + subject
        people = self.thread_people(folder, thread)
        name, address = people[position % len(people)]
        parent = (folder, parent_index) if parent_index is not None else None
        return Envelope(name, address, date, subject, self.message_id(folder, index), parent, (folder, thread))

    def references(self, envelope: Envelope) -> list[str]:
        chain = []
        parent = envelope.parent
        while parent and len(chain) < 20:
            parent_env = self.envelope(*parent)
            chain.insert(0, parent_env.message_id)
            parent = parent_env.parent
        return chain

    def keywords(self, folder: str, index: int) -> list[str]:
        spec = self.folders[folder]
        r = self.rng(folder, "keywords", index)
        keywords = []
        if spec.role == "sent" or r.random() < spec.seen_ratio:
            keywords.append("$seen")
        if r.random() < spec.flagged_ratio:
            keywords.append("$flagged")
        if (folder, index) in self.answered:
            keywords.append("$answered")
        return keywords

    def attachment_size(self, r: random.Random) -> int:
        s = self.spec
        low, high = (s.large_from, s.attachment_max) if r.random() < s.large_share else (s.attachment_min,
                                                                                         min(s.large_from, s.attachment_max))
        return int(math.exp(r.uniform(math.log(low), math.log(max(high, low + 1)))))

    def subject(self, folder: str, index: int, envelope: Envelope | None = None) -> str:
        """The message's Subject as written: its thread's subject plus the terms planted in subjects."""
        subject = (envelope or self.envelope(folder, index)).subject
        for term in self.planted_at.get((folder, index), []):
            if term.field == "subject":
                subject = f"{subject} – {term.term}"
        return subject

    def generate(self, folder: str, index: int) -> CorpusMessage:
        env = self.envelope(folder, index)
        r = self.rng(folder, "body", index)
        text = TextGenerator(r)
        planted = self.planted_at.get((folder, index), [])
        subject = self.subject(folder, index, env)
        sent = self.folders[folder].role == "sent"
        if sent and env.parent:
            parent_env = self.envelope(*env.parent)
            recipient_name, recipient_address = parent_env.sender_name, parent_env.sender_address
        elif sent:
            recipient_name, recipient_address = text.person()
        else:
            recipient_name, recipient_address = self.spec.owner_name, self.spec.owner_address
        cc = [text.person() for _ in range(r.choices((0, 1, 2), weights=(70, 20, 10))[0])]
        body_terms = [t.term for t in planted if t.field == "body"]
        paragraphs = text.body(recipient_name.split()[0], env.sender_name, r.randint(1, 6), body_terms)
        if env.parent:
            quoted = self.envelope(*env.parent)
            paragraphs.append(f"On {format_datetime(quoted.date)}, {quoted.sender_name} wrote:\n> "
                              + text.sentence() + "\n> " + text.sentence())

        files = SyntheticFiles(r)
        attachments = []
        if self.spec.attachment_messages is not None:
            if (folder, index) in self.with_attachment:
                attachments.append(files.exact_pdf(self.spec.attachment_size, f"{env.date:%Y-%m-%d}-{index:05d}-1"))
        elif r.random() < self.spec.attachment_ratio:
            for n in range(r.choices((1, 2, 3), weights=(75, 20, 5))[0]):
                kind = r.choices(("pdf", "jpeg", "png", "docx", "xlsx"), weights=(35, 25, 10, 15, 15))[0]
                label = f"{env.date:%Y-%m-%d}-{index:05d}-{n + 1}"
                attachments.append(files.make(kind, self.attachment_size(r), label))
        inline = None
        use_html = r.random() < self.spec.html_ratio
        if use_html and r.random() < self.spec.inline_image_ratio / max(self.spec.html_ratio, 0.01):
            inline = Attachment(f"logo-{index}.png", "image/png", files.png_bytes(160, 48),
                                content_id=f"img{index}.{env.message_id.strip('<>')}")

        mime = MimeWriter(r)
        headers = [
            ("Date", format_datetime(env.date)),
            ("From", MimeWriter.address(env.sender_name, env.sender_address)),
            ("To", MimeWriter.address(recipient_name, recipient_address)),
        ]
        if cc:
            headers.append(("Cc", ", ".join(MimeWriter.address(n, a) for n, a in cc)))
        headers += [("Subject", MimeWriter.encode_header(subject)), ("Message-ID", env.message_id)]
        if env.parent:
            refs = self.references(env)
            headers += [("In-Reply-To", refs[-1]), ("References", " ".join(refs))]
        headers.append(("MIME-Version", "1.0"))
        raw = mime.message(headers, paragraphs, use_html, inline, attachments)
        return CorpusMessage(folder, index, env.message_id, env.date, self.keywords(folder, index), raw,
                             [t.term for t in planted], len(attachments))

    def folder_messages(self, folder: str, start: int = 0) -> Iterator[CorpusMessage]:
        for i in range(start, self.folders[folder].count):
            yield self.generate(folder, i)

    def messages(self) -> Iterator[CorpusMessage]:
        for folder in self.spec.folders:
            yield from self.folder_messages(folder.name)

    def expected(self) -> dict:
        folders = {f.name: {"count": f.count, "role": f.role} for f in self.spec.folders}
        planted = {}
        for term in self.spec.planted:
            per_folder = {}
            for (folder, _), terms in self.planted_at.items():
                if term in terms:
                    per_folder[folder] = per_folder.get(folder, 0) + 1
            planted[term.term] = {"count": term.count, "field": term.field, "per_folder": per_folder}
        attachments = len(self.with_attachment) if self.spec.attachment_messages is not None else None
        return {"folders": folders, "planted": planted, "total": sum(f.count for f in self.spec.folders),
                "profile": self.spec.profile, "attachment_messages": attachments,
                "attachment_size": self.spec.attachment_size if attachments is not None else None}

    def manifest(self, messages_path: Path | None = None, progress=None) -> dict:
        digest = hashlib.sha256()
        stats = {f.name: {"count": 0, "bytes": 0, "unread": 0, "flagged": 0, "with_attachments": 0}
                 for f in self.spec.folders}
        out = open(messages_path, "w", encoding="utf-8") if messages_path else None
        try:
            for n, msg in enumerate(self.messages()):
                sha = msg.sha256
                digest.update(sha.encode())
                s = stats[msg.folder]
                s["count"] += 1
                s["bytes"] += len(msg.raw)
                s["unread"] += "$seen" not in msg.keywords
                s["flagged"] += "$flagged" in msg.keywords
                s["with_attachments"] += msg.attachment_count > 0
                if out:
                    out.write(json.dumps({"folder": msg.folder, "index": msg.index, "message_id": msg.message_id,
                                          "received_at": msg.received_at.isoformat(), "keywords": msg.keywords,
                                          "size": len(msg.raw), "sha256": sha, "planted": msg.planted}) + "\n")
                if progress and n % 1000 == 0:
                    progress(n)
        finally:
            if out:
                out.close()
        expected = self.expected()
        return {"version": 1, "spec": self.spec.to_dict(), "digest": digest.hexdigest(),
                "total_messages": sum(s["count"] for s in stats.values()),
                "total_bytes": sum(s["bytes"] for s in stats.values()), "folders": stats,
                "planted": expected["planted"]}


class MimeWriter:
    """Hand-written MIME with CRLF line ends and deterministic boundaries."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def boundary(self) -> str:
        return "=_" + self.rng.randbytes(12).hex()

    @staticmethod
    def encode_header(text: str) -> str:
        if text.isascii():
            return text
        encoded = []
        for ch in text:
            if ch.isascii() and (ch.isalnum() or ch in "!*+-/"):
                encoded.append(ch)
            elif ch == " ":
                encoded.append("_")
            else:
                encoded.extend(f"={b:02X}" for b in ch.encode("utf-8"))
        words, current = [], ""
        for token in encoded:
            if len(current) + len(token) > 45:
                words.append(current)
                current = ""
            current += token
        words.append(current)
        return " ".join(f"=?UTF-8?Q?{w}?=" for w in words)

    @classmethod
    def address(cls, name: str, address: str) -> str:
        display = cls.encode_header(name) if not name.isascii() else f'"{name}"' if "," in name else name
        return f"{display} <{address}>"

    @staticmethod
    def fold(name: str, value: str) -> str:
        line = f"{name}: "
        lines = []
        for word in value.split(" "):
            if len(line) + len(word) > 76 and line.strip():
                lines.append(line.rstrip())
                line = " "
            line += word + " "
        lines.append(line.rstrip())
        return "\r\n".join(lines)

    @staticmethod
    def crlf(text: bytes) -> bytes:
        return text.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")

    def text_part(self, subtype: str, text: str) -> bytes:
        body = self.crlf(quopri.encodestring(text.encode("utf-8")))
        return (f"Content-Type: text/{subtype}; charset=utf-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n"
                .encode() + body)

    def binary_part(self, attachment: Attachment) -> bytes:
        disposition = "inline" if attachment.content_id else "attachment"
        head = (f"Content-Type: {attachment.content_type}; name=\"{attachment.filename}\"\r\n"
                f"Content-Disposition: {disposition}; filename=\"{attachment.filename}\"\r\n"
                f"Content-Transfer-Encoding: base64\r\n")
        if attachment.content_id:
            head += f"Content-ID: <{attachment.content_id}>\r\n"
        return (head + "\r\n").encode() + base64.encodebytes(attachment.data).replace(b"\n", b"\r\n")

    def multipart(self, subtype: str, parts: list[bytes]) -> bytes:
        boundary = self.boundary()
        out = bytearray(f"Content-Type: multipart/{subtype}; boundary=\"{boundary}\"\r\n\r\n".encode())
        for part in parts:
            out += f"--{boundary}\r\n".encode() + part
            if not part.endswith(b"\r\n"):
                out += b"\r\n"
        out += f"--{boundary}--\r\n".encode()
        return bytes(out)

    @staticmethod
    def html(paragraphs: list[str], inline: Attachment | None) -> str:
        def escape(t: str) -> str:
            return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        body = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)
        if inline:
            body += f'<p><img src="cid:{inline.content_id}" alt="logo" width="160" height="48"></p>'
        return ('<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
                f'<body style="font-family: sans-serif">{body}</body></html>')

    def message(self, headers: list[tuple[str, str]], paragraphs: list[str], use_html: bool,
                inline: Attachment | None, attachments: list[Attachment]) -> bytes:
        plain = "\n\n".join(paragraphs) + "\n"
        if use_html:
            html_part = self.text_part("html", self.html(paragraphs, inline))
            if inline:
                html_part = self.multipart("related", [html_part, self.binary_part(inline)])
            body = self.multipart("alternative", [self.text_part("plain", plain), html_part])
        else:
            body = self.text_part("plain", plain)
        if attachments:
            body = self.multipart("mixed", [body, *[self.binary_part(a) for a in attachments]])
        head = "".join(self.fold(name, value) + "\r\n" for name, value in headers).encode()
        return head + body
