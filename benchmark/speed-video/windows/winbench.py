#!/usr/bin/env python3
"""The Windows test session of the Parula speed benchmark. Started by run-windows-tests.ps1 (which fetches Python,
ffmpeg and Parula first); the password comes only from the environment variable BENCH_PASSWORD."""

import argparse
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from benchlib.config import Config  # noqa: E402
from benchlib.stages import Pipeline  # noqa: E402
from benchlib.winapps import SessionState  # noqa: E402
from benchlib.winsession import Prerequisites, WindowsConfig, WindowsSession  # noqa: E402


class SessionLog:
    """Progress on the console and in a log file, with the password replaced by <secret>."""

    def __init__(self, path: Path, secret: str | None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.secret = secret

    def __call__(self, message: str):
        if self.secret:
            message = message.replace(self.secret, "<secret>")
        line = f"{datetime.now():%H:%M:%S} {message}"
        print(line, flush=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


class CommandLine:
    def __init__(self):
        parser = argparse.ArgumentParser(description=__doc__)
        sub = parser.add_subparsers(dest="command", required=True)
        for name, text in (("check", "check the prerequisites, change nothing"),
                           ("session", "run the whole test session"),
                           ("cleanup", "undo what an interrupted session changed")):
            command = sub.add_parser(name, help=text)
            command.add_argument("--root", required=True, help="the benchmark folder (tools, state, results)")
            if name != "cleanup":
                command.add_argument("--server", required=True)
                command.add_argument("--email", required=True)
                command.add_argument("--ffmpeg", required=True)
                command.add_argument("--ffprobe", required=True)
                command.add_argument("--parula-exe", required=True)
                command.add_argument("--outlook-exe", default="")
        self.parser = parser
        self.code = Path(__file__).resolve().parent.parent

    def config(self, args, display: dict | None = None) -> tuple[Config, Path]:
        root = Path(args.root).resolve()
        values = {"root": root, "code": self.code, "server": args.server, "email": args.email,
                  "ffmpeg": args.ffmpeg, "ffprobe": args.ffprobe, "parula_exe": args.parula_exe,
                  "outlook_exe": args.outlook_exe or "OUTLOOK.EXE"}
        data = WindowsConfig.build(self.code / "windows" / "config.windows.yaml", values, display)
        path = root / "state" / "config.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return Config.load(path), path

    @staticmethod
    def desktop(config: Config):
        from benchlib.windows import WindowsDesktop
        return WindowsDesktop(int(config.get("display.monitor", 0)))

    def prerequisites(self, args, progress) -> tuple[dict, Config, Path]:
        config, path = self.config(args)
        desktop = self.desktop(config)
        account = Pipeline(config, progress).account()
        result = Prerequisites(config, desktop, account.check.run, progress).run(Path(args.root))
        config, path = self.config(args, result["display"] if result["display"]["ok"] else None)
        return result, config, path

    @staticmethod
    def print_checks(result: dict, progress):
        for check in result["checks"]:
            mark = "ok  " if check["ok"] else ("FAIL" if check["fatal"] else "note")
            progress(f"  [{mark}] {check['name']}: {check['detail']}")
            if not check["ok"] and check.get("fix"):
                progress(f"         → {check['fix']}")

    def cmd_check(self, args) -> int:
        progress = SessionLog(Path(args.root) / "state" / "check.log", os.environ.get("BENCH_PASSWORD"))
        result, _, _ = self.prerequisites(args, progress)
        (Path(args.root) / "state" / "prerequisites.json").write_text(json.dumps(result, indent=2,
                                                                                  ensure_ascii=False))
        self.print_checks(result, progress)
        return 0 if result["ok"] else 1

    def pending_cleanup(self, root: Path) -> bool:
        state = SessionState(root / "state" / "session-state.json")
        return any(state.get(key) for key in ("parula_moved", "parula_aside", "outlook_profile",
                                              "outlook_new_account_pending", "settings_saved", "parula_updates"))

    def cmd_cleanup(self, args) -> int:
        root = Path(args.root).resolve()
        progress = SessionLog(root / "state" / "cleanup.log", os.environ.get("BENCH_PASSWORD"))
        path = root / "state" / "config.yaml"
        if not path.exists():
            progress("nothing to clean up (no session config)")
            return 0
        config = Config.load(path)
        session = WindowsSession(config, root, progress, desktop=self.desktop(config))
        for line in session.cleanup():
            progress(f"  cleanup: {line}")
        return 0

    def cmd_session(self, args) -> int:
        root = Path(args.root).resolve()
        password = os.environ.get("BENCH_PASSWORD")
        progress = SessionLog(root / "state" / "session.log", password)
        if not password:
            progress("BENCH_PASSWORD is not set")
            return 2
        result, config, config_path = self.prerequisites(args, progress)
        self.print_checks(result, progress)
        if not result["ok"]:
            progress("The test can't start; fix the items marked FAIL above and start it again.")
            return 1
        session = WindowsSession(config, root, progress, desktop=self.desktop(config))
        if self.pending_cleanup(root):
            progress("A previous session didn't finish; undoing its changes first.")
            for line in session.cleanup():
                progress(f"  cleanup: {line}")
        problem = None
        exit_code = 0
        try:
            problem = session.run()
            exit_code = 1 if problem else 0
        except KeyboardInterrupt:
            problem, exit_code = "stopped with Ctrl+C", 130
        except Exception as ex:
            problem, exit_code = session.hide_address(f"{type(ex).__name__}: {ex}"), 1
            progress(session.hide_address(traceback.format_exc()))
        finally:
            done = session.cleanup()
            for line in done:
                progress(f"  cleanup: {line}")
        if session.folder is None:
            progress(f"The session stopped before its result folder existed: {problem}")
            return exit_code or 1
        logs = session.folder.logs_dir
        (logs / "cleanup.txt").write_text("\n".join(done) + "\n", encoding="utf-8")
        for name, copy in (("session.log", "console.log"), ("check.log", "check.log"),
                           ("bootstrap.log", "bootstrap.log"), ("code.json", "code.json"), ("parula.json", "parula.json")):
            source = root / "state" / name
            if source.exists():
                (logs / copy).write_text(session.hide_address(source.read_text(encoding="utf-8", errors="replace")),
                                         encoding="utf-8")
        (session.folder.path / "prerequisites.json").write_text(
            session.hide_address(json.dumps(result, indent=2, ensure_ascii=False)), encoding="utf-8")
        if not session.folder.results_path.exists():
            try:
                session.pipeline.analyze(next(iter(config.get("comparisons"))))
            except Exception as ex:
                progress(f"analysis of the runs so far failed: {type(ex).__name__}: {ex}")
        text = session.folder.package("Windows", problem is None, problem, progress=progress)
        progress("")
        for line in text.splitlines():
            progress(line)
        return exit_code

    def main(self, argv=None) -> int:
        args = self.parser.parse_args(argv)
        return getattr(self, "cmd_" + args.command)(args)


if __name__ == "__main__":
    sys.exit(CommandLine().main())
