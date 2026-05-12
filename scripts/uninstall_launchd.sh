#!/bin/bash
set -euo pipefail

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
UID_VALUE="$(id -u)"
LABEL_PREFIX="com.osori.stock-tracker"

for mode in open noon close; do
  label="$LABEL_PREFIX.$mode"
  launchctl bootout "gui/$UID_VALUE/$label" >/dev/null 2>&1 || true
  rm -f "$LAUNCH_AGENTS_DIR/$label.plist"
done

echo "Removed stock-tracker launch agents from $LAUNCH_AGENTS_DIR"
