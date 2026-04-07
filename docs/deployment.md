# TM4 Deployment Guide

TM4 is designed to run as a systemd service on Ubuntu-based VPS servers.

## Prerequisites
1. **Root Access**: To create system paths and manage services.
2. **Global Runtime Path**: `/var/lib/tm4` (owned by service user).
3. **Application Path**: `/opt/tm4/app` (git checkout location).

## Server Setup
1. **Clone Repo**:
   ```bash
   git clone <repo-url> /opt/tm4/app
   ```

2. **Environment**:
   ```bash
   python3 -m venv /opt/tm4/venv
   source /opt/tm4/venv/bin/activate
   pip install -r /opt/tm4/app/requirements.txt
   ```

3. **Systemd Service**:
   - Template: `systemd/tm4-runner.service`
   - Copy to `/etc/systemd/system/tm4-runner.service`
   - Update `User=YOUR_LINUX_USER`

4. **Initialize Service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable tm4-runner
   sudo systemctl start tm4-runner
   ```

## Environment Variables
- `TM4_BASE_PATH`: Set to `/var/lib/tm4` on the server.
- `TM4_POLL_INTERVAL_S`: Polling frequency for incoming jobs.
