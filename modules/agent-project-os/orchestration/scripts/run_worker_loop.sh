#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APOS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLANNING_SCRIPTS="$APOS_ROOT/planning/scripts"
RUNTIME_STATE_WRITER="$APOS_ROOT/orchestration/scripts/write_runtime_state.py"

usage() {
  cat <<USAGE
Usage:
  $0 \
    --agent-id <agent-id> \
    --tracker <tracker.csv> \
    --deps <dependencies.csv> \
    --contracts <contracts.md> \
    --handoff <agent_handoff.md> \
    --claim-lock <lock-file> \
    --agent-cmd-template '<command with {ticket} {tracker} {deps} {contracts} {handoff}>' \
    [--state-dir planning/state] [--poll-seconds 15] [--once]
USAGE
}

AGENT_ID=""
TRACKER=""
DEPS=""
CONTRACTS=""
HANDOFF=""
CLAIM_LOCK="planning/.claim.lock"
STATE_DIR="planning/state"
POLL_SECONDS="15"
ONCE="false"
AGENT_CMD_TEMPLATE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent-id) AGENT_ID="$2"; shift 2 ;;
    --tracker) TRACKER="$2"; shift 2 ;;
    --deps) DEPS="$2"; shift 2 ;;
    --contracts) CONTRACTS="$2"; shift 2 ;;
    --handoff) HANDOFF="$2"; shift 2 ;;
    --claim-lock) CLAIM_LOCK="$2"; shift 2 ;;
    --state-dir) STATE_DIR="$2"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
    --agent-cmd-template) AGENT_CMD_TEMPLATE="$2"; shift 2 ;;
    --once) ONCE="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$AGENT_ID" || -z "$TRACKER" || -z "$DEPS" || -z "$CONTRACTS" || -z "$HANDOFF" || -z "$AGENT_CMD_TEMPLATE" ]]; then
  usage
  exit 2
fi

state_update() {
  python3 "$RUNTIME_STATE_WRITER" \
    --state-dir "$STATE_DIR" \
    --role worker \
    --id "$AGENT_ID" \
    --status "$1" \
    --current-ticket "${2:-}" \
    --last-ticket "${3:-}" \
    --last-error "${4:-}" \
    --event "${5:-}" \
    --details "${6:-}" >/dev/null
}

claim_next() {
  local out
  if ! out=$("$PLANNING_SCRIPTS/claim_next_ticket.sh" "$AGENT_ID" "$TRACKER" "$DEPS" "$CLAIM_LOCK" 2>&1); then
    echo "$out"
    return 1
  fi
  echo "$out"
}

mark_blocked() {
  local ticket="$1"
  local note="$2"
  python3 "$PLANNING_SCRIPTS/update_tracker_status.py" \
    --tracker "$TRACKER" \
    --lock-file "$CLAIM_LOCK" \
    --ticket "$ticket" \
    --status blocked \
    --assignee "$AGENT_ID" \
    --tests fail \
    --notes "$note" >/dev/null
}

run_ticket() {
  local ticket="$1"
  local cmd="$AGENT_CMD_TEMPLATE"

  cmd="${cmd//\{ticket\}/$ticket}"
  cmd="${cmd//\{tracker\}/$TRACKER}"
  cmd="${cmd//\{deps\}/$DEPS}"
  cmd="${cmd//\{contracts\}/$CONTRACTS}"
  cmd="${cmd//\{handoff\}/$HANDOFF}"

  state_update "running_ticket" "$ticket" "$ticket" "" "worker.ticket.started" "Executing ticket command"
  echo "[$AGENT_ID] Running ticket $ticket"
  echo "[$AGENT_ID] Command: $cmd"

  set +e
  eval "$cmd"
  local rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    echo "[$AGENT_ID] Ticket $ticket failed with rc=$rc"
    mark_blocked "$ticket" "Agent command failed with exit code $rc"
    state_update "blocked" "$ticket" "$ticket" "Agent command failed with exit code $rc" "worker.ticket.failed" "Command exited non-zero"
    return $rc
  fi

  echo "[$AGENT_ID] Ticket $ticket completed command execution"
  state_update "idle" "" "$ticket" "" "worker.ticket.completed" "Ticket command finished"
  return 0
}

state_update "idle" "" "" "" "worker.loop.started" "Worker loop started"

while true; do
  state_update "claiming" "" "" "" "worker.claim.attempt" "Attempting to claim ticket"
  ticket="$(claim_next || true)"

  if [[ "$ticket" == "NO_READY_TICKETS" || -z "$ticket" ]]; then
    echo "[$AGENT_ID] No ready tickets."
    state_update "sleeping" "" "" "" "worker.sleeping" "No ready tickets"
    if [[ "$ONCE" == "true" ]]; then
      exit 0
    fi
    sleep "$POLL_SECONDS"
    continue
  fi

  run_ticket "$ticket" || true

  if [[ "$ONCE" == "true" ]]; then
    exit 0
  fi

done
