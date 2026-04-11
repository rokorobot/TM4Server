import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "v1"
ALLOWED_STATUSES = {"queued", "running", "success", "failed", "interrupted", "unknown"}
TERMINAL_STATUSES = {"success", "failed", "interrupted"}


def detect_instance_id() -> str:
    """Resolves the instance ID from environment or hostname (Spec v1)."""
    return (
        os.environ.get("TM4_INSTANCE_ID")
        or os.environ.get("HOSTNAME")
        or socket.gethostname()
        or "unknown-instance"
    )


def utc_now_z() -> str:
    """Returns a standardized UTC ISO-8601 timestamp with Z suffix (Spec v1)."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _is_valid_iso_z(ts: Any) -> bool:
    """Strictly validates ISO-8601 UTC with Z suffix (Spec v1)."""
    if not isinstance(ts, str) or not ts.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Enforces the atomic write requirement (Spec v1) via temp-file + replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".{os.getpid()}.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def write_manifest(run_dir: Path, data: dict[str, Any]) -> None:
    """
    Writes immutable run_manifest.json (Spec v1).
    Validation: required fields, immutability, timestamp format.
    """
    path = run_dir / "run_manifest.json"
    if path.exists():
        raise FileExistsError(f"Immutability Violation: {path.name} already exists.")

    payload = data.copy()
    
    # Required Fields Check
    required = ["run_id", "exp_id", "workload_type", "requested_by", "created_at"]
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"run_manifest missing required fields: {missing}")

    # Timestamp Validation
    if not _is_valid_iso_z(payload["created_at"]):
        raise ValueError(f"Invalid created_at format: {payload['created_at']}. Must be ISO-8601 Z.")

    payload["schema_version"] = SCHEMA_VERSION
    _atomic_write_json(path, payload)


def write_status(run_dir: Path, data: dict[str, Any]) -> None:
    """
    Writes mutable status.json (Spec v1).
    Validation: status enum, started_at requirement, timestamp formats.
    Injection: instance_id, worker_pid, updated_at.
    """
    path = run_dir / "status.json"
    payload = data.copy()

    # Enum Validation
    status = payload.get("status", "unknown")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status value: {status}. Must be one of {ALLOWED_STATUSES}")

    # Load existing to preserve fields (Spec v1 Resilience)
    existing = {}
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    # Injection (Spec v1)
    payload["schema_version"] = SCHEMA_VERSION
    payload["run_id"] = payload.get("run_id") or existing.get("run_id") or run_dir.name
    
    # Instance ID Preservation (Tightening 2C.1)
    payload["instance_id"] = payload.get("instance_id") or existing.get("instance_id") or detect_instance_id()
    
    payload["worker_pid"] = payload.get("worker_pid") or existing.get("worker_pid") or os.getpid()
    payload["updated_at"] = utc_now_z()

    # started_at Requirement & Preservation (Tightening 2C.1)
    # It must be provided on first write or preserved from existing
    started_at = payload.get("started_at") or existing.get("started_at")
    if not started_at:
        # If we are marking as running, we SHOULD have started_at
        if status == "running":
            started_at = utc_now_z()
        else:
            raise ValueError("status.json requires 'started_at' field (Spec v1 Requirement).")
    
    payload["started_at"] = started_at

    # Timestamp Validation (Tightening 2C.1)
    for ts_key in ["started_at", "completed_at"]:
        val = payload.get(ts_key)
        if val:
            if not _is_valid_iso_z(val):
                raise ValueError(f"Invalid {ts_key} format: {val}. Must be ISO-8601 Z.")

    _atomic_write_json(path, payload)


def write_summary(run_dir: Path, data: dict[str, Any]) -> None:
    """
    Writes immutable run_summary.json (Spec v1).
    Validation: terminal status, duration, required fields, immutability, timestamps.
    """
    path = run_dir / "run_summary.json"
    if path.exists():
        raise FileExistsError(f"Immutability Violation: {path.name} already exists.")

    payload = data.copy()

    # Terminal Status Validation
    status = payload.get("status", "unknown")
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"Invalid terminal status: {status}. Must be one of {TERMINAL_STATUSES}")

    # Timestamp Validation
    for ts_key in ["started_at", "completed_at"]:
        if ts_key in payload and payload[ts_key]:
            if not _is_valid_iso_z(payload[ts_key]):
                raise ValueError(f"Invalid {ts_key} format: {payload[ts_key]}. Must be ISO-8601 Z.")

    # Duration Calculation
    if "duration_s" not in payload:
        started = payload.get("started_at")
        completed = payload.get("completed_at")
        if started and completed:
            try:
                s_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                c_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                payload["duration_s"] = round((c_dt - s_dt).total_seconds(), 3)
            except Exception:
                payload["duration_s"] = 0
        else:
            payload["duration_s"] = 0

    # Required Fields
    payload["schema_version"] = SCHEMA_VERSION
    payload["run_id"] = payload.get("run_id") or run_dir.name
    payload["instance_id"] = payload.get("instance_id") or detect_instance_id() # Mandatory forensic injection
    payload["exit_code"] = payload.get("exit_code", 0 if status == "success" else 1)
    
    provenance = payload.get("provenance", {})
    provenance["summary_generated_at"] = utc_now_z()
    provenance["writer"] = "tm4server.execution.artifacts"
    provenance["generator_version"] = "v1"
    payload["provenance"] = provenance

    # Identity consensus check & exp_id propagation
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                man = json.load(f)
                payload["run_id"] = man.get("run_id", payload["run_id"])
                # Propagate exp_id from manifest (Tightening 2C.1)
                payload["exp_id"] = man.get("exp_id", payload.get("exp_id"))
        except Exception:
            pass

    _atomic_write_json(path, payload)
