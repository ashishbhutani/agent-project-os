#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage:
  $0 --workers 4 --worker-cmd-template '<worker command with {id}>' --mayor-cmd '<mayor command>'
USAGE
}

WORKERS=""
WORKER_CMD_TEMPLATE=""
MAYOR_CMD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workers) WORKERS="$2"; shift 2 ;;
    --worker-cmd-template) WORKER_CMD_TEMPLATE="$2"; shift 2 ;;
    --mayor-cmd) MAYOR_CMD="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$WORKERS" || -z "$WORKER_CMD_TEMPLATE" || -z "$MAYOR_CMD" ]]; then
  usage
  exit 2
fi

pids=()

for i in $(seq 1 "$WORKERS"); do
  cmd="${WORKER_CMD_TEMPLATE//\{id\}/$i}"
  echo "[team] starting worker $i: $cmd"
  bash -lc "$cmd" &
  pids+=("$!")
done

echo "[team] starting mayor: $MAYOR_CMD"
bash -lc "$MAYOR_CMD" &
pids+=("$!")

cleanup() {
  echo "[team] stopping all processes"
  for p in "${pids[@]}"; do
    kill "$p" >/dev/null 2>&1 || true
  done
}

trap cleanup INT TERM EXIT
wait
