#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <agent_id> <tracker_csv> <dependencies_csv> [lock_file] [--dry-run]"
}

if [[ $# -lt 3 ]]; then
  usage
  exit 2
fi

AGENT_ID="$1"
TRACKER="$2"
DEPS="$3"
LOCK_FILE="${4:-planning/.claim.lock}"
DRY_RUN=""

if [[ $# -ge 5 ]]; then
  if [[ "$5" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
  else
    echo "Unknown argument: $5"
    usage
    exit 2
  fi
fi

if [[ $# -gt 5 ]]; then
  echo "Too many arguments"
  usage
  exit 2
fi

python3 modules/agent-project-os/planning/scripts/validate_dependencies.py \
  --tracker "$TRACKER" \
  --dependencies "$DEPS" \
  --lock-file "$LOCK_FILE" \
  --claim-next \
  --agent "$AGENT_ID" \
  $DRY_RUN
