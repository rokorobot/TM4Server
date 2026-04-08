# TM4Server Deployment Guide (v1.0 — Hardened)

Complete, reproducible instructions for deploying TM4Server and TM4 Core to an Ubuntu VPS.

## 🧠 Architecture Overview

```text
/opt/tm4server/          # API + orchestration layer
/opt/tm4-core/           # TM4 autonomy engine
/opt/tm4server/venv/     # Python virtualenv
/var/lib/tm4/            # runtime state (queue, runs, artifacts)
/var/log/tm4/            # logs
/etc/tm4server.env       # environment config
```

## ⚙️ Prerequisites

- Ubuntu 22.04+
- Python 3.11+
- git
- systemd
- sudo access

---

## 1️⃣ System Preparation

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
  python3.11 python3.11-venv python3-pip \
  git curl build-essential \
  jq
```

👉 Ensure Python version:
```bash
python3.11 --version
```

---

## 2️⃣ Directory Layout (Correct Permissions)

```bash
sudo mkdir -p /opt/tm4server /opt/tm4-core
sudo mkdir -p /var/lib/tm4 /var/log/tm4

sudo chown -R $USER:$USER /opt/tm4server /opt/tm4-core
sudo chown -R $USER:$USER /var/lib/tm4 /var/log/tm4
```

---

## 3️⃣ Clone Repositories

```bash
git clone <TM4SERVER_REPO_URL> /opt/tm4server
git clone <TM4_CORE_REPO_URL> /opt/tm4-core
```

---

## 4️⃣ Python Virtual Environment (Isolated + Deterministic)

```bash
cd /opt/tm4server

python3.11 -m venv venv
source venv/bin/activate

pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
```

---

## 5️⃣ Environment Configuration (Centralized)

Create the configuration file:
```bash
sudo nano /etc/tm4server.env
```

Add the following content:
```ini
# === Core Paths ===
TM4_CORE_PATH=/opt/tm4-core
TM4_STATE_DIR=/var/lib/tm4
TM4_LOG_DIR=/var/log/tm4

# === Runtime ===
PYTHONUNBUFFERED=1
TM_T_MAX=0
TM_STEERING_STRENGTH=0.7
TM_ANCHOR_REGIME=A1_WEAKENED_ANCHOR

# === Model (Ollama local) ===
OLLAMA_BASE_URL=http://127.0.0.1:11434

# === API ===
HOST=0.0.0.0
PORT=8000
```

Secure it:
```bash
sudo chmod 600 /etc/tm4server.env
```

---

## 6️⃣ Ollama Setup (Local Model Runtime)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Start + enable:
```bash
sudo systemctl enable ollama
sudo systemctl start ollama
```

Pull model:
```bash
ollama pull qwen2.5:3b
```

Test:
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:3b",
  "prompt": "ping"
}'
```

---

## 7️⃣ Systemd Service (Production Control Layer)

Create the service file:
```bash
sudo nano /etc/systemd/system/tm4server.service
```

Add the following content:
```ini
[Unit]
Description=TM4 Server
After=network.target ollama.service

[Service]
User=ubuntu
WorkingDirectory=/opt/tm4server
EnvironmentFile=/etc/tm4server.env

ExecStart=/opt/tm4server/venv/bin/python -m uvicorn server.dashboard:app \
  --host ${HOST} --port ${PORT}

Restart=always
RestartSec=3

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

# Logging
StandardOutput=append:/var/log/tm4/server.log
StandardError=append:/var/log/tm4/server.err

[Install]
WantedBy=multi-user.target
```

---

## 8️⃣ Enable + Start Service

```bash
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

sudo systemctl enable tm4server
sudo systemctl start tm4server
```

---

## 9️⃣ Health Checks

**API:**
```bash
curl http://localhost:8000/status
```

**Logs:**
```bash
tail -f /var/log/tm4/server.log
```

**Service:**
```bash
systemctl status tm4server
```

---

## 🔟 Optional: Firewall (Production Safe)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8000
sudo ufw enable
```

---

## 🧪 11️⃣ Validation Checklist

- [ ] `/status` returns JSON
- [ ] Ollama responds locally
- [ ] Runs persist in `/var/lib/tm4`
- [ ] Logs written to `/var/log/tm4`
- [ ] No crash loops (`systemctl status` clean)

---

## ⚠️ Common Failure Modes (Now Eliminated)

| Issue | Fix in v1.0 |
|---|---|
| Wrong Python version | Forced python3.11 |
| Missing env vars | Centralized `/etc/tm4server.env` |
| Permission errors | Explicit `chown` |
| Silent crashes | `systemd` logging + restart |
| Model not reachable | Ollama `systemd` integration |
| Path inconsistencies | Canonical `/opt` + `/var` layout |

---

## 🧠 Operator Notes (Important for TM4 Evolution)

- State + logs are externally visible and auditable (critical for governance layer).
- You now have a stable base for multi-agent arenas + batch experiments.
- **Git Sync Note**: Automated report pushing requires `TM4_DOCS_ROOT` to resolve inside the `TM4Server` Git repository.
