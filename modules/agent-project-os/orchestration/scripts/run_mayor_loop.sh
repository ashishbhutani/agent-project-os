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
    --phase P2 \
    --tracker planning/jira_phase2_tracker.csv \
    --deps planning/jira_phase2_dependencies.csv \
    --integration-branch phase/P2-integration \
    --base-branch main \
    --full-test-cmd '<command>' \
    [--lock-file planning/.claim.lock] [--state-dir planning/state] [--poll-seconds 15] [--once]
USAGE
}

PHASE=""
TRACKER=""
DEPS=""
INTEGRATION_BRANCH=""
BASE_BRANCH="main"
LOCK_FILE="planning/.claim.lock"
STATE_DIR="planning/state"
POLL_SECONDS="15"
ONCE="false"
FULL_TEST_CMD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase) PHASE="$2"; shift 2 ;;
    --tracker) TRACKER="$2"; shift 2 ;;
    --deps) DEPS="$2"; shift 2 ;;
    --integration-branch) INTEGRATION_BRANCH="$2"; shift 2 ;;
    --base-branch) BASE_BRANCH="$2"; shift 2 ;;
    --lock-file) LOCK_FILE="$2"; shift 2 ;;
    --state-dir) STATE_DIR="$2"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
    --full-test-cmd) FULL_TEST_CMD="$2"; shift 2 ;;
    --once) ONCE="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$PHASE" || -z "$TRACKER" || -z "$DEPS" || -z "$INTEGRATION_BRANCH" || -z "$FULL_TEST_CMD" ]]; then
  usage
  exit 2
fi

state_update() {
  python3 "$RUNTIME_STATE_WRITER" \
    --state-dir "$STATE_DIR" \
    --role mayor \
    --id "$PHASE" \
    --status "$1" \
    --current-ticket "${2:-}" \
    --last-ticket "${3:-}" \
    --last-error "${4:-}" \
    --event "${5:-}" \
    --details "${6:-}" >/dev/null
}

ensure_integration_branch() {
  if git show-ref --verify --quiet "refs/heads/$INTEGRATION_BRANCH"; then
    git checkout "$INTEGRATION_BRANCH" >/dev/null
  else
    git checkout "$BASE_BRANCH" >/dev/null
    git pull --ff-only origin "$BASE_BRANCH" >/dev/null
    git checkout -b "$INTEGRATION_BRANCH" >/dev/null
  fi
}

eligible_in_review() {
  python3 - <<PY
import csv
from pathlib import Path

tracker = Path("$TRACKER")
deps = Path("$DEPS")

status = {}
rows = []
with tracker.open("r", encoding="utf-8", newline="") as f:
    r = csv.DictReader(f)
    rows = list(r)
for row in rows:
    status[(row.get("Key") or "").strip()] = (row.get("Status") or "").strip().lower()

depmap = {}
with deps.open("r", encoding="utf-8", newline="") as f:
    r = csv.DictReader(f)
    for row in r:
        src = (row.get("From") or "").strip()
        dst = (row.get("To") or "").strip()
        t = (row.get("DependencyType") or "").strip().lower()
        if src and dst and (not t or t == "blocks"):
            depmap.setdefault(dst, []).append(src)

eligible = []
for row in rows:
    key = (row.get("Key") or "").strip()
    st = (row.get("Status") or "").strip().lower()
    if st != "in_review":
        continue
    blockers = depmap.get(key)
    if blockers is None:
        blockers = [b.strip() for b in (row.get("BlockedBy") or "").split("|") if b.strip()]
    if all(status.get(b) == "done" for b in blockers):
        eligible.append(key)

for k in sorted(eligible):
    print(k)
PY
}

mark_status() {
  local ticket="$1"
  local status="$2"
  local tests="$3"
  local notes="$4"
  local merge_commit="${5:-}"

  local args=(
    --tracker "$TRACKER"
    --lock-file "$LOCK_FILE"
    --ticket "$ticket"
    --status "$status"
    --tests "$tests"
    --notes "$notes"
  )

  if [[ -n "$merge_commit" ]]; then
    args+=(--merge-commit "$merge_commit")
  fi

  python3 "$PLANNING_SCRIPTS/update_tracker_status.py" "${args[@]}" >/dev/null
}

process_ticket() {
  local ticket="$1"
  local branch="ticket/$ticket"

  state_update "processing_ticket" "$ticket" "$ticket" "" "mayor.ticket.processing" "Processing in_review ticket"
  echo "[mayor] processing $ticket from $branch"

  if ! git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    git fetch origin "$branch":"$branch" >/dev/null 2>&1 || true
  fi
  if ! git show-ref --verify --quiet "refs/heads/$branch"; then
    mark_status "$ticket" "blocked" "fail" "Mayor: missing branch $branch"
    state_update "blocked" "$ticket" "$ticket" "Missing branch $branch" "mayor.ticket.blocked" "Missing ticket branch"
    return 1
  fi

  state_update "merging" "$ticket" "$ticket" "" "mayor.merge.started" "Merging ticket branch"
  set +e
  git merge --no-ff "$branch" -m "mayor merge: $ticket into $INTEGRATION_BRANCH" >/tmp/mayor-merge.log 2>&1
  local mrc=$?
  set -e

  if [[ $mrc -ne 0 ]]; then
    git merge --abort >/dev/null 2>&1 || true
    mark_status "$ticket" "blocked" "fail" "Mayor: merge conflict or merge failure"
    state_update "blocked" "$ticket" "$ticket" "Merge conflict/failure" "mayor.merge.failed" "Merge conflict or failure"
    return 1
  fi

  state_update "running_tests" "$ticket" "$ticket" "" "mayor.tests.started" "Running full-suite tests"
  set +e
  eval "$FULL_TEST_CMD" >/tmp/mayor-test.log 2>&1
  local trc=$?
  set -e

  if [[ $trc -ne 0 ]]; then
    mark_status "$ticket" "blocked" "fail" "Mayor: full-suite failed on integration branch"
    state_update "blocked" "$ticket" "$ticket" "Full-suite test failed" "mayor.tests.failed" "Integration test gate failed"
    return 1
  fi

  local sha
  sha=$(git rev-parse --short HEAD)
  mark_status "$ticket" "done" "pass" "Mayor merged and validated on integration branch" "$sha"
  state_update "idle" "" "$ticket" "" "mayor.ticket.done" "Ticket merged and marked done"
  return 0
}

ensure_integration_branch
state_update "idle" "" "" "" "mayor.loop.started" "Mayor loop started"

while true; do
  state_update "scanning" "" "" "" "mayor.scan" "Scanning for eligible in_review tickets"
  tickets=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && tickets+=("$line")
  done < <(eligible_in_review)

  if [[ ${#tickets[@]} -eq 0 ]]; then
    echo "[mayor] no eligible in_review tickets"
    state_update "sleeping" "" "" "" "mayor.sleeping" "No eligible in_review tickets"
    if [[ "$ONCE" == "true" ]]; then
      exit 0
    fi
    sleep "$POLL_SECONDS"
    continue
  fi

  for t in "${tickets[@]}"; do
    process_ticket "$t" || true
  done

  if [[ "$ONCE" == "true" ]]; then
    exit 0
  fi

done
