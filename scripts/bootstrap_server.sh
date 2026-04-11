#!/bin/bash
# =============================================================================
# TM4Server Bootstrap — SERVER
# Idempotent setup script for Ubuntu VPS.
# Run once as the service user (not root, but with sudo access).
# =============================================================================

set -euo pipefail

TM4SERVER_REPO="${TM4SERVER_REPO:-/opt/tm4server}"
TM4_CORE_REPO="${TM4_CORE_REPO:-/opt/tm4-core}"
TM4_BASE="${TM4_BASE_PATH:-/var/lib/tm4}"
TM4_LOGS="${TM4_LOGS:-/var/log/tm4}"
VENV_PATH="${TM4SERVER_REPO}/venv"

echo "============================================="
echo "TM4Server — Server Bootstrap"
echo "TM4Server repo : $TM4SERVER_REPO"
echo "TM4 Core repo  : $TM4_CORE_REPO"
echo "Runtime base   : $TM4_BASE"
echo "Log dir        : $TM4_LOGS"
echo "============================================="

# 0. Create dedicated service user
echo "[0/5] Ensuring 'tm4' service user exists..."
if ! id "tm4" &>/dev/null; then
  sudo useradd -r -s /usr/sbin/nologin tm4
  echo "    User 'tm4' created."
else
  echo "    User 'tm4' already exists — skipping."
fi

# 1. Create runtime directory structure
echo "[1/5] Creating runtime directories..."
sudo mkdir -p "$TM4_BASE/state"
sudo mkdir -p "$TM4_BASE/runs"
sudo mkdir -p "$TM4_BASE/artifacts"
sudo mkdir -p "$TM4_BASE/logs"
sudo mkdir -p "$TM4_BASE/snapshots"
sudo mkdir -p "$TM4_BASE/queue/queued"
sudo mkdir -p "$TM4_BASE/queue/running"
sudo mkdir -p "$TM4_BASE/queue/completed"
sudo mkdir -p "$TM4_BASE/queue/failed"
sudo mkdir -p "$TM4_LOGS"
sudo chown -R tm4:tm4 "$TM4_BASE" "$TM4_LOGS"
echo "    Runtime directories created and owned by 'tm4'."

# 2. Initialize status.json if missing
STATUS_FILE="$TM4_BASE/state/status.json"
if [ ! -f "$STATUS_FILE" ]; then
  echo "[2/5] Initializing status.json..."
  cat > "$STATUS_FILE" <<EOF
{
  "status": "idle",
  "ts_utc": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "current_run": null
}
EOF
else
  echo "[2/5] status.json already exists — skipping."
fi

# 3. Create Python virtualenv for TM4Server
echo "[3/5] Setting up TM4Server virtualenv..."
if [ ! -d "$VENV_PATH" ]; then
  python3 -m venv "$VENV_PATH"
  "$VENV_PATH/bin/pip" install --upgrade pip -q
  echo "    Venv created at $VENV_PATH"
else
  echo "    Venv already exists — skipping."
fi

# Install requirements if any
if [ -f "$TM4SERVER_REPO/requirements.txt" ]; then
  "$VENV_PATH/bin/pip" install -r "$TM4SERVER_REPO/requirements.txt" -q
  echo "    Requirements installed."
fi

# 4. Install systemd service
echo "[4/5] Installing systemd service..."
SERVICE_TEMPLATE="$TM4SERVER_REPO/systemd/tm4-runner.service"
SERVICE_DEST="/etc/systemd/system/tm4-runner.service"

if [ -f "$SERVICE_TEMPLATE" ]; then
  # Replace placeholder username with current user
  sudo sed "s/YOUR_LINUX_USER/$USER/g" "$SERVICE_TEMPLATE" | sudo tee "$SERVICE_DEST" > /dev/null
  sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$TM4SERVER_REPO|g" "$SERVICE_DEST"
  sudo sed -i "s|ExecStart=.*|ExecStart=$VENV_PATH/bin/python -m tm4server.worker|g" "$SERVICE_DEST"
  sudo systemctl daemon-reload
  echo "    Service installed at $SERVICE_DEST"
else
  echo "    WARNING: systemd template not found at $SERVICE_TEMPLATE"
fi

# 5. Run preflight check
echo "[5/5] Running preflight check..."
TM4_AUTONOMY_SCRIPT="${TM4_AUTONOMY_SCRIPT:-$TM4_CORE_REPO/mvp/scripts/run_autonomy_loop.py}"
TM4_PYTHON_BIN="${TM4_PYTHON_BIN:-$TM4_CORE_REPO/venv/bin/python}"

ERRORS=0
[ -d "$TM4_CORE_REPO" ] && echo "    [OK] TM4_CORE_REPO exists" || { echo "    [FAIL] TM4_CORE_REPO missing: $TM4_CORE_REPO"; ERRORS=$((ERRORS+1)); }
[ -f "$TM4_AUTONOMY_SCRIPT" ] && echo "    [OK] TM4_AUTONOMY_SCRIPT exists" || { echo "    [FAIL] TM4_AUTONOMY_SCRIPT missing: $TM4_AUTONOMY_SCRIPT"; ERRORS=$((ERRORS+1)); }
$TM4_PYTHON_BIN --version > /dev/null 2>&1 && echo "    [OK] TM4_PYTHON_BIN resolves ($TM4_PYTHON_BIN)" || { echo "    [FAIL] TM4_PYTHON_BIN not found: $TM4_PYTHON_BIN"; ERRORS=$((ERRORS+1)); }

echo ""
if [ "$ERRORS" -eq 0 ]; then
  echo "============================================="
  echo "Bootstrap complete — all preflight checks passed."
  echo ""
  echo "Next steps:"
  echo "  sudo systemctl enable tm4-runner"
  echo "  sudo systemctl start tm4-runner"
  echo "  sudo systemctl status tm4-runner"
  echo ""
  echo "To submit a test run:"
  echo "  cd $TM4SERVER_REPO"
  echo "  TM4_BASE_PATH=$TM4_BASE $VENV_PATH/bin/python -m tm4server.submit_run --exp-id EXP-AUT-SERVER-0001 --task sanity_check --model qwen2.5:3b"
  echo "============================================="
else
  echo "============================================="
  echo "Bootstrap finished with $ERRORS preflight error(s)."
  echo "Fix the issues above before starting the service."
  echo "============================================="
  exit 1
fi

# Final Ownership Enforcement
echo "[deploy] Enforcing 'tm4' ownership on repositories..."
sudo chown -R tm4:tm4 "$TM4SERVER_REPO" "$TM4_CORE_REPO"
