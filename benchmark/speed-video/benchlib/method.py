import html
import json
import re
from pathlib import Path

import yaml

from .compose import PaneLabels, ShortSettings
from .narration import MethodTemplate, NarrationValues


class MethodError(Exception):
    pass


class ManifestTexts:
    """Sentences a result folder's manifest.json records (`instrumentation`, `deviations`: what that session
    actually used), in the method text's language: as recorded (English), or translated sentence by sentence from
    `translations/<lang>.yaml` and the config's `translations.<lang>`. A sentence without a translation leaves the
    block without a value; `untranslated` names it."""

    def __init__(self, config, language: str):
        self.language = language
        self.table = {}
        path = Path(__file__).resolve().parent.parent / "translations" / f"{language}.yaml"
        if language != "en" and path.exists():
            self.table.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        self.table.update((config.get("translations") or {}).get(language) or {})
        self.untranslated: dict[str, list[str]] = {}

    def lines(self, folder: Path, key: str) -> list[str] | None:
        path = Path(folder) / "manifest.json"
        recorded = (json.loads(path.read_text()) if path.exists() else {}).get(key)
        if isinstance(recorded, dict):
            if recorded.get(self.language) is not None:
                return list(recorded[self.language])
            recorded = recorded.get("en")
        if recorded is None:
            return None
        if self.language == "en":
            return list(recorded)
        missing = [line for line in recorded if not self.table.get(line)]
        if missing:
            self.untranslated[f"{Path(folder).name}/manifest.json {key}"] = missing
            return None
        return [self.table[line] for line in recorded]

    def block(self, folders: list[Path], key: str, separator: str, list_items: bool = False,
              summary: bool = False) -> str | None:
        """One text from the folders' sentences ("Linux: … Windows: …" for several folders); `list_items` joins
        them as items of one sentence, without their final periods; `summary`: only their number and subjects."""
        parts = []
        for folder in folders:
            lines = self.lines(folder, key)
            if lines is None:
                return None
            if list_items:
                lines = [line.rstrip(".") for line in lines]
            text = self.summary(lines) if summary else separator.join(lines)
            if len(folders) > 1:
                os_name = str(json.loads((Path(folder) / "manifest.json").read_text()).get("os") or "").capitalize()
                text = f"{os_name}: {text}"
            parts.append(text)
        return separator.join(parts) if parts else None

    @staticmethod
    def summary(lines: list[str]) -> str:
        """The short form of a list for the YouTube text: its length and the subjects its sentences start with
        ("Thunderbird: …"), e.g. "7 (Test computer, Thunderbird, Parula)"; the website has the whole list."""
        if not lines:
            return ""
        subjects = []
        for line in lines:
            match = re.match(r"([^:.;,]{1,40}): ", line)
            if match and match.group(1) not in subjects:
                subjects.append(match.group(1))
        return f"{len(lines)} ({', '.join(subjects)})" if subjects else str(len(lines))


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
               "connections": "{n} connection(s) to the mail server", "no_connections": "no connection to the mail "
                                                                                       "server",
               "also": "also {n} connection(s) to {owner} ({asn}, {prefix})", "inbox_complete": "Inbox complete",
               "inbox_incomplete": "Inbox not complete", "no_network": "no network evidence",
               "after_download": "{mb} MB more from the mail server after the list was complete, until the app was closed",
               "warmup_run": "warm-up", "failed_attempt": "failed attempt, recorded again", "none": "none"},
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
               "connections": "{n} Verbindung(en) zum Mailserver", "no_connections": "keine Verbindung zum Mailserver",
               "also": "außerdem {n} Verbindung(en) zu {owner} ({asn}, {prefix})",
               "inbox_complete": "Posteingang vollständig", "inbox_incomplete": "Posteingang nicht vollständig",
               "no_network": "keine Netzwerk-Belege",
               "after_download": "{mb} MB mehr vom Mailserver nach der vollständigen Liste bis zum Schließen der App",
               "warmup_run": "Aufwärmlauf", "failed_attempt": "fehlgeschlagener Versuch, erneut aufgenommen",
               "none": "keine"},
    }

    def __init__(self, config, results: dict, values: NarrationValues, language: str, voice_dir: Path | None,
                 settings: ShortSettings | None = None):
        self.config = config
        self.results = results
        self.values = values
        self.language = language if language in self.words else "en"
        self.voice_dir = voice_dir
        self.labels = PaneLabels(settings or ShortSettings(None, config.get("compose") or {}), language)
        self.manifest_texts = ManifestTexts(config, self.language)

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

    def runs_block(self, comparison_id: str, task: dict) -> str:
        rows = []
        for side_name in ("left", "right"):
            side = task[side_name]
            for run in side.get("warmups", []) + side["runs"]:
                rows.append((run["order"] or 0, self.labels.name(comparison_id, side_name, side), run))
        lines = []
        for order, name, run in sorted(rows, key=lambda r: r[0]):
            label = f"{name} ({self.w('warmup')})" if run["warmup"] else name
            lines.append(f"• #{order} {label}: {self.run_text(None, run)}")
        return "\n".join(lines)

    def actions_block(self, comparison_id: str, task: dict) -> str:
        return " · ".join(f"{self.labels.name(comparison_id, n, task[n])} ({task[n]['actions']}): "
                          + "; ".join(task[n]["action_list"]) for n in ("left", "right"))

    def client_evidence_block(self, comparison_id: str, comparison: dict, evidence: dict) -> str:
        lines = []
        for side_name, data in evidence["sides"].items():
            name = self.labels.name(comparison_id, side_name, comparison["tasks"][evidence["task"]][side_name])
            if not data["runs_with_evidence"]:
                lines.append(f"• {name}: {self.w('no_network')}")
                continue
            for run in data["runs"]:
                count = run.get("server_connections")
                if count is None:
                    count = run.get("direct_connections") or 0
                parts = [self.w("connections", n=count) if count else self.w("no_connections")]
                for network in run.get("remote_networks", []):
                    if network.get("connections"):
                        parts.append(self.w("also", n=network["connections"], owner=network.get("owner"),
                                            asn=network.get("asn") or "–", prefix=network.get("prefix") or "–"))
                if run.get("inbox_complete") is not None:
                    parts.append(self.w("inbox_complete" if run["inbox_complete"] else "inbox_incomplete"))
                kind = {"warm-up": f" ({self.w('warmup_run')})", "attempt": f" ({self.w('failed_attempt')})"}.get(
                    run.get("kind"), "")
                lines.append(f"• {name} {run['run']}{kind}: " + ", ".join(parts))
        return "\n".join(lines)

    def evidence_block(self, comparison_id: str, comparison: dict) -> str:
        evidence = comparison.get("evidence") or {}
        if evidence.get("kind") == "client":
            block = self.client_evidence_block(comparison_id, comparison, evidence)
            if comparison.get("server_evidence"):
                block += "\n" + self.server_evidence_block(comparison_id, comparison, comparison["server_evidence"])
            return block
        return self.server_evidence_block(comparison_id, comparison, evidence)

    def server_evidence_block(self, comparison_id: str, comparison: dict, evidence: dict) -> str:
        if not evidence.get("sides"):
            return self.w("no_evidence")
        lines = []
        for side_name, data in evidence["sides"].items():
            name = self.labels.name(comparison_id, side_name, comparison["tasks"][evidence["task"]][side_name])
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
                after = (run.get("evidence") or {}).get("direct_bytes_after_measured_end")
                if after is not None:
                    notes.append(self.w("after_download", mb=self.values.number(after / 1e6, 1)))
                window = ((run.get("server_evidence") or {}).get("windows") or {}).get("after_steps")
                if window:
                    downloads = sum(s.get("downloads", 0) for s in window["sources"])
                    notes.append(self.w("after_fetch", messages=sum(window["full_messages"].values()),
                                        downloads=downloads))
                if notes:
                    parts.append(f"{self.labels.named(comparison_id, side_name, side)}: " + "; ".join(notes))
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

    def folders(self, comparisons: list[str]) -> list[Path]:
        """The result folders of these comparisons, in their order."""
        out = []
        for comparison_id in comparisons:
            folder = self.results["comparisons"][comparison_id].get("result_folder")
            if folder and Path(folder) not in out and (Path(folder) / "manifest.json").exists():
                out.append(Path(folder))
        return out

    def config_lines(self, key: str) -> list[str]:
        lines = self.config.get(key) or []
        if isinstance(lines, dict):
            lines = lines.get(self.language) or lines.get("en") or []
        return list(lines)

    def fill(self, comparisons: list[str]):
        v = self.values
        for comparison_id in comparisons:
            comparison = self.results["comparisons"][comparison_id]
            for task_id, task in comparison["tasks"].items():
                v.set_text(f"block.runs.{comparison_id}.{task_id}", self.runs_block(comparison_id, task))
                v.set_text(f"block.actions.{comparison_id}.{task_id}", self.actions_block(comparison_id, task))
            v.set_text(f"block.evidence.{comparison_id}", self.evidence_block(comparison_id, comparison))
        folders = self.folders(comparisons)
        for name, key, separator, list_items, summary in (
                ("deviations", "deviations", "; ", True, False), ("deviations_short", "deviations", "; ", True, True),
                ("instrumentation", "instrumentation", " ", False, False)):
            if folders:
                text = self.manifest_texts.block(folders, key, separator, list_items, summary)
            else:
                lines = [line.rstrip(".") if list_items else line for line in self.config_lines(key)]
                text = ManifestTexts.summary(lines) if summary else separator.join(lines)
            if text is not None:
                v.set_text(f"block.{name}", text or self.w("none"))
        v.set_text("block.after", self.after_block(comparisons))
        for key in ("page_url", "repo_url", "imprint_url"):
            value = self.config.get(f"publish.{key}")
            if value:
                v.set_text(key, str(value))
        v.set_text("method_url", str(self.config.get("publish.method_url") or "https://parula.app"))
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
                untranslated = "".join(f"; no {self.language} translation in {where}: " + " | ".join(lines)
                                       for where, lines in self.manifest_texts.untranslated.items())
                raise MethodError(f"{template.name}: no value for {', '.join(missing)}{untranslated}")
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
