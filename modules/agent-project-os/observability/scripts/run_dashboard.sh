#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage:
  $0 \
    --tracker planning/jira_phase2_tracker.csv \
    --deps planning/jira_phase2_dependencies.csv \
    --state-dir planning/state \
    [--host 127.0.0.1] [--port 7070] [--poll-seconds 2] [--stale-after-seconds 45]
USAGE
}

TRACKER=""
DEPS=""
STATE_DIR=""
HOST="127.0.0.1"
PORT="7070"
POLL_SECONDS="2"
STALE_AFTER_SECONDS="45"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tracker) TRACKER="$2"; shift 2 ;;
    --deps) DEPS="$2"; shift 2 ;;
    --state-dir) STATE_DIR="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
    --stale-after-seconds) STALE_AFTER_SECONDS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$TRACKER" || -z "$DEPS" || -z "$STATE_DIR" ]]; then
  usage
  exit 2
fi

python3 modules/agent-project-os/observability/scripts/dashboard_server.py \
  --tracker "$TRACKER" \
  --deps "$DEPS" \
  --state-dir "$STATE_DIR" \
  --host "$HOST" \
  --port "$PORT" \
  --poll-seconds "$POLL_SECONDS" \
  --stale-after-seconds "$STALE_AFTER_SECONDS"
