#!/usr/bin/env python3
"""Write worker/mayor runtime state and append bounded events."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import tempfile
from pathlib import Path


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as tmp:
        json.dump(payload, tmp, sort_keys=True)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def rotate_if_oversize(path: Path, max_bytes: int) -> None:
    if not path.exists() or path.stat().st_size <= max_bytes:
        return
    backup = path.with_suffix(path.suffix + ".1")
    if backup.exists():
        backup.unlink()
    path.replace(backup)


def append_event(path: Path, event: dict, max_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rotate_if_oversize(path, max_bytes)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True))
        f.write("\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--state-dir", required=True)
    p.add_argument("--role", required=True, choices=["worker", "mayor"])
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--current-ticket", default="")
    p.add_argument("--last-ticket", default="")
    p.add_argument("--last-error", default="")
    p.add_argument("--event", default="")
    p.add_argument("--details", default="")
    p.add_argument("--events-file", default="events.ndjson")
    p.add_argument("--max-event-bytes", type=int, default=1_000_000)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    state_dir = Path(a.state_dir)
    state_file = state_dir / ("mayor.json" if a.role == "mayor" else f"worker-{a.id}.json")

    payload = {
        "role": a.role,
        "id": a.id,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "status": a.status,
        "current_ticket": a.current_ticket,
        "last_ticket": a.last_ticket,
        "last_error": a.last_error,
        "updated_at_utc": now_utc(),
    }
    atomic_write_json(state_file, payload)

    if a.event:
        evt = {
            "ts": now_utc(),
            "actor": f"{a.role}:{a.id}",
            "event": a.event,
            "ticket": a.current_ticket or a.last_ticket,
            "details": {"message": a.details} if a.details else {},
        }
        append_event(state_dir / a.events_file, evt, max_bytes=a.max_event_bytes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
