import html
import json
from pathlib import Path

from .narration import MethodTemplate, NarrationValues


class MethodError(Exception):
    pass


class MethodTexts:
    """Fills the voice-over's method templates (YouTube description, website expander) for one variant and
    language: the narration's values plus every run, the action lists, the server-log evidence, the deviations,
    what the apps did after the list was complete, links and credits."""

    words = {
        "en": {"warmup": "warm-up, discarded", "not_done": "not done within {limit}", "failed": "not valid: {reason}",
               "attempt": "recorded again at the end of the series (attempt {attempt})",
               "after_screen": "the screen changed in {frames} frames of the {recorded:.0f} s recorded after the "
                               "list was complete", "after_quiet": "no screen change in the {recorded:.0f} s recorded "
                                                                   "after the list was complete",
               "after_fetch": "the server log shows {messages} messages fetched in full and {downloads} downloads "
                              "from then until the app was closed",
               "no_evidence": "no server log evidence", "benchmark_only": "all from the test computer",
               "logins": "{n} logins", "from": "from {owner} ({asn}, {prefix})",
               "fetched": "{messages} messages fetched in full ({gb} GB) before the account was removed",
               "after_removal": "{n} logins from outside the test computer after the account was removed",
               "none": "none"},
        "de": {"warmup": "Aufwärmlauf, verworfen", "not_done": "nicht fertig in {limit}",
               "failed": "nicht gültig: {reason}",
               "attempt": "am Ende der Serie erneut aufgenommen (Versuch {attempt})",
               "after_screen": "der Bildschirm änderte sich in {frames} Bildern der {recorded:.0f} s, die nach der "
                               "vollständigen Liste aufgenommen wurden",
               "after_quiet": "keine Bildschirmänderung in den {recorded:.0f} s, die nach der vollständigen Liste "
                              "aufgenommen wurden",
               "after_fetch": "das Server-Protokoll zeigt {messages} vollständig abgerufene Mails und {downloads} "
                              "Downloads von da an bis zum Schließen der App",
               "no_evidence": "keine Belege aus dem Server-Protokoll", "benchmark_only": "alle vom Testrechner",
               "logins": "{n} Anmeldungen", "from": "von {owner} ({asn}, {prefix})",
               "fetched": "{messages} Mails vollständig abgerufen ({gb} GB), bevor das Konto entfernt wurde",
               "after_removal": "{n} Anmeldungen von außerhalb des Testrechners, nachdem das Konto entfernt wurde",
               "none": "keine"},
    }

    def __init__(self, config, results: dict, values: NarrationValues, language: str, voice_dir: Path | None):
        self.config = config
        self.results = results
        self.values = values
        self.language = language if language in self.words else "en"
        self.voice_dir = voice_dir

    def w(self, key: str, **kwargs) -> str:
        return self.words[self.language][key].format(**kwargs)

    def seconds(self, value: float) -> str:
        text = self.values.number(value, 2) + " s"
        if value >= 60:
            minutes, rest = divmod(value, 60)
            text += f" ({int(minutes)}:{int(rest):02d})"
        return text

    def run_text(self, side: dict, run: dict) -> str:
        if run["status"] == "ok":
            value = self.seconds(run["total_s"])
        elif run["status"] == "timeout":
            value = self.w("not_done", limit=self.seconds(run["censored_at_s"]))
        else:
            value = self.w("failed", reason=run["reason"])
        if run.get("attempt", 1) > 1:
            value += f" ({self.w('attempt', attempt=run['attempt'])})"
        return value

    def runs_block(self, task: dict) -> str:
        rows = []
        for side in (task["left"], task["right"]):
            for run in side.get("warmups", []) + side["runs"]:
                rows.append((run["order"] or 0, side["name"], run))
        lines = []
        for order, name, run in sorted(rows, key=lambda r: r[0]):
            label = f"{name} ({self.w('warmup')})" if run["warmup"] else name
            lines.append(f"• #{order} {label}: {self.run_text(None, run)}")
        return "\n".join(lines)

    @staticmethod
    def actions_block(task: dict) -> str:
        return " · ".join(f"{s['name']} ({s['actions']}): " + "; ".join(s["action_list"]) for s in (task["left"],
                                                                                                    task["right"]))

    def evidence_block(self, comparison: dict) -> str:
        evidence = comparison.get("evidence") or {}
        if not evidence.get("sides"):
            return self.w("no_evidence")
        lines = []
        for side_name, data in evidence["sides"].items():
            name = comparison["tasks"][evidence["task"]][side_name]["name"]
            for run in data["runs"]:
                logins = sum(run["logins"].values())
                parts = [self.w("logins", n=logins)]
                if run["logins"].get("benchmark", 0) == logins:
                    parts.append(self.w("benchmark_only"))
                for source in run.get("sources", []):
                    if source["kind"] != "benchmark":
                        parts.append(self.w("from", owner=source["owner"], asn=source["asn"], prefix=source["prefix"]))
                if run["cloud_full_messages"]:
                    parts.append(self.w("fetched", messages=self.values.number(run["cloud_full_messages"], 0),
                                        gb=self.values.number((run["cloud_full_bytes"] or 0) / 1e9, 2)))
                if run.get("cloud_logins_after_removal") is not None:
                    parts.append(self.w("after_removal", n=run["cloud_logins_after_removal"]))
                lines.append(f"• {name} {run['run']}: " + ", ".join(parts))
        return "\n".join(lines)

    def after_block(self, comparisons: list[str]) -> str:
        parts = []
        for comparison_id in comparisons:
            comparison = self.results["comparisons"][comparison_id]
            task_id = (comparison.get("evidence") or {}).get("task") or next(iter(comparison["tasks"]))
            task = comparison["tasks"][task_id]
            for side_name in ("left", "right"):
                side = task[side_name]
                run = next((r for r in side["runs"] if r["run"] == side.get("median_run")), None)
                if run is None:
                    continue
                notes = []
                tail = run.get("tail") or {}
                if tail.get("recorded_s"):
                    notes.append(self.w("after_screen", frames=tail["significant_frames"], recorded=tail["recorded_s"])
                                 if tail.get("significant_frames") else self.w("after_quiet",
                                                                               recorded=tail["recorded_s"]))
                window = ((run.get("evidence") or {}).get("windows") or {}).get("after_steps")
                if window:
                    downloads = sum(s.get("downloads", 0) for s in window["sources"])
                    notes.append(self.w("after_fetch", messages=sum(window["full_messages"].values()),
                                        downloads=downloads))
                if notes:
                    parts.append(f"{side['name']}: " + "; ".join(notes))
        return " · ".join(parts) or self.w("none")

    def credits(self) -> dict:
        voice = None
        if self.voice_dir and (self.voice_dir / self.language / "credit.json").exists():
            credit = json.loads((self.voice_dir / self.language / "credit.json").read_text())
            voice = ", ".join(str(x) for x in (credit.get("engine"), credit.get("voice")) if x)
        music = (self.config.get("compose") or {}).get("music_license") or {}
        music_text = (f"“{music['title']}” by {music['author']} ({music['license']})" if music.get("title")
                      else self.w("none"))
        return {"voice_credit": voice, "music_credit": music_text}

    def fill(self, comparisons: list[str]):
        v = self.values
        for comparison_id in comparisons:
            comparison = self.results["comparisons"][comparison_id]
            for task_id, task in comparison["tasks"].items():
                v.set_text(f"block.runs.{comparison_id}.{task_id}", self.runs_block(task))
                v.set_text(f"block.actions.{comparison_id}.{task_id}", self.actions_block(task))
            v.set_text(f"block.evidence.{comparison_id}", self.evidence_block(comparison))
        deviations = self.config.get("deviations") or []
        if isinstance(deviations, dict):
            deviations = deviations.get(self.language) or deviations.get("en") or []
        v.set_text("block.deviations", "; ".join(deviations) or self.w("none"))
        v.set_text("block.after", self.after_block(comparisons))
        for key in ("page_url", "repo_url", "imprint_url"):
            value = self.config.get(f"publish.{key}")
            if value:
                v.set_text(key, str(value))
        for key, value in self.credits().items():
            if value:
                v.set_text(key, value)

    def render(self, template_dir: Path, variant: str, out_dir: Path, comparisons: list[str],
               allow_missing: bool = False) -> dict:
        self.fill(comparisons)
        out_dir.mkdir(parents=True, exist_ok=True)
        report = {}
        for kind, suffix in (("youtube", "youtube.txt"), ("expander", "expander.md")):
            template = template_dir / f"{variant}.{self.language}.{suffix}"
            if not template.exists():
                raise MethodError(f"No method template {template}")
            text, missing = MethodTemplate.render(template.read_text(encoding="utf-8"), self.values)
            if missing and not allow_missing:
                raise MethodError(f"{template.name}: no value for {', '.join(missing)}")
            out = out_dir / template.name
            out.write_text(text, encoding="utf-8")
            entry = {"file": str(out), "characters": len(text), "missing": missing}
            if kind == "youtube":
                problems = []
                size = len(text.encode("utf-8"))
                entry["bytes"] = size
                if size > 5000:
                    problems.append(f"{size} bytes (YouTube allows 5,000 bytes)")
                if "<" in text or ">" in text:
                    problems.append("contains < or > (YouTube rejects them)")
                if problems:
                    raise MethodError(f"{template.name}: " + "; ".join(problems))
            else:
                html_path = out.with_suffix(".html")
                html_path.write_text(self.to_html(text), encoding="utf-8")
                entry["html"] = str(html_path)
            report[kind] = entry
        return report

    @staticmethod
    def to_html(text: str) -> str:
        blocks = []
        for paragraph in text.strip().split("\n\n"):
            lines = paragraph.split("\n")
            bullets = [line for line in lines if line.startswith("• ")]
            head = [line for line in lines if not line.startswith("• ")]
            if head:
                blocks.append("<p>" + "<br>".join(html.escape(line) for line in head) + "</p>")
            if bullets:
                blocks.append("<ul>" + "".join(f"<li>{html.escape(line[2:])}</li>" for line in bullets) + "</ul>")
        return "\n".join(blocks) + "\n"
