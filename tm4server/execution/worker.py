import time
import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime

from .artifacts import write_manifest, write_status, write_summary, utc_now_z
from .launcher import build_tm4_command
from ..state import StateManager

# Default paths for worker context
TM4_RUNTIME_ROOT = Path(os.getenv("TM4_RUNTIME_ROOT", "/var/lib/tm4"))
TM4SERVER_REPO_ROOT = Path(os.getenv("TM4SERVER_REPO_ROOT", "/opt/tm4server"))
TM4CORE_REPO_ROOT = Path(os.getenv("TM4CORE_REPO_ROOT", "/opt/tm4-core"))

def generate_run_id() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"RUN-{ts}"

def run_worker():
    """
    Main persistent worker daemon for TM4Server Phase 2A.
    Absolute single-run discipline via StateManager.get_active_run() and one-shot intent claim.
    """
    state = StateManager(
        runtime_root=TM4_RUNTIME_ROOT,
        tm4server_repo=TM4SERVER_REPO_ROOT,
        tm4core_repo=TM4CORE_REPO_ROOT
    )
    
    # Ensure safe defaults exist on startup
    state.ensure_defaults()
    
    print(f"[*] TM4 Runner started. Polling {TM4_RUNTIME_ROOT}/state")
    
    while True:
        try:
            # 1. Check intent vs reality
            control_mode = state.get_control_state()
            active_run = state.get_active_run()
            
            # Absolute single-run discipline: if busy, just poll.
            # No parallel fallback, no background triggers.
            if control_mode != "run" or active_run is not None:
                time.sleep(2)
                continue
                
            # 2. CONSUME intent immediately: One-Shot Trigger
            # This prevents infinite relaunch loops.
            state.set_control_mode("pause", source="worker_claim")
            
            # 3. Trigger confirmed: Initialize concrete run
            run_id = generate_run_id()
            # Every run needs a unique evidence identity
            exp_id = f"EXP-AUT-SERVER-{run_id.replace('RUN-', '')}"
            
            runs_root = TM4_RUNTIME_ROOT / "runs"
            run_dir = runs_root / run_id
            
            started_at = utc_now_z()
            completed_at = None
            
            try:
                # No silent reuse: exist_ok=False
                run_dir.mkdir(parents=True, exist_ok=False)
                
                # 4. Write immutable manifest (Spec v1)
                manifest = {
                    "run_id": run_id,
                    "exp_id": exp_id,
                    "workload_type": "tm4_autonomy_loop",
                    "requested_by": "operator",
                    "created_at": started_at,
                }
                write_manifest(run_dir, manifest)
                
                # 5. Set authoritative active lock (SINGLE-RUN AUTHORITY)
                state.set_active_run(run_id, manifest)
                
                # 6. Global truth anchor: Update status to busy
                state.set_runtime_execution_status(
                    runtime_state="busy",
                    current_run_id=run_id,
                    extra={
                        "active_run_id": run_id,
                        "active_exp_id": exp_id,
                        "workload_type": "tm4_autonomy_loop"
                    }
                )
                
                # 7. Build and launch
                cmd, env = build_tm4_command(TM4CORE_REPO_ROOT, run_dir)
                
                stdout_f = open(run_dir / "stdout.log", "w", encoding="utf-8")
                stderr_f = open(run_dir / "stderr.log", "w", encoding="utf-8")
                
                try:
                    process = subprocess.Popen(
                        cmd,
                        stdout=stdout_f,
                        stderr=stderr_f,
                        cwd=str(TM4CORE_REPO_ROOT),
                        env=env
                    )
                    
                    # 8. Local status mid-run (Spec v1 status.json)
                    write_status(run_dir, {
                        "run_id": run_id,
                        "status": "running",
                        "started_at": started_at,
                        "worker_pid": process.pid,
                    })
                    
                    # 9. Wait for completion
                    exit_code = process.wait()
                    completed_at = utc_now_z()
                finally:
                    stdout_f.close()
                    stderr_f.close()
                
                # 10. Final terminal summary (Model A authority for production)
                write_summary(run_dir, {
                    "run_id": run_id,
                    "exp_id": exp_id,
                    "status": "success" if exit_code == 0 else "failed",
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "exit_code": exit_code,
                    "artifact_root": str(run_dir),
                })
                
                # 11. Global truth anchor: Update status to idle
                state.set_runtime_execution_status(
                    runtime_state="idle",
                    current_run_id=None,
                    last_completed_run_id=run_id,
                    extra={
                        "active_run_id": None,
                        "active_exp_id": None,
                        "workload_type": None,
                        "last_error": None,
                        "last_exit_code": exit_code,
                        "last_run_status": "success" if exit_code == 0 else "failed",
                        "last_exp_id": exp_id
                    }
                )
                
            except Exception as e:
                # Emergency terminal summary on failure (Fail-Closed Evidence)
                print(f"[!] Launch failure: {e}")
                completed_at = utc_now_z()
                
                if run_dir.exists():
                    write_summary(run_dir, {
                        "run_id": run_id,
                        "exp_id": exp_id,
                        "status": "failed",
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "exit_code": -1,
                        "artifact_root": str(run_dir),
                        "error": str(e)
                    })
                
                # Global fail state reflection
                state.set_runtime_execution_status(
                    runtime_state="idle",
                    current_run_id=None,
                    last_completed_run_id=run_id,
                    extra={
                        "active_run_id": None,
                        "active_exp_id": None,
                        "workload_type": None,
                        "last_exit_code": -1,
                        "last_run_status": "failed",
                        "last_exp_id": exp_id,
                        "last_error": str(e)
                    }
                )
            finally:
                # Always clear the authoritative lock for this specific run
                active = state.get_active_run()
                if active and active.get("run_id") == run_id:
                    state.clear_active_run()
                
        except Exception as e:
            print(f"[!!] Worker loop error: {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    run_worker()
