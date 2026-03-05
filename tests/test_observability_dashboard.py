from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = ROOT / "modules/agent-project-os/observability/scripts/dashboard_server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("dashboard_server", DASHBOARD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_classify_tickets_counts_and_pending():
    mod = load_module()

    tracker_rows = [
        {"Key": "P2-00", "Status": "done", "BlockedBy": "", "Assignee": "", "Branch": "", "PRURL": "", "Tests": "pass", "LastUpdatedUTC": "", "Notes": ""},
        {"Key": "P2-01", "Status": "todo", "BlockedBy": "P2-00", "Assignee": "", "Branch": "", "PRURL": "", "Tests": "pending", "LastUpdatedUTC": "", "Notes": ""},
        {"Key": "P2-02", "Status": "in_progress", "BlockedBy": "", "Assignee": "agent-1", "Branch": "ticket/P2-02", "PRURL": "", "Tests": "pending", "LastUpdatedUTC": "", "Notes": ""},
        {"Key": "P2-03", "Status": "ready", "BlockedBy": "", "Assignee": "", "Branch": "", "PRURL": "", "Tests": "pending", "LastUpdatedUTC": "", "Notes": ""},
    ]
    dep_map = {"P2-01": ["P2-00"]}

    out = mod.classify_tickets(tracker_rows, dep_map)
    counts = out["counts"]

    assert counts["done"] == 1
    assert counts["todo"] == 1
    assert counts["in_progress"] == 1
    assert counts["ready"] == 1
    assert counts["pending"] == 0

    todo = [t for t in out["tickets"] if t["key"] == "P2-01"][0]
    assert todo["is_pending"] is False
    assert todo["blocked_by"] == []


def test_mark_staleness_live_and_stale():
    mod = load_module()
    now = mod.now_utc()

    fresh = {
        "id": "agent-1",
        "updated_at_utc": (now - mod.dt.timedelta(seconds=5)).replace(microsecond=0).isoformat(),
    }
    stale = {
        "id": "agent-2",
        "updated_at_utc": (now - mod.dt.timedelta(seconds=200)).replace(microsecond=0).isoformat(),
    }

    fresh_out = mod.mark_staleness(fresh, stale_after_seconds=45)
    stale_out = mod.mark_staleness(stale, stale_after_seconds=45)

    assert fresh_out["is_stale"] is False
    assert stale_out["is_stale"] is True
    assert isinstance(fresh_out["age_seconds"], int)
