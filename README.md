# agent-project-os

A reusable **planning + orchestration system** for multi-agent software delivery.

`agent-project-os` helps teams run multiple coding agents in parallel with deterministic ticket claiming, dependency-aware execution, and a top-level mayor process that enforces merge/test gates.

## What Problem It Solves
Running many agents in parallel usually breaks down due to:
- duplicate ticket pickup,
- dependency violations,
- inconsistent status updates,
- unsafe merges into shared branches.

This project provides a practical operating model to avoid that.

## Core Model
There are two explicit phases:

1. **Planning phase**
- Define tickets, dependencies, and tracker files (`jira_phaseX*.csv`).
- Validate that only dependency-safe tickets are eligible.

2. **Execution phase**
- Worker agents claim and implement ready tickets in parallel.
- A mayor agent monitors `in_review` tickets, merges into integration branch, runs full tests, and marks `done`.

## Repository Layout
- `modules/agent-project-os/planning`
  - templates, prompts, and tracker/dependency scripts.
- `modules/agent-project-os/orchestration`
  - worker loop, mayor loop, team launcher, merge/test policies.
- `modules/agent-project-os/common`
  - shared config schema.
- `docs/`
  - architecture and operational runbook.
- `examples/`
  - example phase config.

## Key Scripts
### Planning
- `planning/scripts/validate_dependencies.py`
  - list-ready, can-start, claim-next
- `planning/scripts/claim_next_ticket.sh`
  - shell wrapper for deterministic claim
- `planning/scripts/update_tracker_status.py`
  - race-safe tracker updates
- `planning/scripts/bootstrap_phase.py`
  - generate phase planning files from templates

### Orchestration
- `orchestration/scripts/run_worker_loop.sh`
  - one worker process loop
- `orchestration/scripts/run_mayor_loop.sh`
  - top-level merge/test/status gate loop
- `orchestration/scripts/run_team.sh`
  - launch multiple workers + mayor together

## Determinism and Safety
The system enforces deterministic behavior via:
- lock-protected claim/update (`flock`),
- deterministic claim order (smallest ready ticket key),
- atomic tracker writes (`tmp + replace`),
- mayor-only merge policy (recommended).

## Quick Start
### 1) Validate ready tickets
```bash
python3 modules/agent-project-os/planning/scripts/validate_dependencies.py \
  --tracker planning/jira_phase2_tracker.csv \
  --dependencies planning/jira_phase2_dependencies.csv \
  --list-ready
```

### 2) Run one worker
```bash
modules/agent-project-os/orchestration/scripts/run_worker_loop.sh \
  --agent-id agent-1 \
  --tracker planning/jira_phase2_tracker.csv \
  --deps planning/jira_phase2_dependencies.csv \
  --contracts docs/architecture/contracts.md \
  --handoff planning/agent_handoff.md \
  --claim-lock planning/.claim.lock \
  --agent-cmd-template 'your-agent-cli run --ticket {ticket} --tracker {tracker} --deps {deps} --contracts {contracts} --handoff {handoff}'
```

### 3) Run mayor
```bash
modules/agent-project-os/orchestration/scripts/run_mayor_loop.sh \
  --phase P2 \
  --tracker planning/jira_phase2_tracker.csv \
  --deps planning/jira_phase2_dependencies.csv \
  --integration-branch phase/P2-integration \
  --base-branch main \
  --full-test-cmd 'pytest -q'
```

## Typical Usage Across Repositories
You can run `agent-project-os` against another repo’s planning artifacts (for example `vector-search-platform`) by pointing tracker/dependency/contracts paths to that target repo.

This allows dogfooding orchestration without coupling the target repo as a package dependency.

## Important Note
Current file locking is reliable when agents share the same filesystem.
For distributed/multi-machine execution, use a centralized lock/lease backend (Redis/DB/Jira API lock layer).

## Docs
- Architecture: `docs/architecture.md`
- Operations: `docs/ops/runbook.md`
- Example config: `examples/phase-config.yaml`
