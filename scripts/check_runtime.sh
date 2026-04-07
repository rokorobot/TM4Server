#!/bin/bash

# TM4 Runtime Status Checker
# Shows the current state of the local queue and workspace.

# Get the repository root
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Base Path
TM4_BASE="${TM4_BASE_PATH:-$REPO_ROOT/local_runtime}"

echo "Checking TM4 Runtime at $TM4_BASE..."

# Display status.json
if [ -f "$TM4_BASE/state/status.json" ]; then
  echo "Current Status (status.json):"
  cat "$TM4_BASE/state/status.json" | python3 -m json.tool
else
  echo "No status.json found."
fi

# Show queue counts
echo -e "\nQueue Counts:"
echo "Queued:    $(ls "$TM4_BASE/queue/queued" | wc -l)"
echo "Running:   $(ls "$TM4_BASE/queue/running" | wc -l)"
echo "Completed: $(ls "$TM4_BASE/queue/completed" | wc -l)"
echo "Failed:    $(ls "$TM4_BASE/queue/failed" | wc -l)"

# List recent runs (last 5)
echo -e "\nRecent Runs:"
ls -dt "$TM4_BASE/runs"/* 2>/dev/null | head -n 5
