#!/usr/bin/env python3
"""Synthetic "mail app" for the end-to-end test of the pipeline (X11 only, python-xlib + Pillow).

It reacts to configured trigger keys with known delays and shows the typical in-between states of a real app:
an animated spinner, a static "Loading…" text, progressive rendering of the list, and a blinking caret in a text
field. It logs, in the same monotonic clock as the driver (time.perf_counter = CLOCK_MONOTONIC), when each trigger
key arrived and when the last pixel of the final state was drawn: that is the ground truth the pipeline's
measurement is checked against.

Config (JSON): {"title": "...", "background": [r,g,b], "steps": [{"key": "Return", "delay_s": 0.8,
"feedback": "spinner"|"loading"|"none", "progressive": 4, "rows": 12, "counter_s": 1.5}, ...]}; a key press
triggers the first step with that key that hasn't run yet. With `counter_s`, a small "n of 30000" counter at the
bottom of the list keeps counting for that long after the rows are final (like an Inbox that shows its first page
and loads the rest of the list in the background); the final state is the counter's last update. End draws the
"oldest message" row at the bottom of the list (the verify check).
"""

import argparse
import json
import os
import select
import sys
import time

from PIL import Image, ImageDraw, ImageFont
from Xlib import X, XK, Xatom, display


class FakeMailApp:
    def __init__(self, config: dict, log_path: str, x: int, y: int, width: int, height: int, start_delay: float):
        self.config = config
        self.width, self.height = width, height
        self.log = open(log_path, "a", encoding="utf-8")
        self.display = display.Display()
        screen = self.display.screen()
        self.window = screen.root.create_window(
            x, y, width, height, 0, screen.root_depth, X.InputOutput, X.CopyFromParent,
            background_pixel=screen.white_pixel,
            event_mask=X.ExposureMask | X.KeyPressMask | X.StructureNotifyMask)
        self.window.set_wm_name(config.get("title", "Fake Mail"))
        self.window.set_wm_class("fakemail", "FakeMail")
        self.window.change_property(self.display.intern_atom("_NET_WM_PID"), Xatom.CARDINAL, 32, [os.getpid()])
        self.gc = self.window.create_gc()
        self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        self.small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        self.big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        self.image = Image.new("RGB", (width, height), tuple(config.get("background", [246, 247, 250])))
        self.steps = config.get("steps", [])
        self.used_steps: set[int] = set()
        self.typed = ""
        self.caret_on = True
        self.timers: list[tuple[float, str, object]] = []
        self.spinner_until = 0.0
        self.spinner_phase = 0
        if start_delay:
            time.sleep(start_delay)
        self.paint_chrome()
        self.window.map()
        self.display.sync()
        self.write("started")
        self.at(time.perf_counter() + 0.53, "caret", None)

    def write(self, event: str, **fields):
        self.log.write(json.dumps({"t": time.perf_counter(), "event": event, **fields}) + "\n")
        self.log.flush()

    def at(self, when: float, kind: str, payload):
        self.timers.append((when, kind, payload))
        self.timers.sort(key=lambda t: t[0])

    def blit(self, box: tuple[int, int, int, int]):
        x0, y0, x1, y1 = box
        region = self.image.crop(box)
        data = region.tobytes("raw", "BGRX")
        stride = (x1 - x0) * 4
        rows_per_request = max(1, (self.display.display.info.max_request_length * 4 - 64) // stride)
        for row in range(0, y1 - y0, rows_per_request):
            h = min(rows_per_request, y1 - y0 - row)
            self.window.put_image(self.gc, x0, y0 + row, x1 - x0, h, X.ZPixmap, 24, 0,
                                  data[row * stride:(row + h) * stride])

    def paint_chrome(self):
        d = ImageDraw.Draw(self.image)
        d.rectangle([0, 0, self.width, 48], fill=(40, 70, 120))
        d.text((16, 12), self.config.get("title", "Fake Mail"), font=self.big, fill=(255, 255, 255))
        d.rectangle([16, 64, self.width - 16, 96], outline=(150, 150, 160), fill=(255, 255, 255))
        d.rectangle([0, 110, 180, self.height], fill=(228, 232, 240))
        for i, name in enumerate(("Inbox", "Archive", "Sent", "Projects")):
            d.text((16, 124 + i * 28), name, font=self.font, fill=(30, 30, 40))
        self.paint_list(0, 6)

    def list_box(self) -> tuple[int, int, int, int]:
        return 190, 110, self.width - 10, self.height - 10

    def paint_list(self, seed: int, rows: int, upto: int | None = None):
        d = ImageDraw.Draw(self.image)
        x0, y0, x1, y1 = self.list_box()
        if upto is None or upto == 0:
            d.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))
        row_h = 30
        for r in range(rows if upto is None else upto):
            y = y0 + 8 + r * row_h
            if y + row_h > y1:
                break
            shade = 60 + (seed * 37 + r * 11) % 120
            d.rectangle([x0 + 1, y, x1 - 1, y + row_h - 1], fill=(255, 255, 255))
            d.rectangle([x0 + 8, y + 4, x0 + 8 + 12, y + 16], fill=(shade, 120, 200))
            d.text((x0 + 30, y), f"Message {seed}-{r}: subject line number {r + 1}", font=self.font,
                   fill=(20, 20, 30))

    def paint_text_field(self):
        d = ImageDraw.Draw(self.image)
        d.rectangle([17, 65, self.width - 17, 95], fill=(255, 255, 255))
        d.text((24, 70), self.typed[-60:], font=self.font, fill=(10, 10, 10))
        self.paint_caret()

    def caret_x(self) -> int:
        return 24 + int(ImageDraw.Draw(self.image).textlength(self.typed[-60:], font=self.font)) + 2

    def paint_caret(self):
        d = ImageDraw.Draw(self.image)
        x = self.caret_x()
        d.rectangle([x, 70, x + 1, 89], fill=(10, 10, 10) if self.caret_on else (255, 255, 255))
        self.blit((17, 65, self.width - 17, 96))

    def spinner_box(self) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = self.list_box()
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        return cx - 24, cy - 24, cx + 24, cy + 24

    def paint_spinner(self):
        d = ImageDraw.Draw(self.image)
        box = self.spinner_box()
        d.rectangle(box, fill=(255, 255, 255))
        d.arc(box, start=self.spinner_phase * 30, end=self.spinner_phase * 30 + 270, fill=(40, 110, 220), width=6)
        self.blit(box)

    def on_trigger(self, step: dict, index: int):
        t_key = time.perf_counter()
        self.write("key", step=index, key=step["key"])
        delay = float(step.get("delay_s", 1.0))
        feedback = step.get("feedback", "spinner")
        x0, y0, x1, y1 = self.list_box()
        d = ImageDraw.Draw(self.image)
        d.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))
        if feedback == "loading":
            d.text((x0 + 40, y0 + 40), "Loading…", font=self.big, fill=(80, 80, 90))
        self.blit((x0, y0, x1 + 1, y1 + 1))
        self.display.sync()
        if feedback == "spinner":
            self.spinner_until = t_key + delay - 0.05 * max(int(step.get("progressive", 1)) - 1, 0)
            self.at(time.perf_counter() + 1 / 30, "spin", None)
        chunks = max(1, int(step.get("progressive", 1)))
        rows = int(step.get("rows", 12))
        counter_s = float(step.get("counter_s", 0))
        for c in range(chunks):
            when = t_key + delay - (chunks - 1 - c) * 0.05
            upto = rows if c == chunks - 1 else max(1, rows * (c + 1) // chunks)
            self.at(when, "content", (index, rows, upto, c == chunks - 1 and not counter_s, c == 0))
        if counter_s:
            updates = max(1, int(counter_s / 0.1))
            for k in range(1, updates + 1):
                self.at(t_key + delay + k * counter_s / updates, "counter", (index, k, updates))

    def handle_timer(self, kind: str, payload):
        if kind == "caret":
            self.caret_on = not self.caret_on
            self.paint_caret()
            self.at(time.perf_counter() + 0.53, "caret", None)
        elif kind == "spin":
            if time.perf_counter() < self.spinner_until:
                self.spinner_phase = (self.spinner_phase + 1) % 12
                self.paint_spinner()
                self.at(time.perf_counter() + 1 / 30, "spin", None)
        elif kind == "content":
            index, rows, upto, final, first = payload
            if first:
                self.spinner_until = 0
                x0, y0, x1, y1 = self.list_box()
                ImageDraw.Draw(self.image).rectangle([x0, y0, x1, y1], fill=(255, 255, 255))
            self.paint_list(index + 1, rows, upto)
            self.blit((self.list_box()[0], self.list_box()[1], self.list_box()[2] + 1, self.list_box()[3] + 1))
            self.display.sync()
            if first:
                self.write("first_drawn", step=index)
            if final:
                self.write("final_drawn", step=index)
        elif kind == "counter":
            index, k, updates = payload
            x0, y0, x1, y1 = self.list_box()
            box = (x0 + 8, y1 - 16, x0 + 60, y1 - 4)
            d = ImageDraw.Draw(self.image)
            d.rectangle(box, fill=(255, 255, 255))
            d.text((box[0], box[1]), f"{k:02d}", font=self.small, fill=(90, 90, 100))
            self.blit((box[0], box[1], box[2] + 1, box[3] + 1))
            self.display.sync()
            if k == updates:
                self.write("final_drawn", step=index)

    def handle_key(self, event):
        keysym = self.display.keycode_to_keysym(event.detail, 1 if event.state & X.ShiftMask else 0)
        for index, step in enumerate(self.steps):
            if index not in self.used_steps and keysym == XK.string_to_keysym(step["key"]):
                self.used_steps.add(index)
                self.on_trigger(step, index)
                return
        if keysym == XK.string_to_keysym("End"):
            x0, y0, x1, y1 = self.list_box()
            d = ImageDraw.Draw(self.image)
            d.rectangle([x0 + 8, y1 - 52, x1 - 8, y1 - 24], fill=(255, 236, 200))
            d.text((x0 + 30, y1 - 48), "Oldest message: welcome to the corpus", font=self.font, fill=(20, 20, 30))
            self.blit((x0, y1 - 52, x1, y1 - 23))
            self.display.sync()
            self.write("verify_drawn")
            return
        if keysym == XK.string_to_keysym("q") and event.state & X.ControlMask:
            self.write("quit")
            sys.exit(0)
        text = XK.keysym_to_string(keysym)
        if text and text.isprintable() and len(text) == 1:
            self.typed += text
            self.paint_text_field()

    def loop(self):
        fd = self.display.fileno()
        while True:
            while self.display.pending_events():
                event = self.display.next_event()
                if event.type == X.Expose and event.count == 0:
                    self.blit((0, 0, self.width, self.height))
                elif event.type == X.KeyPress:
                    self.handle_key(event)
                elif event.type == X.DestroyNotify:
                    return
            self.display.flush()
            now = time.perf_counter()
            while self.timers and self.timers[0][0] <= now:
                _, kind, payload = self.timers.pop(0)
                self.handle_timer(kind, payload)
                now = time.perf_counter()
            self.display.flush()
            timeout = max(0.0, self.timers[0][0] - time.perf_counter()) if self.timers else 0.5
            select.select([fd], [], [], min(timeout, 0.5))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--geometry", default="640x480+0+0")
    parser.add_argument("--start-delay", type=float, default=0.0)
    args = parser.parse_args()
    size, _, pos = args.geometry.partition("+")
    width, height = map(int, size.split("x"))
    x, y = map(int, pos.split("+"))
    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    FakeMailApp(config, args.log, x, y, width, height, args.start_delay).loop()


if __name__ == "__main__":
    main()
