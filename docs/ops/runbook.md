# Operational Runbook

## Start one worker
```bash
modules/agent-project-os/orchestration/scripts/run_worker_loop.sh \
  --agent-id agent-1 \
  --tracker planning/jira_phase2_tracker.csv \
  --deps planning/jira_phase2_dependencies.csv \
  --contracts docs/architecture/contracts.md \
  --handoff planning/agent_handoff.md \
  --claim-lock planning/.claim.lock \
  --state-dir planning/state \
  --agent-cmd-template 'your-agent-cli run --ticket {ticket} --tracker {tracker} --deps {deps} --contracts {contracts} --handoff {handoff}'
```

## Start one worker (Codex adapter, recommended)
```bash
modules/agent-project-os/orchestration/scripts/run_worker_loop.sh \
  --agent-id agent-1 \
  --tracker planning/jira_phase2_tracker.csv \
  --deps planning/jira_phase2_dependencies.csv \
  --contracts docs/architecture/contracts.md \
  --handoff planning/agent_handoff.md \
  --claim-lock planning/.claim.lock \
  --state-dir planning/state \
  --agent-cmd-template '/Users/ashish.bhutani/code/2026/agent-project-os/modules/agent-project-os/orchestration/adapters/codex_exec_worker.sh --ticket {ticket} --tracker {tracker} --deps {deps} --contracts {contracts} --handoff {handoff} --repo-root /Users/ashish.bhutani/code/2026/hnsw-phase2-run --agent-id agent-1 --phase-csv planning/jira_phase2.csv'
```

## Start mayor loop
```bash
modules/agent-project-os/orchestration/scripts/run_mayor_loop.sh \
  --phase P2 \
  --tracker planning/jira_phase2_tracker.csv \
  --deps planning/jira_phase2_dependencies.csv \
  --integration-branch phase/P2-integration \
  --base-branch main \
  --state-dir planning/state \
  --full-test-cmd 'pytest -q'
```

## Start local dashboard
```bash
modules/agent-project-os/observability/scripts/run_dashboard.sh \
  --tracker planning/jira_phase2_tracker.csv \
  --deps planning/jira_phase2_dependencies.csv \
  --state-dir planning/state \
  --port 7070
```

Then open `http://127.0.0.1:7070`.

## Start full team
```bash
modules/agent-project-os/orchestration/scripts/run_team.sh \
  --workers 4 \
  --worker-cmd-template 'modules/agent-project-os/orchestration/scripts/run_worker_loop.sh --agent-id agent-{id} --tracker planning/jira_phase2_tracker.csv --deps planning/jira_phase2_dependencies.csv --contracts docs/architecture/contracts.md --handoff planning/agent_handoff.md --claim-lock planning/.claim.lock --state-dir planning/state --agent-cmd-template "your-agent-cli run --ticket {ticket} --tracker {tracker} --deps {deps} --contracts {contracts} --handoff {handoff}"' \
  --mayor-cmd 'modules/agent-project-os/orchestration/scripts/run_mayor_loop.sh --phase P2 --tracker planning/jira_phase2_tracker.csv --deps planning/jira_phase2_dependencies.csv --integration-branch phase/P2-integration --base-branch main --state-dir planning/state --full-test-cmd "pytest -q"'
```
