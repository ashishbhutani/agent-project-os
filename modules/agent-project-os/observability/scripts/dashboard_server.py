#!/usr/bin/env python3
"""Local observability dashboard for Agent Project OS."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
import uvicorn


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_ts(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def load_dependencies(path: Path) -> Dict[str, List[str]]:
    rows = load_csv_rows(path)
    dep_map: Dict[str, List[str]] = {}
    for row in rows:
        src = (row.get("From") or "").strip()
        dst = (row.get("To") or "").strip()
        dep_type = (row.get("DependencyType") or "").strip().lower()
        if not src or not dst:
            continue
        if dep_type and dep_type != "blocks":
            continue
        dep_map.setdefault(dst, []).append(src)
    return dep_map


def tracker_status_map(rows: List[Dict[str, str]]) -> Dict[str, str]:
    return {
        (r.get("Key") or "").strip(): (r.get("Status") or "").strip().lower()
        for r in rows
        if (r.get("Key") or "").strip()
    }


def unresolved_blockers(row: Dict[str, str], dep_map: Dict[str, List[str]], status: Dict[str, str]) -> List[str]:
    key = (row.get("Key") or "").strip()
    blockers = dep_map.get(key)
    if blockers is None:
        blockers = [b.strip() for b in (row.get("BlockedBy") or "").split("|") if b.strip()]
    return sorted([b for b in blockers if status.get(b) != "done"])


def classify_tickets(tracker_rows: List[Dict[str, str]], dep_map: Dict[str, List[str]]) -> Dict[str, object]:
    status = tracker_status_map(tracker_rows)

    tickets = []
    counts: Dict[str, int] = {
        "todo": 0,
        "ready": 0,
        "in_progress": 0,
        "in_review": 0,
        "done": 0,
        "blocked": 0,
        "unknown": 0,
        "pending": 0,
    }

    for row in tracker_rows:
        key = (row.get("Key") or "").strip()
        st = (row.get("Status") or "").strip().lower() or "unknown"
        blockers = unresolved_blockers(row, dep_map, status)
        is_pending = st in {"todo", "ready"} and len(blockers) > 0

        if st in counts:
            counts[st] += 1
        else:
            counts["unknown"] += 1

        if is_pending:
            counts["pending"] += 1

        tickets.append(
            {
                "key": key,
                "status": st,
                "assignee": (row.get("Assignee") or "").strip(),
                "branch": (row.get("Branch") or "").strip(),
                "prurl": (row.get("PRURL") or "").strip(),
                "tests": (row.get("Tests") or "").strip(),
                "updated_at_utc": (row.get("LastUpdatedUTC") or "").strip(),
                "blocked_by": blockers,
                "is_pending": is_pending,
                "notes": (row.get("Notes") or "").strip(),
            }
        )

    tickets.sort(key=lambda t: t["key"])
    return {"counts": counts, "tickets": tickets}


def load_state_file(path: Path) -> Dict[str, object] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def mark_staleness(state: Dict[str, object], stale_after_seconds: int) -> Dict[str, object]:
    ts = parse_ts(str(state.get("updated_at_utc") or ""))
    age = None
    stale = True
    if ts is not None:
        age = int((now_utc() - ts).total_seconds())
        stale = age > stale_after_seconds
    out = dict(state)
    out["age_seconds"] = age
    out["is_stale"] = stale
    return out


def load_workers(state_dir: Path, stale_after_seconds: int) -> List[Dict[str, object]]:
    workers = []
    for path in sorted(state_dir.glob("worker-*.json")):
        data = load_state_file(path)
        if data is None:
            continue
        workers.append(mark_staleness(data, stale_after_seconds))
    return workers


def load_mayor(state_dir: Path, stale_after_seconds: int) -> Dict[str, object] | None:
    data = load_state_file(state_dir / "mayor.json")
    if data is None:
        return None
    return mark_staleness(data, stale_after_seconds)


def make_app(tracker: Path, deps: Path, state_dir: Path, stale_after_seconds: int, poll_seconds: int) -> FastAPI:
    app = FastAPI(title="Agent Project OS Dashboard")

    def snapshot() -> Dict[str, object]:
        tracker_rows = load_csv_rows(tracker)
        dep_map = load_dependencies(deps)
        ticket_data = classify_tickets(tracker_rows, dep_map)
        workers = load_workers(state_dir, stale_after_seconds)
        mayor = load_mayor(state_dir, stale_after_seconds)
        return {
            "generated_at_utc": now_utc().replace(microsecond=0).isoformat(),
            "workers": workers,
            "mayor": mayor,
            "tickets": ticket_data["tickets"],
            "counts": ticket_data["counts"],
            "paths": {
                "tracker": str(tracker),
                "dependencies": str(deps),
                "state_dir": str(state_dir),
            },
            "poll_seconds": poll_seconds,
        }

    @app.get("/healthz")
    def healthz() -> PlainTextResponse:
        return PlainTextResponse("ok")

    @app.get("/api/overview")
    def api_overview() -> JSONResponse:
        data = snapshot()
        return JSONResponse(
            {
                "generated_at_utc": data["generated_at_utc"],
                "counts": data["counts"],
                "workers_total": len(data["workers"]),
                "workers_stale": sum(1 for w in data["workers"] if w.get("is_stale")),
                "mayor": data["mayor"],
                "paths": data["paths"],
            }
        )

    @app.get("/api/workers")
    def api_workers() -> JSONResponse:
        data = snapshot()
        return JSONResponse({"generated_at_utc": data["generated_at_utc"], "workers": data["workers"], "mayor": data["mayor"]})

    @app.get("/api/mayor")
    def api_mayor() -> JSONResponse:
        data = snapshot()
        return JSONResponse({"generated_at_utc": data["generated_at_utc"], "mayor": data["mayor"]})

    @app.get("/api/tickets")
    def api_tickets() -> JSONResponse:
        data = snapshot()
        return JSONResponse({"generated_at_utc": data["generated_at_utc"], "counts": data["counts"], "tickets": data["tickets"]})

    @app.get("/", response_class=HTMLResponse)
    @app.get("/workers", response_class=HTMLResponse)
    @app.get("/tickets", response_class=HTMLResponse)
    def ui() -> HTMLResponse:
        html = f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Agent Project OS Dashboard</title>
  <style>
    :root {{
      --bg: #f4f7fb;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --ok: #0f766e;
      --warn: #b45309;
      --bad: #b91c1c;
      --line: #dbe3ef;
      --accent: #0b5fff;
    }}
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; background: linear-gradient(140deg, #f8fbff 0%, #eef4ff 100%); color: var(--text); }}
    .shell {{ max-width: 1180px; margin: 0 auto; padding: 20px; }}
    .top {{ display: flex; justify-content: space-between; align-items: end; gap: 12px; flex-wrap: wrap; }}
    h1 {{ margin: 0; font-size: 1.5rem; }}
    .meta {{ color: var(--muted); font-size: 0.9rem; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 14px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }}
    .label {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: .04em; }}
    .value {{ font-size: 1.3rem; font-weight: 700; margin-top: 4px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px; margin-top: 14px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px; text-align: left; font-size: 0.92rem; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .dot {{ display:inline-block; width:8px; height:8px; border-radius:999px; margin-right:6px; }}
    .ok {{ color: var(--ok); }}
    .warn {{ color: var(--warn); }}
    .bad {{ color: var(--bad); }}
    code {{ background: #f3f4f6; border-radius: 6px; padding: 1px 5px; }}
  </style>
</head>
<body>
  <div class=\"shell\">
    <div class=\"top\">
      <div>
        <h1>Agent Project OS Dashboard</h1>
        <div class=\"meta\" id=\"stamp\">loading...</div>
      </div>
      <div class=\"meta\">Poll interval: {poll_seconds}s</div>
    </div>

    <div class=\"cards\" id=\"counts\"></div>

    <div class=\"panel\">
      <h3>Mayor</h3>
      <div id=\"mayor\" class=\"meta\">No mayor state yet.</div>
    </div>

    <div class=\"panel\">
      <h3>Workers</h3>
      <table>
        <thead><tr><th>ID</th><th>Status</th><th>Current</th><th>Last</th><th>Age(s)</th><th>Error</th><th>Updated</th></tr></thead>
        <tbody id=\"workers\"></tbody>
      </table>
    </div>

    <div class=\"panel\">
      <h3>Tickets</h3>
      <table>
        <thead><tr><th>Key</th><th>Status</th><th>Assignee</th><th>Pending</th><th>Blocked By</th><th>Tests</th><th>Updated</th></tr></thead>
        <tbody id=\"tickets\"></tbody>
      </table>
    </div>
  </div>

  <script>
    function h(txt) {{ return String(txt ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'); }}
    function badge(isStale) {{ return isStale ? '<span class="dot" style="background:#b91c1c"></span><span class="bad">stale</span>' : '<span class="dot" style="background:#0f766e"></span><span class="ok">live</span>'; }}

    async function refresh() {{
      const [o, w, t] = await Promise.all([
        fetch('/api/overview').then(r => r.json()),
        fetch('/api/workers').then(r => r.json()),
        fetch('/api/tickets').then(r => r.json())
      ]);

      document.getElementById('stamp').innerText = `Updated: ${{o.generated_at_utc}} | tracker: ${{o.paths.tracker}}`;

      const counts = o.counts;
      const keys = ['todo','ready','in_progress','in_review','done','blocked','pending'];
      document.getElementById('counts').innerHTML = keys.map(k => `<div class="card"><div class="label">${{k.replace('_',' ')}}</div><div class="value">${{counts[k] ?? 0}}</div></div>`).join('') +
        `<div class="card"><div class="label">workers</div><div class="value">${{o.workers_total}}</div></div>` +
        `<div class="card"><div class="label">stale workers</div><div class="value">${{o.workers_stale}}</div></div>`;

      const mayor = o.mayor;
      document.getElementById('mayor').innerHTML = mayor
        ? `ID <code>${{h(mayor.id)}}</code> | status <b>${{h(mayor.status)}}</b> | current <code>${{h(mayor.current_ticket || '-')}}</code> | age <b>${{h(mayor.age_seconds)}}</b>s | ${{badge(mayor.is_stale)}}`
        : 'No mayor state yet.';

      document.getElementById('workers').innerHTML = (w.workers || []).map(x =>
        `<tr><td><code>${{h(x.id)}}</code></td><td>${{h(x.status)}} ${{badge(x.is_stale)}}</td><td>${{h(x.current_ticket || '-')}}</td><td>${{h(x.last_ticket || '-')}}</td><td>${{h(x.age_seconds ?? '-') }}</td><td class="bad">${{h(x.last_error || '')}}</td><td>${{h(x.updated_at_utc || '')}}</td></tr>`
      ).join('') || '<tr><td colspan="7" class="meta">No worker state yet.</td></tr>';

      document.getElementById('tickets').innerHTML = (t.tickets || []).map(x =>
        `<tr><td><code>${{h(x.key)}}</code></td><td>${{h(x.status)}}</td><td>${{h(x.assignee || '-')}}</td><td>${{x.is_pending ? '<span class="warn">yes</span>' : 'no'}}</td><td>${{h((x.blocked_by || []).join('|') || '-')}}</td><td>${{h(x.tests || '-')}}</td><td>${{h(x.updated_at_utc || '')}}</td></tr>`
      ).join('') || '<tr><td colspan="7" class="meta">No ticket data.</td></tr>';
    }}

    refresh();
    setInterval(refresh, {poll_seconds * 1000});
  </script>
</body>
</html>
        """
        return HTMLResponse(html)

    return app


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tracker", required=True)
    p.add_argument("--deps", required=True)
    p.add_argument("--state-dir", required=True)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=7070)
    p.add_argument("--poll-seconds", type=int, default=2)
    p.add_argument("--stale-after-seconds", type=int, default=45)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    app = make_app(
        tracker=Path(a.tracker),
        deps=Path(a.deps),
        state_dir=Path(a.state_dir),
        stale_after_seconds=a.stale_after_seconds,
        poll_seconds=a.poll_seconds,
    )
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
