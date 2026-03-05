# Agent Adapters

Define provider-specific launch/invoke behavior.

Expected contract (conceptual):
- start_worker(agent_id, ticket_context)
- run_ticket(agent_id, ticket_key, prompt_payload)
- health(agent_id)
- stop_worker(agent_id)

Current runtime uses command templates in shell scripts; adapters can replace this with richer provider SDK usage.

## Included adapter
- `codex_exec_worker.sh`: runs one ticket through `codex exec` in a dedicated worktree, pushes `ticket/<KEY>`, and updates tracker to `in_review` (or `blocked` on failure).
