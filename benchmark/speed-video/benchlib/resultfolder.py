import json
import os
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path


class ResultFolderError(Exception):
    pass


class ResultFolder:
    """One session's self-describing output (README, "Result folder format"): manifest.json, runs/<app>/<task>/<run>/,
    results.json, evidence.json, report.md, logs/. The Linux session here and Ben's Windows session write the same
    layout; analysis, compose and the method texts read it."""

    format_name = "parula-speed-results"
    version = 1

    def __init__(self, path: Path):
        self.path = Path(path).resolve()

    @classmethod
    def create(cls, parent: Path, os_name: str, now: datetime | None = None) -> "ResultFolder":
        stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M")
        path = Path(parent) / f"results-{os_name}-{stamp}"
        suffix = 2
        while path.exists():
            path = Path(parent) / f"results-{os_name}-{stamp}-{suffix}"
            suffix += 1
        (path / "runs").mkdir(parents=True)
        (path / "logs").mkdir()
        folder = cls(path)
        folder.write_manifest(format=cls.format_name, version=cls.version, os=os_name,
                              created_utc=datetime.now().astimezone().isoformat())
        return folder

    @classmethod
    def open(cls, path) -> "ResultFolder":
        folder = cls(Path(path))
        manifest = folder.path / "manifest.json"
        if not manifest.exists():
            raise ResultFolderError(f"{folder.path} is not a result folder (no manifest.json)")
        data = json.loads(manifest.read_text())
        if data.get("format") != cls.format_name:
            raise ResultFolderError(f"{manifest}: format '{data.get('format')}', expected '{cls.format_name}'")
        if int(data.get("version", 0)) > cls.version:
            raise ResultFolderError(f"{manifest}: version {data.get('version')} is newer than this tool reads")
        return folder

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def runs_dir(self) -> Path:
        return self.path / "runs"

    @property
    def logs_dir(self) -> Path:
        path = self.path / "logs"
        path.mkdir(exist_ok=True)
        return path

    @property
    def results_path(self) -> Path:
        return self.path / "results.json"

    @property
    def evidence_path(self) -> Path:
        return self.path / "evidence.json"

    @property
    def report_path(self) -> Path:
        return self.path / "report.md"

    def run_dir(self, app_id: str, task_id: str, run_id: str) -> Path:
        return self.runs_dir / app_id / task_id / run_id

    def run_dirs(self, app_id: str, task_id: str) -> list[Path]:
        """Recorded runs (warm-ups and measured), without failed attempts that were recorded again."""
        root = self.runs_dir / app_id / task_id
        if not root.exists():
            return []
        return sorted(p for p in root.iterdir() if (p / "meta.json").exists() and ".failed-" not in p.name)

    def relative(self, path: Path) -> str:
        return Path(path).resolve().relative_to(self.path).as_posix()

    def manifest(self) -> dict:
        path = self.path / "manifest.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def write_manifest(self, **sections):
        data = self.manifest()
        data.update(sections)
        (self.path / "manifest.json").write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    @property
    def zip_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.zip")

    @property
    def small_zip_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}-small.zip")

    def needed_recordings(self) -> set[str]:
        """The run folders whose recordings the composition uses (results.json): per comparison, task and side the
        median run, or the run shown for a time limit."""
        if not self.results_path.exists():
            return set()
        results = json.loads(self.results_path.read_text())
        needed = set()
        for comparison in (results.get("comparisons") or {}).values():
            for task in (comparison.get("tasks") or {}).values():
                for side in (task.get(name) or {} for name in ("left", "right")):
                    shown = {side.get("median_run"), side.get("timeout_run")} - {None}
                    needed |= {r["dir"] for r in side.get("runs") or [] if r.get("run") in shown and r.get("dir")}
        return needed

    def zip(self, small: bool = False) -> Path:
        """The folder as a zip next to it. `small`: every file except the recordings the composition doesn't use
        (`needed_recordings`): the one to send. Recordings and images are stored as they are (they don't compress)."""
        recordings = {".mkv", ".mp4", ".webm"}
        stored = recordings | {".png", ".jpg", ".npz", ".zip"}
        needed = self.needed_recordings() if small else set()
        target = self.small_zip_path if small else self.zip_path
        partial = target.with_name(target.name + ".partial")
        with zipfile.ZipFile(partial, "w", allowZip64=True) as archive:
            for path in sorted(self.path.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(self.path).as_posix()
                if small and path.suffix.lower() in recordings and \
                        not any(relative.startswith(run + "/") for run in needed):
                    continue
                compression = zipfile.ZIP_STORED if path.suffix.lower() in stored else zipfile.ZIP_DEFLATED
                archive.write(path, f"{self.path.name}/{relative}", compress_type=compression)
        os.replace(partial, target)
        return target

    def package(self, os_label: str, ok: bool, problem: str | None = None, full: bool = True,
                progress=print) -> str:
        """README-FIRST.txt, the small zip and (unless `full` is False) the zip of everything; README-FIRST is
        written again with the sizes once the zips exist. Returns its text."""
        ReadmeFirst.write(self, os_label, ok, problem, full)
        progress(f"writing {self.small_zip_path.name}")
        self.zip(small=True)
        if full:
            progress(f"writing {self.zip_path.name}")
            self.zip()
        return ReadmeFirst.write(self, os_label, ok, problem, full)

    @staticmethod
    def tool_version(source_dir: Path) -> dict:
        def git(*args) -> str | None:
            try:
                return subprocess.run(["git", *args], cwd=source_dir, capture_output=True, text=True,
                                      timeout=10).stdout.strip() or None
            except (OSError, subprocess.TimeoutExpired):
                return None
        status = git("status", "--porcelain", "--", ".")
        return {"git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(status) if status is not None else None,
                "git_branch": git("rev-parse", "--abbrev-ref", "HEAD")}


class ReadmeFirst:
    """README-FIRST.txt in the result folder, for the person who ran the test: where the results are, how big,
    what to send (the small zip)."""

    @staticmethod
    def size(path: Path) -> str:
        if not path.exists():
            return "being written"
        total = sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else path.stat().st_size
        return f"{total / 1e9:.1f} GB" if total >= 1e9 else f"{total / 1e6:.0f} MB"

    @classmethod
    def write(cls, folder: ResultFolder, os_label: str, ok: bool, problem: str | None = None,
              full: bool = True) -> str:
        lines = [f"Parula speed test on {os_label}: " + ("finished." if ok else "stopped before the end."), ""]
        if problem:
            lines += [f"Why: {problem}", ""]
        lines += [f"Results folder: {folder.path}  ({cls.size(folder.path)})", "",
                  f"Please send this file to the Parula team: {folder.small_zip_path}  "
                  f"({cls.size(folder.small_zip_path)})",
                  "  It holds every measurement, log, check and screenshot of every run, and the screen recordings "
                  "the videos are made from (the median run of each app). If it is too large for e-mail, share it "
                  "as a link from OneDrive, Google Drive or Dropbox."]
        if full:
            lines += ["", f"Everything, with all recordings: {folder.zip_path}  ({cls.size(folder.zip_path)})",
                      "  Please keep it (or the results folder) until the Parula team confirms they have what they "
                      "need; they may ask for it."]
        lines += ["", "The folder contains no password. The test account's address is visible in the screen recordings "
                      "(typed into each app's setup) and in the apps' own logs; the data files name only its domain."]
        if os_label == "Windows":
            lines.append("Everything the test changed on this computer has been undone (see logs/cleanup.txt).")
        text = "\n".join(lines) + "\n"
        (folder.path / "README-FIRST.txt").write_text(text, encoding="utf-8")
        return text
