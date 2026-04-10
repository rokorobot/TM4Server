from __future__ import annotations
import time
import os
from pathlib import Path

from .config import (
    POLL_INTERVAL_S, 
    TM4_RUNTIME_ROOT, 
    TM4SERVER_REPO_ROOT, 
    TM4CORE_REPO_ROOT,
    RUNS_DIR
)
from .runner import init_dirs, process_one
from .state import StateManager


def get_queue_depth(state: StateManager) -> int:
    try:
        summary = state.get_workload_summary(RUNS_DIR)
        return summary.get("pending", 0)
    except Exception:
        return 0


def main() -> None:
    init_dirs()
    
    state = StateManager(
        runtime_root=TM4_RUNTIME_ROOT,
        tm4server_repo=TM4SERVER_REPO_ROOT,
        tm4core_repo=TM4CORE_REPO_ROOT,
    )
    state.ensure_defaults()
    
    print(f"TM4 Worker started (polling every {POLL_INTERVAL_S}s)")
    
    # 0. Crash Recovery Scan
    interrupted = state.scan_for_interrupted_runs(RUNS_DIR)
    if interrupted:
        print(f"Crash recovery: found and marked {interrupted} interrupted runs.")
    
    # Initialize status
    state.write_status(
        runtime_state="idle",
        current_exp_id=None,
        queue_depth=get_queue_depth(state)
    )

    try:
        while True:
            # 1. Read control mode and workload
            mode = state.read_control_mode()
            pending_run = state.get_next_pending_run(RUNS_DIR)
            queue_depth = get_queue_depth(state)

            # 1. Dispatch by Mode
            if mode == "halt":
                state.write_status(runtime_state="halted", queue_depth=queue_depth)
                time.sleep(POLL_INTERVAL_S)
                continue

            if mode == "pause":
                state.write_status(runtime_state="paused", queue_depth=queue_depth)
                time.sleep(POLL_INTERVAL_S)
                continue

            # 2. Run mode: check for work
            try:
                if not pending_run:
                    # Idle state: symmetrical heartbeat
                    state.write_status(runtime_state="idle", queue_depth=queue_depth)
                    time.sleep(POLL_INTERVAL_S)
                    continue
                
                # We have a run and mode is "run" -> process it
                processed = process_one(run_dir=pending_run, state_manager=state)
                
                # Update back to idle or next pending check
                state.write_status(runtime_state="idle", queue_depth=get_queue_depth(state))
                
            except Exception as e:
                state.write_status(
                    runtime_state="error",
                    queue_depth=get_queue_depth(state),
                    extra={"last_error": str(e)}
                )
                print(f"Loop error: {e}")
                time.sleep(POLL_INTERVAL_S)

    except KeyboardInterrupt:
        state.write_status(
            runtime_state="halted",
            queue_depth=get_queue_depth(state),
            extra={"reason": "keyboard_interrupt"}
        )
        print("\nWorker stopped by signal (KeyboardInterrupt).")


if __name__ == "__main__":
    main()
