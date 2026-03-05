#!/usr/bin/env bash
set -euo pipefail

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
    [--poll-seconds 15] [--once]

Example:
  $0 --agent-id agent-1 \
     --tracker planning/jira_phase2_tracker.csv \
     --deps planning/jira_phase2_dependencies.csv \
     --contracts docs/architecture/contracts.md \
     --handoff planning/agent_handoff.md \
     --claim-lock planning/.claim.lock \
     --agent-cmd-template 'my-agent-cli run --ticket {ticket} --tracker {tracker} --deps {deps} --contracts {contracts} --handoff {handoff}'
USAGE
}

AGENT_ID=""
TRACKER=""
DEPS=""
CONTRACTS=""
HANDOFF=""
CLAIM_LOCK="planning/.claim.lock"
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

claim_next() {
  local out
  if ! out=$(./modules/agent-project-os/planning/scripts/claim_next_ticket.sh "$AGENT_ID" "$TRACKER" "$DEPS" "$CLAIM_LOCK" 2>&1); then
    echo "$out"
    return 1
  fi
  echo "$out"
}

mark_blocked() {
  local ticket="$1"
  local note="$2"
  python3 modules/agent-project-os/planning/scripts/update_tracker_status.py \
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

  echo "[$AGENT_ID] Running ticket $ticket"
  echo "[$AGENT_ID] Command: $cmd"

  set +e
  eval "$cmd"
  local rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    echo "[$AGENT_ID] Ticket $ticket failed with rc=$rc"
    mark_blocked "$ticket" "Agent command failed with exit code $rc"
    return $rc
  fi

  echo "[$AGENT_ID] Ticket $ticket completed command execution"
  return 0
}

while true; do
  ticket="$(claim_next || true)"

  if [[ "$ticket" == "NO_READY_TICKETS" || -z "$ticket" ]]; then
    echo "[$AGENT_ID] No ready tickets."
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
