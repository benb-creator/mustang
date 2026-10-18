import io
import random
import struct
import zipfile
import zlib
from dataclasses import dataclass


@dataclass
class Attachment:
    filename: str
    content_type: str
    data: bytes
    content_id: str | None = None


class SyntheticFiles:
    """Valid, deterministic files of a requested size (no encoder library whose output could vary by version)."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def make(self, kind: str, size: int, label: str) -> Attachment:
        maker = {"pdf": self.pdf, "jpeg": self.jpeg, "png": self.png, "docx": self.docx, "xlsx": self.xlsx}[kind]
        return maker(size, label)

    @staticmethod
    def stored_deflate(data: bytes) -> bytes:
        out = bytearray(b"\x78\x01")
        block = 65535
        for offset in range(0, max(len(data), 1), block):
            chunk = data[offset:offset + block]
            final = offset + block >= len(data)
            out += bytes([1 if final else 0]) + struct.pack("<HH", len(chunk), len(chunk) ^ 0xFFFF) + chunk
        out += struct.pack(">I", zlib.adler32(data))
        return bytes(out)

    def png_bytes(self, width: int, height: int) -> bytes:
        rows = bytearray()
        for _ in range(height):
            rows += b"\x00" + self.rng.randbytes(width * 3)

        def chunk(tag: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload))

        header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", self.stored_deflate(bytes(rows))) + \
            chunk(b"IEND", b"")

    def png(self, size: int, label: str) -> Attachment:
        width = self.rng.choice((640, 800, 1024, 1280, 1600))
        height = max(1, size // (width * 3 + 1))
        name = f"Screenshot-{label}.png"
        return Attachment(name, "image/png", self.png_bytes(width, height))

    def jpeg_bytes(self, width: int, height: int, padding: int) -> bytes:
        dc_codes = ["00", "010", "011", "100", "101", "110", "1110", "11110", "111110", "1111110", "11111110",
                    "111111110"]
        blocks_x, blocks_y = (width + 7) // 8, (height + 7) // 8
        base = self.rng.randint(-60, 60)
        gx, gy = self.rng.uniform(-1.5, 1.5), self.rng.uniform(-1.5, 1.5)
        bits = []
        previous = 0
        for by in range(blocks_y):
            for bx in range(blocks_x):
                dc = int(base + gx * bx + gy * by + self.rng.randint(-6, 6))
                dc = max(-127, min(127, dc))
                diff = dc - previous
                previous = dc
                category = abs(diff).bit_length()
                bits.append(dc_codes[category])
                if category:
                    value = diff if diff > 0 else diff + (1 << category) - 1
                    bits.append(format(value, f"0{category}b"))
                bits.append("0")
        stream = "".join(bits)
        stream += "1" * (-len(stream) % 8)
        entropy = bytearray()
        for i in range(0, len(stream), 8):
            byte = int(stream[i:i + 8], 2)
            entropy.append(byte)
            if byte == 0xFF:
                entropy.append(0)

        def segment(marker: int, payload: bytes) -> bytes:
            return struct.pack(">BBH", 0xFF, marker, len(payload) + 2) + payload

        out = bytearray(b"\xFF\xD8")
        out += segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
        remaining = padding
        while remaining > 0:
            n = min(65533, remaining)
            out += segment(0xFE, self.rng.randbytes(n))
            remaining -= n + 4
        out += segment(0xDB, b"\x00" + bytes([8] + [1] * 63))
        out += segment(0xC0, struct.pack(">BHHB", 8, height, width, 1) + b"\x01\x11\x00")
        dc_table = bytes([0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]) + bytes(range(12))
        ac_table = bytes([1] + [0] * 15) + b"\x00"
        out += segment(0xC4, b"\x00" + dc_table + b"\x10" + ac_table)
        out += segment(0xDA, b"\x01\x01\x00\x00\x3F\x00")
        out += entropy + b"\xFF\xD9"
        return bytes(out)

    def jpeg(self, size: int, label: str) -> Attachment:
        width, height = self.rng.choice(((1600, 1200), (2048, 1536), (1200, 900), (1920, 1080)))
        plain = self.jpeg_bytes(width, height, 0)
        data = self.jpeg_bytes(width, height, max(0, size - len(plain))) if size > len(plain) else plain
        return Attachment(f"IMG_{label}.jpg", "image/jpeg", data)

    @staticmethod
    def pdf_escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def pdf(self, size: int, label: str) -> Attachment:
        padding = max(0, size - 1200)
        data = self.pdf_with_padding(label, lambda: self.rng.randbytes(padding) if padding else b"")
        return Attachment(f"{label}.pdf", "application/pdf", data)

    def exact_pdf(self, size: int, label: str) -> Attachment:
        """A PDF of exactly `size` bytes: the padding stream is regenerated until the file length matches."""
        padding_seed = self.rng.getrandbits(64)
        lines_state = self.rng.getstate()
        padding = max(0, size - 1200)
        for _ in range(6):
            self.rng.setstate(lines_state)
            data = self.pdf_with_padding(label, lambda: random.Random(padding_seed).randbytes(padding))
            if len(data) == size:
                return Attachment(f"{label}.pdf", "application/pdf", data)
            padding = max(0, padding + size - len(data))
        raise ValueError(f"Can't make a PDF of exactly {size} bytes")

    def pdf_with_padding(self, label: str, padding) -> bytes:
        lines = [f"Document {label}", "", *[f"Item {i + 1}: {self.rng.randint(10, 9999)}.{self.rng.randint(0, 99):02d} EUR"
                                           for i in range(self.rng.randint(5, 25))]]
        text_ops = "BT /F1 12 Tf 72 770 Td 16 TL " + " ".join(f"({self.pdf_escape(l)}) '" for l in lines) + " ET"
        content = text_ops.encode("latin-1")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        blob = padding()
        if blob:
            objects.append(b"<< /Length %d >>\nstream\n" % len(blob) + blob + b"\nendstream")
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for number, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
        for offset in offsets:
            out += b"%010d 00000 n \n" % offset
        out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
        return bytes(out)

    @staticmethod
    def zip_stored(files: list[tuple[str, bytes]]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as archive:
            for name, data in files:
                info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.create_version = 20
                info.extract_version = 20
                info.external_attr = 0o644 << 16
                archive.writestr(info, data)
        return buf.getvalue()

    def docx(self, size: int, label: str) -> Attachment:
        content_types = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         b'<Default Extension="xml" ContentType="application/xml"/>'
                         b'<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
                         b'officedocument.wordprocessingml.document.main+xml"/></Types>')
        rels = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                b'officeDocument" Target="word/document.xml"/></Relationships>')
        paragraphs = []
        total = 0
        number = 0
        while total < max(size - 1500, 200):
            number += 1
            text = f"Section {number}. Figures {self.rng.randint(100, 99999)} and {self.rng.randint(100, 99999)} were checked."
            p = f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
            paragraphs.append(p)
            total += len(p)
        document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                    f"<w:p><w:r><w:t>{label}</w:t></w:r></w:p>{''.join(paragraphs)}</w:body></w:document>").encode()
        data = self.zip_stored([("[Content_Types].xml", content_types), ("_rels/.rels", rels),
                                ("word/document.xml", document)])
        return Attachment(f"{label}.docx",
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document", data)

    def xlsx(self, size: int, label: str) -> Attachment:
        content_types = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         b'<Default Extension="xml" ContentType="application/xml"/>'
                         b'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
                         b'officedocument.spreadsheetml.sheet.main+xml"/>'
                         b'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-'
                         b'officedocument.spreadsheetml.worksheet+xml"/></Types>')
        rels = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                b'officeDocument" Target="xl/workbook.xml"/></Relationships>')
        workbook = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    b'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    b'<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        workbook_rels = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                         b'relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        rows = []
        total = 0
        row = 0
        while total < max(size - 2000, 200):
            row += 1
            cells = "".join(f'<c r="{col}{row}"><v>{self.rng.randint(0, 999999) / 100}</v></c>' for col in "ABCDEF")
            r = f'<row r="{row}">{cells}</row>'
            rows.append(r)
            total += len(r)
        sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                 f"{''.join(rows)}</sheetData></worksheet>").encode()
        data = self.zip_stored([("[Content_Types].xml", content_types), ("_rels/.rels", rels),
                                ("xl/workbook.xml", workbook), ("xl/_rels/workbook.xml.rels", workbook_rels),
                                ("xl/worksheets/sheet1.xml", sheet)])
        return Attachment(f"{label}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", data)
