import platform
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass
class Theme:
    background: tuple = (14, 18, 28)
    band: tuple = (24, 30, 44)
    left_band: tuple = (22, 46, 74)
    right_band: tuple = (44, 40, 52)
    text: tuple = (240, 242, 246)
    muted: tuple = (160, 168, 184)
    accent: tuple = (64, 196, 255)
    done: tuple = (46, 204, 113)


class Fonts:
    def __init__(self, regular: str | None = None, bold: str | None = None):
        self.regular = regular or self.default(False)
        self.bold = bold or self.default(True)

    @staticmethod
    def default(bold: bool) -> str:
        if platform.system() == "Windows":
            return "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"
        for candidate in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                          "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf"):
            if Path(candidate).exists():
                return candidate
        raise FileNotFoundError("No default font found; set compose.font_regular and compose.font_bold")

    def get(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.bold if bold else self.regular, max(8, int(size)))


class CardRenderer:
    def __init__(self, width: int, height: int, scale: float, fonts: Fonts, theme: Theme | None = None):
        self.width = width
        self.height = height
        self.scale = scale
        self.fonts = fonts
        self.theme = theme or Theme()

    def px(self, value: float) -> int:
        return int(round(value * self.scale))

    def canvas(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        image = Image.new("RGB", (self.width, self.height), self.theme.background)
        return image, ImageDraw.Draw(image)

    def fit_font(self, draw: ImageDraw.ImageDraw, text: str, size: int, max_width: int, bold: bool):
        font = self.fonts.get(size, bold)
        while draw.textlength(text, font=font) > max_width and size > 10:
            size = int(size * 0.92)
            font = self.fonts.get(size, bold)
        return font

    def centered_lines(self, draw, lines: list[tuple[str, int, bool, tuple]], top: int | None = None):
        heights = [self.px(size) * 1.35 for _, size, _, _ in lines]
        y = top if top is not None else (self.height - sum(heights)) / 2
        for (text, size, bold, color), h in zip(lines, heights):
            font = self.fit_font(draw, text, self.px(size), self.width - self.px(160), bold)
            w = draw.textlength(text, font=font)
            draw.text(((self.width - w) / 2, y), text, font=font, fill=color)
            y += h

    def text_card(self, path: Path, lines: list[str]) -> Path:
        image, draw = self.canvas()
        styled = [(lines[0], 84, True, self.theme.text)] if lines else []
        styled += [(line, 48, False, self.theme.muted) for line in lines[1:]]
        self.centered_lines(draw, styled)
        image.save(path)
        return path

    def title_card(self, path: Path, title: str, subtitle: str, extra: list[str]) -> Path:
        image, draw = self.canvas()
        lines = [(title, 104, True, self.theme.text), (subtitle, 46, False, self.theme.accent)]
        lines += [(line, 40, False, self.theme.muted) for line in extra]
        self.centered_lines(draw, lines)
        image.save(path)
        return path

    def race_background(self, path: Path, layout, title: str, left_label: str, right_label: str,
                        footnote: list[str]) -> Path:
        image, draw = self.canvas()
        t = self.theme
        draw.rectangle([0, 0, self.width, layout.header_h], fill=t.band)
        font = self.fit_font(draw, title, self.px(52), self.width - self.px(80), True)
        w = draw.textlength(title, font=font)
        draw.text(((self.width - w) / 2, self.px(10)), title, font=font, fill=t.text)
        for x0, label, color in ((0, left_label, t.left_band), (layout.pane_w, right_label, t.right_band)):
            draw.rectangle([x0, layout.label_top, x0 + layout.pane_w, layout.label_top + layout.label_h], fill=color)
            font = self.fit_font(draw, label, self.px(36), layout.pane_w - self.px(460), True)
            draw.text((x0 + self.px(24), layout.label_top + (layout.label_h - self.px(36) * 1.2) / 2), label,
                      font=font, fill=t.text)
        draw.rectangle([0, layout.hold_top, self.width, self.height], fill=t.band)
        y = layout.footer_top + self.px(10)
        for line in footnote[:2]:
            font = self.fit_font(draw, line, self.px(30), self.width - self.px(80), False)
            w = draw.textlength(line, font=font)
            draw.text(((self.width - w) / 2, y), line, font=font, fill=t.muted)
            y += self.px(42)
        image.save(path)
        return path

    def pane_card(self, path: Path, width: int, height: int, lines: list[str]) -> Path:
        """Neutral card in a pane's place (no recording shown): the same look for both sides."""
        image = Image.new("RGB", (width, height), self.theme.band)
        draw = ImageDraw.Draw(image)
        sizes = [56, 40] + [36] * max(0, len(lines) - 2)
        y = (height - sum(self.px(s) * 1.5 for s in sizes[:len(lines)])) / 2
        for line, size in zip(lines, sizes):
            font = self.fit_font(draw, line, self.px(size), width - self.px(80), size == 56)
            w = draw.textlength(line, font=font)
            draw.text(((width - w) / 2, y), line, font=font, fill=self.theme.text if size == 56 else self.theme.muted)
            y += self.px(size) * 1.5
        image.save(path)
        return path

    def result_card(self, path: Path, heading: str, left_name: str, right_name: str, rows: list[dict],
                    footer_lines: list[str], labels: dict) -> Path:
        image, draw = self.canvas()
        t = self.theme
        y = self.px(70)
        font = self.fit_font(draw, heading, self.px(64), self.width - self.px(160), True)
        w = draw.textlength(heading, font=font)
        draw.text(((self.width - w) / 2, y), heading, font=font, fill=t.text)
        y += self.px(130)
        columns = [(labels["task"], 0.06, "left"), (left_name, 0.42, "right"), (right_name, 0.64, "right"),
                   (labels["ratio"], 0.78, "right"), (labels["actions"], 0.95, "right")]
        header_font = self.fonts.get(self.px(34), True)
        row_font = self.fonts.get(self.px(36), False)
        small = self.fonts.get(self.px(24), False)

        def put(text, x_frac, align, yy, font, fill):
            x = self.width * x_frac
            if align == "right":
                x -= draw.textlength(text, font=font)
            draw.text((x, yy), text, font=font, fill=fill)

        for text, x_frac, align in columns:
            put(text, x_frac, align, y, header_font, t.accent)
        y += self.px(62)
        row_h = min(self.px(96), int((self.height - y - self.px(200)) / max(len(rows), 1)))
        for row in rows:
            put(row["task"], 0.06, "left", y, row_font, t.text)
            put(row["left"], 0.42, "right", y, row_font, t.done if row.get("left_first") else t.text)
            put(row["right"], 0.64, "right", y, row_font, t.done if row.get("right_first") else t.text)
            put(row["ratio"], 0.78, "right", y, row_font, t.text)
            put(row["actions"], 0.95, "right", y, row_font, t.text)
            if row.get("range_left") or row.get("range_right"):
                put(row.get("range_left", ""), 0.42, "right", y + self.px(42), small, t.muted)
                put(row.get("range_right", ""), 0.64, "right", y + self.px(42), small, t.muted)
            y += row_h
        y = self.height - self.px(60) * len(footer_lines) - self.px(40)
        for line in footer_lines:
            font = self.fit_font(draw, line, self.px(28), self.width - self.px(160), False)
            w = draw.textlength(line, font=font)
            draw.text(((self.width - w) / 2, y), line, font=font, fill=t.muted)
            y += self.px(48)
        image.save(path)
        return path
