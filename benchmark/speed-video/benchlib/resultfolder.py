import json
import shutil
import subprocess
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

    def zip(self) -> Path:
        archive = shutil.make_archive(str(self.path), "zip", root_dir=self.path.parent, base_dir=self.path.name)
        return Path(archive)

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
