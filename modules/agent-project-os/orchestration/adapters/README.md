# Agent Adapters

Define provider-specific launch/invoke behavior.

Expected contract (conceptual):
- start_worker(agent_id, ticket_context)
- run_ticket(agent_id, ticket_key, prompt_payload)
- health(agent_id)
- stop_worker(agent_id)

Current runtime uses command templates in shell scripts; adapters can replace this with richer provider SDK usage.
