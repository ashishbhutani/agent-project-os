from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modules/agent-project-os/orchestration/scripts/write_runtime_state.py"


def test_write_runtime_state_and_event(tmp_path):
    state_dir = tmp_path / "state"

    cmd = [
        sys.executable,
        str(SCRIPT),
        "--state-dir",
        str(state_dir),
        "--role",
        "worker",
        "--id",
        "agent-1",
        "--status",
        "running_ticket",
        "--current-ticket",
        "P2-01",
        "--event",
        "worker.ticket.started",
        "--details",
        "started",
    ]
    subprocess.run(cmd, check=True)

    worker_path = state_dir / "worker-agent-1.json"
    event_path = state_dir / "events.ndjson"

    assert worker_path.exists()
    assert event_path.exists()

    state = json.loads(worker_path.read_text(encoding="utf-8"))
    assert state["role"] == "worker"
    assert state["id"] == "agent-1"
    assert state["status"] == "running_ticket"
    assert state["current_ticket"] == "P2-01"

    line = event_path.read_text(encoding="utf-8").strip().splitlines()[0]
    event = json.loads(line)
    assert event["actor"] == "worker:agent-1"
    assert event["event"] == "worker.ticket.started"
    assert event["ticket"] == "P2-01"
