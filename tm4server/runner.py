from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path
import shutil
import traceback
import os

if TYPE_CHECKING:
    from .state import StateManager

from .config import (
    QUEUED_DIR,
    RUNNING_DIR,
    COMPLETED_DIR,
    FAILED_DIR,
    RUNS_DIR,
    CURRENT_RUN_FILE,
)
from .utils import ensure_dir, read_json, write_json, utc_now_iso, append_line
from .runtime import run_experiment, _emit_event
from .execution import artifacts


def init_dirs() -> None:
    for d in [RUNS_DIR]:
        ensure_dir(d)


# next_manifest_file is deprecated in favor of StateManager.get_next_pending_run


def process_one(run_dir: Path, state_manager: StateManager | None = None) -> bool:
    """Processes a single run directory by executing the autonomy loop."""
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return False
    
    # 0. Load Intent (Spec v1)
    try:
        manifest = read_json(manifest_path)
        exp_id = manifest.get("exp_id") or "unknown"
    except Exception:
        return False

    # 1. Update State to Running (Spec v1)
    status_data = {
        "status": "running",
        "started_at": artifacts.utc_now_z(),
    }
    artifacts.write_status(run_dir, status_data)
    
    # Update global state for visibility
    if state_manager:
        state_manager.write_status(
            runtime_state="running",
            current_exp_id=exp_id,
            queue_depth=state_manager.get_workload_summary(RUNS_DIR).get("pending", 0)
        )

    # 2. Setup environment
    write_json(CURRENT_RUN_FILE, {
        "exp_id": exp_id,
        "ts_utc": artifacts.utc_now_z(),
        "run_dir": str(run_dir),
    })
    
    stdout_log = run_dir / "stdout.log"
    stderr_log = run_dir / "stderr.log"

    try:
        append_line(stdout_log, f"[{artifacts.utc_now_z()}] Runner picked job: {exp_id}")
        
        # Executes experiment (writes results.json internally)
        # Note: runtime.py manages aggregation and the SOLE terminal summary write in its finally block
        results = run_experiment(run_dir, manifest)

        # 3. Relinquish summary ownership (Model A)
        # We NO LONGER write_summary here. runtime.py handles it.
        
        # 4. Sync Global Status
        if state_manager:
            try:
                state_manager.write_status(
                    runtime_state="idle",
                    reset_current=True,
                    queue_depth=state_manager.get_workload_summary(RUNS_DIR).get("pending", 0),
                    last_completed_exp_id=exp_id
                )
            except Exception:
                pass

        return True

    except Exception as e:
        append_line(stdout_log, f"[{artifacts.utc_now_z()}] ERROR: {e}")
        append_line(stderr_log, f"[{artifacts.utc_now_z()}] " + traceback.format_exc())

        # 3. Terminal Failure Status (NOT Summary)
        # We write status to indicate failure to external state manager
        artifacts.write_status(run_dir, {
            "status": "failed",
            "error": str(e),
        })
        
        if state_manager:
             try:
                state_manager.write_status(
                    runtime_state="idle",
                    reset_current=True,
                    queue_depth=state_manager.get_workload_summary(RUNS_DIR).get("pending", 0),
                    extra={"last_error": str(e)}
                )
             except Exception:
                pass

        return True
