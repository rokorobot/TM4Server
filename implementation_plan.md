# Implementation Plan - TM4Server State Layer (Local Repo Only)

Add a minimal runtime state layer to the local TM4Server repo to support future observability and control. This includes status tracking, control mode management (run, pause, halt), and an audit log of control actions.

## ✅ User Approval Received

The plan is approved with the following production-safe refinements:
- **Atomic Writes**: `status.json` and `control.json` writes must use a temp-file-and-replace strategy to prevent corruption.
- **Heartbeat Consistency**: The worker must explicitly update `status.json` during the `pause` loop to ensure the heartbeat remains active.
- **Strict Validation**: Support only `run`, `pause`, and `halt` modes with robust fallback to `run`.

## Proposed Changes

### `tm4server` (Core Package)

#### [NEW] [state.py](file:///c:/Users/Robert/TM4Server/tm4server/state.py)
Implementation of the `StateManager` class.
- Uses `TM4_RUNTIME_ROOT` from config.
- Manages `status.json`, `control.json`, and `control_history.jsonl` under `TM4_RUNTIME_ROOT/state/`.
- **Atomic Writes**: Implements `atomic_write_json` (write to `.tmp` then rename).
- **Robustness**: Fault-tolerant reads for `control.json` (defaults to `run` if missing/malformed). Overwrites malformed files with defaults on next write.
- **Defaults**: Ensures `control.json` exists on startup.

#### [MODIFY] [config.py](file:///c:/Users/Robert/TM4Server/tm4server/config.py)
Add constants for the state layer:
- `TM4_RUNTIME_ROOT` (aliased to `TM4_BASE`)
- `TM4_STATE_ROOT`, `TM4_STATUS_FILE`, `TM4_CONTROL_FILE`, `TM4_CONTROL_HISTORY_FILE`
- `TM4SERVER_REPO_ROOT`, `TM4CORE_REPO_ROOT`

#### [MODIFY] [worker.py](file:///c:/Users/Robert/TM4Server/tm4server/worker.py)
Integrate `StateManager` into the loop:
- Loop checks `control.json` mode before each cycle.
- **Pause Mode**: Sleep for `POLL_INTERVAL_S` and call `state.write_status()` to maintain heartbeat.
- **Halt Mode**: Write `halted` status and exit cleanly.

#### [MODIFY] [runner.py](file:///c:/Users/Robert/TM4Server/tm4server/runner.py)
- Remove all `write_json(STATUS_FILE, ...)` calls.
- `init_dirs` only creates directories.
- `process_one` returns status/progress but does not write to the global `status.json`.

---

### `scripts` (Utilities)

#### [NEW] [set_control_mode.py](file:///c:/Users/Robert/TM4Server/scripts/set_control_mode.py)
A CLI helper to update `control.json` and the history log via `StateManager`.
- Strict input validation: `run`, `pause`, `halt` only.
- Clear error messages and exit codes.

## Verification Plan

### Automated / Scratch Verification
- Test `StateManager` atomic writes and fallback logic.
- Verify `set_control_mode.py` validation.
- **Multi-cycle Test**: Switch `pause -> run -> pause` repeatedly to verify persistence and timing.

### Manual Verification
- Verify heartbeat updates while paused (check `ts_utc` in `status.json`).
- Ensure `halt` stops the `tm4-runner` service cleanly (if tested in service mode) or the CLI process.


