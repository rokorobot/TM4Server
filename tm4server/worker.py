from __future__ import annotations
import time
import os
from pathlib import Path

from .config import (
    POLL_INTERVAL_S, 
    TM4_RUNTIME_ROOT, 
    TM4SERVER_REPO_ROOT, 
    TM4CORE_REPO_ROOT,
    QUEUED_DIR
)
from .runner import init_dirs, process_one
from .state import StateManager


def get_queue_depth() -> int:
    try:
        if not QUEUED_DIR.exists():
            return 0
        return len(list(QUEUED_DIR.glob("*.json")))
    except Exception:
        return 0


def main() -> None:
    init_dirs()
    
    state = StateManager(
        runtime_root=TM4_RUNTIME_ROOT,
        tm4server_repo=TM4SERVER_REPO_ROOT,
        tm4core_repo=TM4CORE_REPO_ROOT,
    )
    
    print(f"TM4 Worker started (polling every {POLL_INTERVAL_S}s)")
    
    # Initialize status
    state.write_status(
        runtime_state="idle",
        current_exp_id=None,
        queue_depth=get_queue_depth()
    )

    try:
        while True:
            # 1. Read control mode
            mode = state.read_control_mode()
            queue_depth = get_queue_depth()

            if mode == "halt":
                state.write_status(
                    runtime_state="halted",
                    current_exp_id=None,
                    queue_depth=queue_depth
                )
                print("Worker halting as requested.")
                break

            if mode == "pause":
                # Heartbeat update while paused
                state.write_status(
                    runtime_state="paused",
                    current_exp_id=None,
                    queue_depth=queue_depth
                )
                time.sleep(POLL_INTERVAL_S)
                continue

            # 2. Normal run mode
            try:
                processed = process_one(state_manager=state)
                if not processed:
                    # Idle heartbeat
                    state.write_status(
                        runtime_state="idle",
                        current_exp_id=None,
                        queue_depth=queue_depth
                    )
                    time.sleep(POLL_INTERVAL_S)
                else:
                    # Run completed (process_one handled the 'running' status)
                    # We update back to idle here
                    state.write_status(
                        runtime_state="idle",
                        current_exp_id=None,
                        queue_depth=get_queue_depth()
                    )
            except Exception as e:
                state.write_status(
                    runtime_state="error",
                    current_exp_id=None,
                    queue_depth=get_queue_depth(),
                    extra={"last_error": str(e)}
                )
                print(f"Loop error: {e}")
                time.sleep(POLL_INTERVAL_S)

    except KeyboardInterrupt:
        state.write_status(
            runtime_state="halted",
            current_exp_id=None,
            queue_depth=get_queue_depth(),
            extra={"reason": "keyboard_interrupt"}
        )
        print("Worker stopped by user.")


if __name__ == "__main__":
    main()
