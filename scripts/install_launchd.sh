#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/osori/workbench/stock-tracker"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
UV_BIN="$(command -v uv)"
UID_VALUE="$(id -u)"
LABEL_PREFIX="com.osori.stock-tracker"

export PROJECT_DIR LAUNCH_AGENTS_DIR

if [ -z "$UV_BIN" ]; then
  echo "uv binary not found in PATH" >&2
  exit 1
fi

mkdir -p "$PROJECT_DIR/logs" "$LAUNCH_AGENTS_DIR"

"$UV_BIN" run python - <<'PY'
import os
from stock_tracker.launchd import write_launch_agent_plists
paths = write_launch_agent_plists(
    project_dir=os.environ["PROJECT_DIR"],
    output_dir=os.environ["LAUNCH_AGENTS_DIR"],
)
for path in paths:
    print(path)
PY

for mode in open noon close; do
  label="$LABEL_PREFIX.$mode"
  plist="$LAUNCH_AGENTS_DIR/$label.plist"
  launchctl bootout "gui/$UID_VALUE/$label" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$UID_VALUE" "$plist"
  launchctl enable "gui/$UID_VALUE/$label"
done

launchctl print "gui/$UID_VALUE/$LABEL_PREFIX.open" | sed -n '1,40p'
launchctl print "gui/$UID_VALUE/$LABEL_PREFIX.noon" | sed -n '1,40p'
launchctl print "gui/$UID_VALUE/$LABEL_PREFIX.close" | sed -n '1,40p'
