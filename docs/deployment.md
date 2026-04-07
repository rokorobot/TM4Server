# TM4 VPS Deployment Guide

Complete, copy-paste instructions for deploying TM4Server to an Ubuntu VPS.

## Server Layout

```text
/opt/tm4server/          # TM4Server repo (this repo)
/opt/tm4server/venv/     # Python virtualenv for TM4Server
/opt/tm4-core/           # TM4 core repo (autonomy loop)
/var/lib/tm4/            # Runtime state (queue, runs, artifacts)
/var/log/tm4/            # Service logs
```

## Prerequisites

- Ubuntu 22.04+
- Python 3.11+
- git
- sudo access

---

## Step 1: Clone Both Repos

```bash
sudo mkdir -p /opt/tm4server /opt/tm4-core
sudo chown -R $USER:$USER /opt/tm4server /opt/tm4-core

git clone <TM4SERVER_REPO_URL> /opt/tm4server
git clone <TM4_CORE_REPO_URL> /opt/tm4-core
```

---

## Step 2: Run Server Bootstrap

This script is idempotent — safe to run multiple times.

```bash
cd /opt/tm4server
bash scripts/bootstrap_server.sh
```

It will:
- Create all `/var/lib/tm4/` and `/var/log/tm4/` directories
- Initialize `status.json`
- Create the TM4Server Python virtualenv at `/opt/tm4server/venv/`
- Install the systemd service (replacing `YOUR_LINUX_USER` with the current user)
- Run a preflight check against TM4 core paths

---

## Step 3: Configure Environment

The systemd service reads environment from its unit file. If you need to override paths, edit `/etc/systemd/system/tm4-runner.service`:

```ini
[Service]
Environment=TM4_BASE_PATH=/var/lib/tm4
Environment=TM4_POLL_INTERVAL_S=3
Environment=TM4_CORE_PATH=/opt/tm4-core
Environment=TM4_AUTONOMY_SCRIPT=/opt/tm4-core/mvp/scripts/run_autonomy_loop.py
Environment=TM4_PYTHON_BIN=/opt/tm4-core/venv/bin/python
```

After editing:

```bash
sudo systemctl daemon-reload
```

---

## Step 4: Enable and Start the Service

```bash
sudo systemctl enable tm4-runner
sudo systemctl start tm4-runner
sudo systemctl status tm4-runner
```

---

## Step 5: First Server Run (Controlled Test)

Submit a single sanity-check run manually:

```bash
cd /opt/tm4server
TM4_BASE_PATH=/var/lib/tm4 \
TM4_CORE_PATH=/opt/tm4-core \
TM4_AUTONOMY_SCRIPT=/opt/tm4-core/mvp/scripts/run_autonomy_loop.py \
TM4_PYTHON_BIN=/opt/tm4-core/venv/bin/python \
/opt/tm4server/venv/bin/python -m tm4server.submit_run \
  --exp-id EXP-AUT-SERVER-0001 \
  --task sanity_check \
  --model qwen2.5:3b
```

Then watch it process:

```bash
# Tail the service log
tail -f /var/log/tm4/tm4-runner.log

# Check runtime state
cat /var/lib/tm4/state/status.json

# Inspect run outputs when complete
ls -la /var/lib/tm4/runs/EXP-AUT-SERVER-0001/
cat /var/lib/tm4/runs/EXP-AUT-SERVER-0001/status.json
cat /var/lib/tm4/runs/EXP-AUT-SERVER-0001/results.json
```

---

## Step 6: Ongoing Deployments

After the first successful run, use the deploy script to update:

```bash
cd /opt/tm4server
bash scripts/deploy_server.sh
```

This pulls both repos and restarts the service.

---

## Environment Variables Reference

| Variable | Default (local) | Server value |
|---|---|---|
| `TM4_BASE_PATH` | `./local_runtime` | `/var/lib/tm4` |
| `TM4_POLL_INTERVAL_S` | `3` | `3` |
| `TM4_CORE_PATH` | `C:\Users\Robert\TM4` | `/opt/tm4-core` |
| `TM4_AUTONOMY_SCRIPT` | `<core>/mvp/scripts/run_autonomy_loop.py` | `/opt/tm4-core/mvp/scripts/run_autonomy_loop.py` |
| `TM4_PYTHON_BIN` | `python` | `/opt/tm4-core/venv/bin/python` |

---

## Run Output Files (per experiment)

Every run in `/var/lib/tm4/runs/<EXP-ID>/` will contain:

| File | Description |
|---|---|
| `manifest.json` | Original job manifest |
| `tm4_input_manifest.json` | Sanitised input actually sent to TM4 core |
| `config.json` | **Resolved config snapshot** (paths, git hashes, params) |
| `stdout.log` | Combined stdout from TM4Server + TM4 core |
| `stderr.log` | Stderr from TM4 core subprocess |
| `event_log.jsonl` | TM4Server event trail (preflight, subprocess lifecycle) |
| `results.json` | Run summary, git hashes, duration, artifact inventory |
| `status.json` | Final status with `preflight_status` and `duration_s` |

---

## Troubleshooting

**Preflight fails:**
```bash
cat /var/lib/tm4/runs/<EXP-ID>/stderr.log
cat /var/lib/tm4/runs/<EXP-ID>/status.json
```

**Service won't start:**
```bash
journalctl -u tm4-runner -n 50
```

**Job stuck in `running/`:**
```bash
# Move back to queued manually
mv /var/lib/tm4/queue/running/<EXP-ID>.json /var/lib/tm4/queue/queued/
sudo systemctl restart tm4-runner
```
