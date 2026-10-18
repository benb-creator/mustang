#!/usr/bin/env python3
"""Checks the server snapshot/restore of a benchmark config against the real (dedicated) server.

Storage level: takes snapshot `check`, mutates the account (flag, delete, move), restores, and requires the same
JMAP ids, the same IMAP UIDs and UIDVALIDITY per folder, and the mutation undone.
With --protocol-level also: wipe + re-import (ids and UIDVALIDITY are expected to change; counts must match).

Usage: snapshot_check.py --config config.yaml [--protocol-level]   (password from the env var named in the config)
This wipes and restores the benchmark account. Run it only against the dedicated benchmark instance.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchlib.config import Config  # noqa: E402
from benchlib.seed import Seeder  # noqa: E402
from benchlib.stages import Pipeline  # noqa: E402


def log(message: str):
    print(message, file=sys.stderr, flush=True)


class SnapshotCheck:
    def __init__(self, config: Config):
        self.config = config
        self.seeder = Seeder(config, log)
        self.pipeline = Pipeline(config, log)

    def state(self) -> dict:
        client = self.seeder.jmap()
        boxes = client.folder_paths()
        jmap = {path: sorted(client.query_ids({"inMailbox": m["id"]})) for path, m in boxes.items()}
        flagged = client.query_count({"hasKeyword": "$flagged"})
        account = self.seeder.imap()
        try:
            imap = {}
            for _, name in account.folders():
                status = account.status(name)
                imap[name] = {"uidvalidity": status["UIDVALIDITY"], "uidnext": status["UIDNEXT"],
                              "uids": account.uids(name)}
        finally:
            account.close()
        return {"jmap": jmap, "imap": imap, "flagged": flagged, "folder_ids": {p: m["id"] for p, m in boxes.items()}}

    def mutate(self, before: dict) -> dict:
        client = self.seeder.jmap()
        inbox = next(p for p in before["jmap"] if p.lower() == "inbox")
        ids = before["jmap"][inbox]
        target = before["folder_ids"].get("Projects/Done") or before["folder_ids"][inbox]
        client.one("Email/set", {"update": {ids[0]: {"keywords/$flagged": True},
                                            ids[1]: {"mailboxIds": {target: True}}},
                                 "destroy": [ids[2]]})
        return {"flagged": ids[0], "moved": ids[1], "destroyed": ids[2]}

    def compare(self, a: dict, b: dict) -> list[str]:
        problems = []
        if a["jmap"] != b["jmap"]:
            problems.append("JMAP ids per folder differ")
        if a["folder_ids"] != b["folder_ids"]:
            problems.append("folder ids differ")
        for name, s in a["imap"].items():
            t = b["imap"].get(name)
            if t is None:
                problems.append(f"IMAP folder {name} missing")
            elif s != t:
                problems.append(f"IMAP {name}: UIDVALIDITY {s['uidvalidity']}→{t['uidvalidity']}, "
                                f"UIDs equal: {s['uids'] == t['uids']}")
        if a["flagged"] != b["flagged"]:
            problems.append(f"flagged count {a['flagged']}→{b['flagged']}")
        return problems

    def storage_level(self) -> dict:
        server = self.pipeline.server_snapshots()
        started = time.monotonic()
        server.take("check")
        take_s = time.monotonic() - started
        before = self.state()
        mutation = self.mutate(before)
        mutated = self.state()
        changed = self.compare(before, mutated)
        started = time.monotonic()
        server.restore("check")
        restore_s = time.monotonic() - started
        after = self.state()
        problems = self.compare(before, after)
        return {"take_s": round(take_s, 1), "restore_s": round(restore_s, 1), "mutation": mutation,
                "mutation_visible_before_restore": changed, "differences_after_restore": problems,
                "messages": sum(len(v) for v in before["jmap"].values()),
                "uidvalidity": {k: v["uidvalidity"] for k, v in before["imap"].items()},
                "ok": bool(changed) and not problems}

    def protocol_level(self) -> dict:
        before = self.state()
        started = time.monotonic()
        self.seeder.wipe()
        self.seeder.seed("jmap")
        duration = time.monotonic() - started
        after = self.state()
        verify = self.seeder.verify("jmap")
        counts_equal = {p: len(v) for p, v in before["jmap"].items()} == {p: len(v) for p, v in after["jmap"].items()}
        ids_changed = before["jmap"] != after["jmap"]
        uidvalidity_changed = any(before["imap"][n]["uidvalidity"] != after["imap"].get(n, {}).get("uidvalidity")
                                  for n in before["imap"] if n.upper() != "INBOX")
        return {"seconds": round(duration, 1), "counts_equal": counts_equal, "verify_ok": verify["ok"],
                "ids_changed": ids_changed, "uidvalidity_changed_for_recreated_folders": uidvalidity_changed,
                "ok": counts_equal and verify["ok"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--protocol-level", action="store_true")
    args = parser.parse_args()
    check = SnapshotCheck(Config.load(args.config))
    report = {"storage_level": check.storage_level()}
    if args.protocol_level:
        report["protocol_level"] = check.protocol_level()
    report["ok"] = all(r["ok"] for r in report.values() if isinstance(r, dict))
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
