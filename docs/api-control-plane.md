# TM4Server API Control Plane - Technical Documentation

The TM4Server Control Plane provides a stable, governed HTTP interface for monitoring and controlling the experiment worker.

## 🛡️ Governance & Integrity Policy

The API follows a strict **Fail-Closed** policy for data integrity:
- **Existence vs. Corruption**: Missing state files (`status.json`, `control.json`) result in safe defaults. However, **corrupted JSON** or **semantically invalid schemas** result in a hard `500 Internal Server Error`.
- **Audit Integrity**: The control history is treated as a high-integrity audit trail. A single malformed line in `control_history.jsonl` invalidates the entire response, as partial audit logs are untrustworthy.
- **No Side-Effects on Read**: Initializing or querying the API (GET requests) is strictly non-mutating. Audit logs and state files are only updated during explicit bootstrap or mutation paths (POST requests).

## 📡 Endpoints (v1)

### System
- `GET /healthz`: Process-level health check. Returns `{"ok": true}`.
- `GET /api/system/version`: Resilient metadata endpoint. Returns API version, git commit, and instance identity. Degrades gracefully to "unknown" if status data is unreadable.

### Status
- `GET /api/status`: Returns current runtime status from `status.json`.
  - **Schema Error**: If `status.json` is corrupted, returns `500 MALFORMED_STATE_FILE`.

### Control
- `GET /api/control/state`: Returns the current operator-requested mode (`run`, `pause`, `halt`).
  - **Integrity Check**: If `control.json` contains an invalid mode (e.g., `{"mode": "banana"}`), returns `500 INVALID_CONTROL_STATE`.
- `POST /api/control/run`: Sets mode to `run`.
- `POST /api/control/pause`: Sets mode to `pause`.
- `POST /api/control/halt`: Sets mode to `halt`.
- `GET /api/control/history`: Returns latest operator events from `control_history.jsonl`.
  - **Params**: `limit` (1-500, default 50).
  - **Strict Policy**: Any malformed JSONL entry triggers `500 AUDIT_LOG_CORRUPTION`.

## ⚠️ Error Envelope

All errors use a unified JSON schema for predictable client consumption:

```json
{
  "ok": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation",
    "details": []  // Optional: only present for VALIDATION_ERROR (422)
  }
}
```

## ⚙️ Deployment

- **Canonical Path**: `/opt/tm4server` (repo) and `/var/lib/tm4` (runtime).
- **Service**: Managed by `systemd` via `systemd/tm4-api.service`.
- **Environment**: Configuration sourced from `/etc/tm4server.env`.
