#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APOS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
UPDATE_TRACKER="$APOS_ROOT/planning/scripts/update_tracker_status.py"

usage() {
  cat <<USAGE
Usage:
  $0 \
    --ticket <P2-00> \
    --tracker <tracker.csv> \
    --deps <dependencies.csv> \
    --contracts <contracts.md> \
    --handoff <handoff.md> \
    --repo-root <target-repo-root> \
    --agent-id <agent-1> \
    [--phase-csv planning/jira_phase2.csv] \
    [--base-branch main] \
    [--lock-file planning/.claim.lock] \
    [--worktrees-dir .worktrees] \
    [--extra-instructions '<text>']
USAGE
}

TICKET=""
TRACKER=""
DEPS=""
CONTRACTS=""
HANDOFF=""
REPO_ROOT=""
AGENT_ID=""
PHASE_CSV="planning/jira_phase2.csv"
BASE_BRANCH="main"
LOCK_FILE=""
WORKTREES_DIR=".worktrees"
EXTRA_INSTRUCTIONS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ticket) TICKET="$2"; shift 2 ;;
    --tracker) TRACKER="$2"; shift 2 ;;
    --deps) DEPS="$2"; shift 2 ;;
    --contracts) CONTRACTS="$2"; shift 2 ;;
    --handoff) HANDOFF="$2"; shift 2 ;;
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    --agent-id) AGENT_ID="$2"; shift 2 ;;
    --phase-csv) PHASE_CSV="$2"; shift 2 ;;
    --base-branch) BASE_BRANCH="$2"; shift 2 ;;
    --lock-file) LOCK_FILE="$2"; shift 2 ;;
    --worktrees-dir) WORKTREES_DIR="$2"; shift 2 ;;
    --extra-instructions) EXTRA_INSTRUCTIONS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$TICKET" || -z "$TRACKER" || -z "$DEPS" || -z "$CONTRACTS" || -z "$HANDOFF" || -z "$REPO_ROOT" || -z "$AGENT_ID" ]]; then
  usage
  exit 2
fi

BRANCH="ticket/$TICKET"
WT_DIR="$REPO_ROOT/$WORKTREES_DIR/wt-$(echo "$TICKET" | tr '[:upper:]' '[:lower:]')"
LOCK_PATH="${LOCK_FILE:-$REPO_ROOT/planning/.claim.lock}"
LAST_MSG="/tmp/codex-last-$TICKET.txt"

mark_blocked() {
  local note="$1"
  python3 "$UPDATE_TRACKER" \
    --tracker "$TRACKER" \
    --lock-file "$LOCK_PATH" \
    --ticket "$TICKET" \
    --status blocked \
    --assignee "$AGENT_ID" \
    --tests fail \
    --notes "$note" >/dev/null || true
}

mkdir -p "$REPO_ROOT/$WORKTREES_DIR"
git -C "$REPO_ROOT" fetch origin "$BASE_BRANCH" >/dev/null 2>&1 || true

if [[ -d "$WT_DIR" ]]; then
  if [[ -n "$(git -C "$WT_DIR" status --porcelain 2>/dev/null || true)" ]]; then
    mark_blocked "Dirty worktree exists for $TICKET: $WT_DIR"
    exit 3
  fi
else
  git -C "$REPO_ROOT" worktree add -B "$BRANCH" "$WT_DIR" "origin/$BASE_BRANCH" >/dev/null
fi

PROMPT="Implement ${TICKET} from ${PHASE_CSV}. Do not ask questions; make reasonable assumptions.
Follow contracts at ${CONTRACTS}. Use dependencies at ${DEPS}. Use handoff at ${HANDOFF}.
Stay within ticket scope. Add or update tests and run python3 -m pytest -q.
Commit your changes on ${BRANCH}. Exit non-zero on failure."

if [[ -n "$EXTRA_INSTRUCTIONS" ]]; then
  PROMPT="${PROMPT}
${EXTRA_INSTRUCTIONS}"
fi

if ! codex exec --full-auto --sandbox workspace-write -C "$WT_DIR" --output-last-message "$LAST_MSG" "$PROMPT"; then
  mark_blocked "Codex execution failed for $TICKET"
  exit 4
fi

if grep -Eiq "how do you want to proceed|options:|i need your input|please choose" "$LAST_MSG"; then
  mark_blocked "Codex requested interactive input in non-interactive mode for $TICKET"
  exit 5
fi

if ! git -C "$WT_DIR" rev-parse --verify HEAD >/dev/null 2>&1; then
  mark_blocked "No commit produced for $TICKET"
  exit 6
fi

if ! git -C "$WT_DIR" push -u origin "$BRANCH" >/dev/null 2>&1; then
  mark_blocked "Push failed for $BRANCH"
  exit 7
fi

python3 "$UPDATE_TRACKER" \
  --tracker "$TRACKER" \
  --lock-file "$LOCK_PATH" \
  --ticket "$TICKET" \
  --status in_review \
  --assignee "$AGENT_ID" \
  --branch "$BRANCH" \
  --worktree "$WT_DIR" \
  --tests pass \
  --notes "Codex adapter completed and pushed $BRANCH." >/dev/null
