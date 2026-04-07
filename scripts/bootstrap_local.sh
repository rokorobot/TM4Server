#!/bin/bash

# TM4 Local Bootstrap Script
# Initializes the local simulation runtime directory structure.

# Get the directory of this script
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Base Path (defaults to local_runtime in the repo root)
TM4_BASE="${TM4_BASE_PATH:-$REPO_ROOT/local_runtime}"

echo "Initializing TM4 local runtime at $TM4_BASE..."

# Create core structure
mkdir -p "$TM4_BASE/state"
mkdir -p "$TM4_BASE/runs"
mkdir -p "$TM4_BASE/artifacts"
mkdir -p "$TM4_BASE/logs"
mkdir -p "$TM4_BASE/snapshots"

# Create queue structure
mkdir -p "$TM4_BASE/queue/queued"
mkdir -p "$TM4_BASE/queue/running"
mkdir -p "$TM4_BASE/queue/completed"
mkdir -p "$TM4_BASE/queue/failed"

# Initialize state
if [ ! -f "$TM4_BASE/state/status.json" ]; then
  cat > "$TM4_BASE/state/status.json" <<EOF
{
  "status": "idle",
  "ts_utc": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "current_run": null
}
EOF
fi

echo "TM4 Local Bootstrap Complete."
ls -R "$TM4_BASE"
