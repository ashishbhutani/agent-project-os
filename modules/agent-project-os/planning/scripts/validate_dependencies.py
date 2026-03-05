#!/usr/bin/env python3
"""Validate dependency readiness and claim next ticket deterministically."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

DONE_STATUS = "done"
CLAIMABLE_STATUSES = {"todo", "ready"}


def load_tracker(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Tracker CSV has no header: {path}")
        return list(reader.fieldnames), [dict(row) for row in reader]


def load_dependencies(path: Path) -> Dict[str, List[str]]:
    deps: Dict[str, List[str]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = (row.get("From") or "").strip()
            dst = (row.get("To") or "").strip()
            dep_type = (row.get("DependencyType") or "").strip().lower()
            if not src or not dst:
                continue
            if dep_type and dep_type != "blocks":
                continue
            deps.setdefault(dst, []).append(src)
    return deps


def status_map(rows: List[Dict[str, str]]) -> Dict[str, str]:
    return {
        (row.get("Key") or "").strip(): (row.get("Status") or "").strip().lower()
        for row in rows
        if (row.get("Key") or "").strip()
    }


def blockers_for(
    key: str,
    row: Dict[str, str],
    dep_map: Dict[str, List[str]],
    statuses: Dict[str, str],
) -> List[str]:
    blockers = dep_map.get(key)
    if blockers is None:
        blockers = [b.strip() for b in (row.get("BlockedBy") or "").split("|") if b.strip()]
    return sorted([b for b in blockers if statuses.get(b) != DONE_STATUS])


def ready_keys(rows: List[Dict[str, str]], dep_map: Dict[str, List[str]]) -> List[str]:
    statuses = status_map(rows)
    out: List[str] = []
    for row in rows:
        key = (row.get("Key") or "").strip()
        status = (row.get("Status") or "").strip().lower()
        if not key or status not in CLAIMABLE_STATUSES:
            continue
        if blockers_for(key, row, dep_map, statuses):
            continue
        out.append(key)
    return sorted(out)


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


def claim_next(tracker: Path, deps: Path, lock: Path, agent: str, dry_run: bool) -> int:
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)

        header, rows = load_tracker(tracker)
        dep_map = load_dependencies(deps)
        ready = ready_keys(rows, dep_map)

        if not ready:
            print("NO_READY_TICKETS")
            return 3

        chosen = ready[0]
        for row in rows:
            if (row.get("Key") or "").strip() != chosen:
                continue
            row["Status"] = "in_progress"
            row["Assignee"] = agent
            row["Branch"] = (row.get("Branch") or "").strip() or f"ticket/{chosen}"
            row["Worktree"] = (row.get("Worktree") or "").strip() or f"wt-{chosen.lower()}"
            row["LastUpdatedUTC"] = now_utc()
            row["Notes"] = f"Claimed by {agent} via deterministic claim loop."
            break

        if not dry_run:
            atomic_write(tracker, header, rows)

        print(chosen)
        return 0


def can_start(tracker: Path, deps: Path, key: str) -> int:
    _, rows = load_tracker(tracker)
    dep_map = load_dependencies(deps)
    statuses = status_map(rows)

    target = next((r for r in rows if (r.get("Key") or "").strip() == key), None)
    if target is None:
        print(f"UNKNOWN_TICKET {key}")
        return 2

    status = (target.get("Status") or "").strip().lower()
    if status not in CLAIMABLE_STATUSES:
        print(f"NOT_CLAIMABLE status={status}")
        return 1

    blockers = blockers_for(key, target, dep_map, statuses)
    if blockers:
        print(f"BLOCKED blockers={'|'.join(blockers)}")
        return 1

    print("READY")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tracker", required=True)
    p.add_argument("--dependencies", required=True)
    p.add_argument("--lock-file", default="planning/.claim.lock")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list-ready", action="store_true")
    mode.add_argument("--can-start", metavar="TICKET")
    mode.add_argument("--claim-next", action="store_true")

    p.add_argument("--agent", default="agent-unknown")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    a = parse_args()
    tracker = Path(a.tracker)
    deps = Path(a.dependencies)

    if a.list_ready:
        _, rows = load_tracker(tracker)
        for key in ready_keys(rows, load_dependencies(deps)):
            print(key)
        return 0

    if a.can_start:
        return can_start(tracker, deps, a.can_start)

    return claim_next(
        tracker=tracker,
        deps=deps,
        lock=Path(a.lock_file),
        agent=a.agent,
        dry_run=a.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
