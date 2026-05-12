#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/osori/workbench/stock-tracker"
LOG_DIR="$PROJECT_DIR/logs"
ENV_FILE="$PROJECT_DIR/.env"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

MODE="${1:-}"
if [ -z "$MODE" ]; then
  echo "usage: $0 <morning|open|noon|close>" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Missing .env file at $ENV_FILE" >> "$LOG_DIR/cron.log"
  exit 1
fi

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] project python not found at $PYTHON_BIN" >> "$LOG_DIR/cron.log"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a
unset VIRTUAL_ENV
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting $MODE briefing"
  "$PYTHON_BIN" -m stock_tracker.cli "$MODE"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finished $MODE briefing"
} >> "$LOG_DIR/cron.log" 2>&1
