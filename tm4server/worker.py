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
    state.ensure_defaults()
    
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
                processed = process_one(state_manager=state)
                if not processed:
                    # Idle state: symmetrical heartbeat
                    state.write_status(runtime_state="idle", queue_depth=queue_depth)
                    time.sleep(POLL_INTERVAL_S)
                    continue
                
                # If we processed something, process_one handled the 'running' status.
                # We update back to idle for the next cycle.
                state.write_status(runtime_state="idle", queue_depth=get_queue_depth())
                
            except Exception as e:
                state.write_status(
                    runtime_state="error",
                    queue_depth=get_queue_depth(),
                    extra={"last_error": str(e)}
                )
                print(f"Loop error: {e}")
                time.sleep(POLL_INTERVAL_S)

    except KeyboardInterrupt:
        state.write_status(
            runtime_state="halted",
            queue_depth=get_queue_depth(),
            extra={"reason": "keyboard_interrupt"}
        )
        print("\nWorker stopped by signal (KeyboardInterrupt).")


if __name__ == "__main__":
    main()
