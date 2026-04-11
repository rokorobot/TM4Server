import json
from pathlib import Path
from datetime import datetime
from typing import Any
from ..state import atomic_write_json, utc_now_iso

def write_manifest(run_dir: Path, data: dict[str, Any]):
    """Writes immutable run manifest."""
    atomic_write_json(run_dir / "run_manifest.json", data)

def write_status(run_dir: Path, data: dict[str, Any]):
    """Writes live execution status updates."""
    payload = data.copy()
    payload["updated_at"] = utc_now_iso()
    atomic_write_json(run_dir / "status.json", payload)

def write_summary(run_dir: Path, data: dict[str, Any]):
    """Writes terminal run summary with duration calculation."""
    payload = data.copy()
    
    # Calculate duration if possible
    started = payload.get("started_at")
    completed = payload.get("completed_at")
    if started and completed:
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            comp_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
            payload["duration_s"] = int((comp_dt - start_dt).total_seconds())
        except Exception:
            payload["duration_s"] = 0
    else:
        payload["duration_s"] = 0
        
    atomic_write_json(run_dir / "run_summary.json", payload)
