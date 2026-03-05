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
  --agent-cmd-template 'your-agent-cli run --ticket {ticket} --tracker {tracker} --deps {deps} --contracts {contracts} --handoff {handoff}'
```

## Start mayor loop
```bash
modules/agent-project-os/orchestration/scripts/run_mayor_loop.sh \
  --phase P2 \
  --tracker planning/jira_phase2_tracker.csv \
  --deps planning/jira_phase2_dependencies.csv \
  --integration-branch phase/P2-integration \
  --base-branch main \
  --full-test-cmd 'pytest -q'
```

## Start full team
```bash
modules/agent-project-os/orchestration/scripts/run_team.sh \
  --workers 4 \
  --worker-cmd-template 'modules/agent-project-os/orchestration/scripts/run_worker_loop.sh --agent-id agent-{id} --tracker planning/jira_phase2_tracker.csv --deps planning/jira_phase2_dependencies.csv --contracts docs/architecture/contracts.md --handoff planning/agent_handoff.md --claim-lock planning/.claim.lock --agent-cmd-template "your-agent-cli run --ticket {ticket} --tracker {tracker} --deps {deps} --contracts {contracts} --handoff {handoff}"' \
  --mayor-cmd 'modules/agent-project-os/orchestration/scripts/run_mayor_loop.sh --phase P2 --tracker planning/jira_phase2_tracker.csv --deps planning/jira_phase2_dependencies.csv --integration-branch phase/P2-integration --base-branch main --full-test-cmd "pytest -q"'
```
