#!/bin/bash
# =============================================================================
# TM4Server — Server Deploy Script
# Pulls latest code and restarts the service.
# Safe to run repeatedly (idempotent).
# =============================================================================

set -euo pipefail

TM4SERVER_REPO="${TM4SERVER_REPO:-/opt/tm4server}"
TM4_CORE_REPO="${TM4_CORE_REPO:-/opt/tm4-core}"

echo "[deploy] Pulling TM4Server repo..."
git -C "$TM4SERVER_REPO" pull --ff-only

echo "[deploy] Pulling TM4 Core repo..."
git -C "$TM4_CORE_REPO" pull --ff-only

echo "[deploy] Installing/updating TM4Server requirements..."
"$TM4SERVER_REPO/venv/bin/pip" install -r "$TM4SERVER_REPO/requirements.txt" -q

echo "[deploy] Restarting tm4-runner service..."
sudo systemctl restart tm4-runner
sudo systemctl status tm4-runner --no-pager -l

echo "[deploy] Done."
