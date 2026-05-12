#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/osori/workbench/stock-tracker"
LOG_DIR="$PROJECT_DIR/logs"
ENV_FILE="$PROJECT_DIR/.env"
UV_BIN="$(command -v uv)"

MODE="${1:-}"
if [ -z "$MODE" ]; then
  echo "usage: $0 <open|noon|close>" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Missing .env file at $ENV_FILE" >> "$LOG_DIR/cron.log"
  exit 1
fi

if [ -z "$UV_BIN" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] uv binary not found in PATH" >> "$LOG_DIR/cron.log"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a
unset VIRTUAL_ENV

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting $MODE briefing"
  "$UV_BIN" run stock-tracker "$MODE"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finished $MODE briefing"
} >> "$LOG_DIR/cron.log" 2>&1
