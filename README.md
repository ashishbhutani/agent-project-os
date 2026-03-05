# agent-project-os

A reusable **planning + orchestration + observability system** for multi-agent software delivery.

`agent-project-os` helps teams run multiple coding agents in parallel with deterministic ticket claiming, dependency-aware execution, a mayor merge gate, and a local dashboard for real-time worker state.

## What It Solves
Parallel agent execution usually breaks due to duplicate claims, broken dependency order, unclear ownership, and unsafe merges. This project provides an operating model with strict state tracking and merge/test guardrails.

## Core Model
1. **Planning phase**
- Define tasks, dependencies, and tracker files (`jira_phaseX*.csv`).
- Validate and claim only dependency-safe tickets.

2. **Execution phase**
- Worker loops claim ready tickets and execute in parallel.
- Mayor loop merges `in_review` tickets into integration branch and runs full-suite gates.

3. **Observability phase**
- Workers and mayor emit heartbeat/state files.
- Local dashboard shows live/stale workers, mayor activity, ticket board, and pending-by-blocker state.

## Repository Layout
- `modules/agent-project-os/planning`: templates, prompts, tracker/dependency scripts.
- `modules/agent-project-os/orchestration`: worker/mayor/team loops and policies.
- `modules/agent-project-os/observability`: dashboard server and run script.
- `modules/agent-project-os/common`: shared schemas.
- `docs/`: architecture and runbook.
- `examples/`: example phase config.

## Quick Start
Install dependencies:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

Validate ready tickets:
```bash
python3 modules/agent-project-os/planning/scripts/validate_dependencies.py \
  --tracker planning/jira_phase2_tracker.csv \
  --dependencies planning/jira_phase2_dependencies.csv \
  --list-ready
```

Run workers/mayor with shared state directory:
```bash
modules/agent-project-os/orchestration/scripts/run_worker_loop.sh ... --state-dir planning/state
modules/agent-project-os/orchestration/scripts/run_mayor_loop.sh ... --state-dir planning/state
```

Run dashboard:
```bash
modules/agent-project-os/observability/scripts/run_dashboard.sh \
  --tracker planning/jira_phase2_tracker.csv \
  --deps planning/jira_phase2_dependencies.csv \
  --state-dir planning/state \
  --port 7070
```
Open `http://127.0.0.1:7070`.

## Determinism and Safety
- Lock-protected claim/update (`flock`)
- Deterministic claim order (smallest ready key)
- Atomic tracker/state writes (`tmp + replace`)
- Mayor-only merge policy
- Stale worker detection via heartbeat age

## Docs
- [Architecture](docs/architecture.md)
- [Operational Runbook](docs/ops/runbook.md)
- [Example config](examples/phase-config.yaml)
