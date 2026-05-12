#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/osori/workbench/stock-tracker"
CRON_FILE="$PROJECT_DIR/deploy/stock-tracker.crontab"
TMP_FILE="$(mktemp)"

cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

(crontab -l 2>/dev/null || true) \
  | grep -v 'stock-tracker-morning' \
  | grep -v 'stock-tracker-open' \
  | grep -v 'stock-tracker-noon' \
  | grep -v 'stock-tracker-close' \
  > "$TMP_FILE"

cat "$CRON_FILE" >> "$TMP_FILE"
crontab "$TMP_FILE"
crontab -l
