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


def init_dirs() -> None:
    for d in [RUNS_DIR]:
        ensure_dir(d)


# next_manifest_file is deprecated in favor of StateManager.get_next_pending_run


def process_one(run_dir: Path, state_manager: StateManager | None = None) -> bool:
    """Processes a single run directory by executing the autonomy loop."""
    manifest_path = run_dir / "run_manifest.json"
    state_file = run_dir / "runtime_state.json"
    
    if not manifest_path.exists():
        return False

    manifest = read_json(manifest_path)
    exp_id = manifest.get("exp_id") or manifest.get("experiment_id")
    
    # 1. Update State to Running
    runtime_state = {
        "status": "running",
        "worker_pid": os.getpid(),
        "started_at": utc_now_iso(),
        "updated_at": utc_now_iso()
    }
    write_json(state_file, runtime_state)
    
    # Update global state for visibility
    if state_manager:
        state_manager.write_status(
            runtime_state="running",
            current_exp_id=exp_id,
            queue_depth=state_manager.get_workload_summary(RUNS_DIR).get("pending", 0)
        )

    # 2. Setup environment
    write_json(CURRENT_RUN_FILE, {
        "experiment_id": exp_id,
        "ts_utc": utc_now_iso(),
        "run_dir": str(run_dir),
    })
    
    stdout_log = run_dir / "stdout.log"
    stderr_log = run_dir / "stderr.log"

    try:
        append_line(stdout_log, f"[{utc_now_iso()}] Runner picked job: {exp_id}")
        
        # Executes experiment (writes results.json internally)
        # Note: runtime.py also manages aggregation and reports in its finally block
        results = run_experiment(run_dir, manifest)

        # 3. Terminal Completion (Summary MUST exist before state is terminal)
        summary_path = run_dir / "run_summary.json"
        if not summary_path.exists():
            # Fallback summary if runtime.py didn't write it
            write_json(summary_path, {
                "experiment_id": exp_id,
                "status": "completed",
                "ts_utc": utc_now_iso(),
            })

        runtime_state["status"] = "completed"
        runtime_state["completed_at"] = utc_now_iso()
        runtime_state["updated_at"] = utc_now_iso()
        write_json(state_file, runtime_state)
        
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
        append_line(stdout_log, f"[{utc_now_iso()}] ERROR: {e}")
        append_line(stderr_log, f"[{utc_now_iso()}] " + traceback.format_exc())

        # 3. Terminal Failure
        # Ensure a final attempt at a summary exists before setting state
        summary_path = run_dir / "run_summary.json"
        if not summary_path.exists():
            try:
                write_json(summary_path, {
                    "experiment_id": exp_id,
                    "status": "failed",
                    "error": str(e),
                    "ts_utc": utc_now_iso(),
                })
            except Exception:
                pass

        runtime_state["status"] = "failed"
        runtime_state["failed_at"] = utc_now_iso()
        runtime_state["updated_at"] = utc_now_iso()
        runtime_state["error"] = str(e)
        write_json(state_file, runtime_state)
        
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
