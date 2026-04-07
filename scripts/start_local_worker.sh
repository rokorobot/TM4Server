#!/bin/bash

# TM4 Local Worker Runner
# Runs the TM4 worker using local environment variables.

# Get the repository root
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Base Path (defaults to local_runtime in the repo root)
export TM4_BASE_PATH="${TM4_BASE_PATH:-$REPO_ROOT/local_runtime}"
export TM4_POLL_INTERVAL_S="${TM4_POLL_INTERVAL_S:-3}"

echo "Starting TM4 Local Worker..."
echo "Runtime: $TM4_BASE_PATH"

# Go to REPO_ROOT and run the worker module
cd "$REPO_ROOT"
python3 -m tm4server.worker
