#!/usr/bin/env python3
"""Parula speed benchmark and screen-capture pipeline. Run `bench.py --help` and see README.md."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchlib.config import Config  # noqa: E402
from benchlib.corpus import CorpusGenerator, CorpusSpec  # noqa: E402
from benchlib.seed import Seeder  # noqa: E402
from benchlib.stages import Calibrator, Pipeline, SnapshotBuilder  # noqa: E402


def split(value: str | None) -> list[str] | None:
    return [v.strip() for v in value.split(",") if v.strip()] if value else None


class CommandLine:
    def __init__(self):
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--config", default="config.yaml", help="benchmark config (YAML)")
        sub = parser.add_subparsers(dest="command", required=True)

        corpus = sub.add_parser("corpus", help="generate the corpus manifest, or time a full generation")
        corpus.add_argument("action", choices=["manifest", "time", "write"])
        corpus.add_argument("--messages-out", help="also write one JSON line per message")
        corpus.add_argument("--dir", help="for 'write': directory for <folder>/<n>.eml files")

        seed = sub.add_parser("seed", help="import the corpus into the benchmark account, verify, or wipe")
        seed.add_argument("action", choices=["import", "verify", "wipe"])
        seed.add_argument("--protocol", choices=["jmap", "imap"], default="jmap")
        seed.add_argument("--resume", action="store_true", help="continue an interrupted import")

        snapshot = sub.add_parser("snapshot", help="take, restore or list snapshot pairs (server + client profiles)")
        snapshot.add_argument("action", choices=["take", "restore", "list", "server-take", "server-restore"])
        snapshot.add_argument("--name", default="synced")
        snapshot.add_argument("--apps", help="comma-separated app ids")
        snapshot.add_argument("--manual", action="store_true", help="set up the accounts by hand")
        snapshot.add_argument("--sync-wait", type=float, default=60, help="seconds to let each app sync")
        snapshot.add_argument("--no-resync", action="store_true")

        calibrate = sub.add_parser("calibrate", help="click points and regions, window geometry, reference images")
        calibrate.add_argument("action", choices=["points", "window", "references", "crop"])
        calibrate.add_argument("--app")
        calibrate.add_argument("--points", help="only these point or region names")
        calibrate.add_argument("--comparison")
        calibrate.add_argument("--tasks")
        calibrate.add_argument("--run", help="for 'crop': a recorded run directory")
        calibrate.add_argument("--at", type=float, help="for 'crop': video time in seconds")
        calibrate.add_argument("--region", help="for 'crop': calibrated region name")
        calibrate.add_argument("--kind", choices=["opening", "end", "first", "verify"], default="opening")
        calibrate.add_argument("--step", help="for 'crop' of kind end/first/verify")

        env = sub.add_parser("env", help="record the test environment")
        env.add_argument("--comparison", required=True)

        run = sub.add_parser("run", help="record warm-up and measured runs, interleaved")
        run.add_argument("--comparison", required=True)
        run.add_argument("--tasks")
        run.add_argument("--no-resume", action="store_true")
        run.add_argument("--runs", type=int)
        run.add_argument("--warmup", type=int)

        analyze = sub.add_parser("analyze", help="settle detection per run, medians, results.json, report.md")
        analyze.add_argument("--comparison", required=True)
        analyze.add_argument("--force", action="store_true")

        compose = sub.add_parser("compose", help="side-by-side video, cards, timeline, subtitles, audio")
        compose.add_argument("--comparisons", help="default: all in results.json")
        compose.add_argument("--lang", default="en")
        compose.add_argument("--narration", help="the voice-over directory, or a narration.<lang>.json")
        compose.add_argument("--variant", help="c1, c2, c3, c4, combined, … (variants/variants.json)")
        compose.add_argument("--name", default="speed")
        compose.add_argument("--results", help="comma-separated results.json files to merge (e.g. Linux + Windows)")

        method = sub.add_parser("method", help="method texts below the video: YouTube description, website expander")
        method.add_argument("--narration", required=True, help="the voice-over directory (with method/)")
        method.add_argument("--variant", required=True)
        method.add_argument("--lang", default="en")
        method.add_argument("--name", default="speed")
        method.add_argument("--comparisons")
        method.add_argument("--results", help="comma-separated results.json files to merge")
        method.add_argument("--allow-missing", action="store_true", help="draft: render missing values as '–'")

        voice = sub.add_parser("voice", help="text-to-speech for the lines a composition chose (voice-script.json)")
        voice.add_argument("--name", default="speed")
        voice.add_argument("--lang", default="en")
        voice.add_argument("--replace", action="store_true", help="synthesize files that exist again")

        encode = sub.add_parser("encode", help="WebM VP9, MP4 H.264, YouTube master")
        encode.add_argument("--name", default="speed")
        encode.add_argument("--lang", default="en")
        encode.add_argument("--formats", help="webm,mp4,youtube")
        encode.add_argument("--internal-preview", action="store_true",
                            help="encode a variant whose publication condition is false, marked 'not for publication'")

        verify = sub.add_parser("verify", help="check the encoded files with ffprobe")
        verify.add_argument("--name", default="speed")
        verify.add_argument("--lang", default="en")

        everything = sub.add_parser("all", help="env, run, analyze, compose, encode, verify for one comparison")
        everything.add_argument("--comparison", required=True)
        everything.add_argument("--tasks")
        everything.add_argument("--lang", default="en")
        everything.add_argument("--narration")
        everything.add_argument("--variant")
        everything.add_argument("--name", default="speed")
        self.parser = parser

    @staticmethod
    def progress(message: str):
        print(message, file=sys.stderr, flush=True)

    def main(self, argv=None) -> int:
        args = self.parser.parse_args(argv)
        config = Config.load(args.config)
        pipeline = Pipeline(config, self.progress)
        handler = getattr(self, "cmd_" + args.command)
        result = handler(pipeline, config, args)
        if result is not None:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            if isinstance(result, dict) and result.get("ok") is False:
                return 1
        return 0

    def cmd_corpus(self, pipeline, config, args):
        generator = CorpusGenerator(CorpusSpec.from_dict(config.get("corpus")))
        if args.action == "time":
            started = time.monotonic()
            total = 0
            count = 0
            for msg in generator.messages():
                total += len(msg.raw)
                count += 1
            return {"messages": count, "bytes": total, "seconds": round(time.monotonic() - started, 1)}
        if args.action == "write":
            root = Path(args.dir)
            for msg in generator.messages():
                path = root / msg.folder / f"{msg.index:06d}.eml"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(msg.raw)
            return {"written_to": str(root)}
        out = config.workdir / "corpus" / "manifest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        manifest = generator.manifest(Path(args.messages_out) if args.messages_out else None,
                                      lambda n: self.progress(f"  {n} messages"))
        out.write_text(json.dumps(manifest, indent=2))
        return {"manifest": str(out), "messages": manifest["total_messages"], "bytes": manifest["total_bytes"],
                "digest": manifest["digest"]}

    def cmd_seed(self, pipeline, config, args):
        seeder = Seeder(config, self.progress)
        if args.action == "import":
            seeder.seed(args.protocol, args.resume)
            return seeder.verify(args.protocol)
        if args.action == "verify":
            return seeder.verify(args.protocol)
        seeder.wipe()
        return None

    def cmd_snapshot(self, pipeline, config, args):
        apps = split(args.apps) or []
        builder = SnapshotBuilder(pipeline)
        if args.action == "take":
            builder.take(args.name, apps, args.manual, args.sync_wait, not args.no_resync)
        elif args.action == "restore":
            builder.restore(args.name, apps)
        elif args.action == "server-take":
            pipeline.server_snapshots().take(args.name)
        elif args.action == "server-restore":
            pipeline.server_snapshots().restore(args.name)
        else:
            server = pipeline.server_snapshots()
            client_root = config.workdir / "snapshots"
            return {"server": server.list() if server else [],
                    "client": sorted(p.name for p in client_root.glob("*") if p.is_dir()) if client_root.exists() else []}
        return None

    def cmd_calibrate(self, pipeline, config, args):
        calibrator = Calibrator(pipeline)
        if args.action == "points":
            return {"saved": str(calibrator.points(args.app, split(args.points), split(args.tasks)))}
        if args.action == "window":
            return calibrator.window(args.app)
        if args.action == "crop":
            task = (split(args.tasks) or ["T1"])[0]
            return {"saved": calibrator.crop(args.run, args.at, args.app, task, args.region, args.kind, args.step)}
        return {"references": calibrator.references_for(args.comparison, split(args.tasks))}

    def cmd_env(self, pipeline, config, args):
        return pipeline.environment(args.comparison)

    def cmd_run(self, pipeline, config, args):
        pipeline.run(args.comparison, split(args.tasks), not args.no_resume, args.runs, args.warmup)
        return None

    def cmd_analyze(self, pipeline, config, args):
        results = pipeline.analyze(args.comparison, args.force)
        summary = {}
        for task_id, task in results["comparisons"][args.comparison]["tasks"].items():
            summary[task_id] = {side: task[side]["median_s"] for side in ("left", "right")}
            summary[task_id]["ratio"] = task["ratio"]
        return summary

    def cmd_compose(self, pipeline, config, args):
        return pipeline.compose(split(args.comparisons), args.lang, args.narration, args.variant, args.name,
                                split(args.results))

    def cmd_method(self, pipeline, config, args):
        return pipeline.method(split(args.comparisons), args.lang, args.narration, args.variant, args.name,
                               split(args.results), args.allow_missing)

    def cmd_voice(self, pipeline, config, args):
        return pipeline.voice(args.name, args.lang, args.replace)

    def cmd_encode(self, pipeline, config, args):
        return pipeline.encode(args.name, args.lang, split(args.formats), args.internal_preview)

    def cmd_verify(self, pipeline, config, args):
        return pipeline.verify(args.name, args.lang)

    def cmd_all(self, pipeline, config, args):
        pipeline.environment(args.comparison)
        pipeline.run(args.comparison, split(args.tasks), True, None, None)
        pipeline.analyze(args.comparison)
        pipeline.compose([args.comparison], args.lang, args.narration, args.variant, args.name)
        pipeline.encode(args.name, args.lang, None)
        return pipeline.verify(args.name, args.lang)


if __name__ == "__main__":
    sys.exit(CommandLine().main())
