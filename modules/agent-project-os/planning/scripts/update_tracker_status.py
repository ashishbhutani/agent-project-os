#!/usr/bin/env python3
"""Race-safe tracker status updates for multi-agent loops."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple


VALID_STATUS = {"todo", "ready", "in_progress", "blocked", "in_review", "done"}


def load_tracker(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Tracker CSV has no header: {path}")
        return list(reader.fieldnames), [dict(row) for row in reader]


def atomic_write(path: Path, header: List[str], rows: List[Dict[str, str]]) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in header})
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tracker", required=True)
    p.add_argument("--lock-file", default="planning/.claim.lock")
    p.add_argument("--ticket", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--assignee")
    p.add_argument("--branch")
    p.add_argument("--worktree")
    p.add_argument("--prurl")
    p.add_argument("--merge-commit")
    p.add_argument("--tests")
    p.add_argument("--docs-updated")
    p.add_argument("--notes")
    args = p.parse_args()

    status = args.status.strip().lower()
    if status not in VALID_STATUS:
        raise ValueError(f"Invalid status: {status}")

    tracker = Path(args.tracker)
    lock = Path(args.lock_file)
    lock.parent.mkdir(parents=True, exist_ok=True)

    with lock.open("a+", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        header, rows = load_tracker(tracker)

        found = False
        for row in rows:
            key = (row.get("Key") or "").strip()
            if key != args.ticket:
                continue
            found = True
            row["Status"] = status
            row["LastUpdatedUTC"] = now_utc()

            if args.assignee is not None:
                row["Assignee"] = args.assignee
            if args.branch is not None:
                row["Branch"] = args.branch
            if args.worktree is not None:
                row["Worktree"] = args.worktree
            if args.prurl is not None:
                row["PRURL"] = args.prurl
            if args.merge_commit is not None:
                row["MergeCommit"] = args.merge_commit
            if args.tests is not None:
                row["Tests"] = args.tests
            if args.docs_updated is not None:
                row["DocsUpdated"] = args.docs_updated
            if args.notes is not None:
                row["Notes"] = args.notes
            break

        if not found:
            print(f"UNKNOWN_TICKET {args.ticket}")
            return 2

        atomic_write(tracker, header, rows)

    print(f"UPDATED {args.ticket} status={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
