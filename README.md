# agent-project-os

Agent Project OS provides reusable planning and orchestration primitives for multi-agent engineering delivery.

## Modules
- `modules/agent-project-os/planning`: templates, prompts, and dependency-aware tracker tooling.
- `modules/agent-project-os/orchestration`: worker loops, mayor loop, and merge/test gate policies.
- `modules/agent-project-os/common`: shared schemas.

## Workflow
1. Generate/approve planning artifacts (tasks, dependencies, tracker).
2. Start workers to implement ready tickets.
3. Start mayor to merge reviewed tickets on integration branch with full test gates.
4. Open final PR from integration branch to main.

## Quick commands
```bash
python3 modules/agent-project-os/planning/scripts/validate_dependencies.py --tracker planning/jira_phase2_tracker.csv --dependencies planning/jira_phase2_dependencies.csv --list-ready
```

```bash
modules/agent-project-os/orchestration/scripts/run_mayor_loop.sh --help
```
