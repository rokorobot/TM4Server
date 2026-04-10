# TM4 Launch Path & Runs Explorer - Technical Specification

This document defines the high-integrity workload management and observability system implemented in TM4Server v1.1-runs-explorer.

## 🏛️ Architectural Principles

1.  **FileSystem as Index**: The `runs/` directory is the single source of truth for both current workload and historical evidence. The specialized `queue/` subfolders are secondary/legacy.
2.  **Explicit State Tracking**: Every run directory contains a `runtime_state.json` file. This prevents ambiguity between "queued", "running", and "terminal" states.
3.  **Atomic ID Allocation**: Experiment ID (`EXP_ID`) generation and directory creation are synchronized using a filesystem lock file (`runs/.lock`) to prevent race conditions during concurrent launch requests.
4.  **Terminal Evidence**: A run is formally considered terminal only when `run_summary.json` exists.

## 📂 Run Directory Contract (`runs/<EXP_ID>/`)

| File | Type | Source | Description |
| :--- | :--- | :--- | :--- |
| `run_manifest.json` | Immutable | API (Launch) | The immutable launch intent snapshot (Contract). |
| `runtime_state.json` | Mutable | API / Runner | The live execution state and lifecycle timestamps. |
| `stdout.log` | Stream | Runner / Subprocess | Sequential capture of execution output. |
| `results.json` | Static | Runner / TM4 Core | Raw technical metrics from the autonomy loop. |
| `run_summary.json` | Terminal | Runner | High-level evidence artifact marking the end of the run. |

## 🔄 State Transition Model

1.  **QUEUED**: `runtime_state.status = "queued"`. Directory and manifest exist.
2.  **RUNNING**: `runtime_state.status = "running"`. Runner has picked the job and updated the PID.
3.  **COMPLETED / FAILED**: `run_summary.json` exists. `runtime_state.status` is updated to a terminal value.
4.  **INTERRUPTED**: Worker startup detected a `running` status but a dead/missing worker PID.

## 🛠️ Operator Semantics

- **LAUNCH [Button]**: Always permitted. Creates a new queued run directory.
- **RUN [Mode]**: Execution is permitted. The Runner will consume `queued` runs in FIFO order (based on `created_at` in the manifest).
- **PAUSE [Mode]**: Prevents the Runner from starting the *next* queued run. The current active run is allowed to finish.
- **HALT [Mode]**: Same effect as PAUSE for the Runner loop. Used to indicate a stronger intent to stop system activity.

## 🚨 Crash Recovery

On startup, the TM4 Worker performs a **Recovery Scan**:
- Iterates through all directories in `runs/`.
- Identifies any directory with `status: "running"` in `runtime_state.json`.
- Checks if the recorded `worker_pid` is still alive.
- If dead AND `run_summary.json` is missing, marks the run as `interrupted` with a timestamp and failure reason.
## 🔍 Runs Explorer (v1.1)

The Runs Explorer provides first-class observability into the `runs/` directory artifacts.

### 1. Normalized Indexing
The system scans `runs/` and derives a normalized status for each row using the following precedence:
- **`failed`**: `run_summary.json` exists and reports failure.
- **`completed`**: `run_summary.json` exists and reports success.
- **`running`**: `runtime_state.json` reports running.
- **`interrupted`**: `runtime_state.json` reports interrupted (manual/crash).
- **`queued`**: `runtime_state.json` reports queued.

### 2. Detail Inspection
The explorer allows interactive drill-down into a specific run ID, fetching three core artifacts:
- **Manifest**: To verify the launch intent (task, model, source).
- **Runtime State**: To track lifecycle (PID, timestamps).
- **Summary**: To inspect terminal evidence (errors, metrics).

### 3. API Surface
- `GET /api/runs`: Normalized list with status and basic metadata.
- `GET /api/runs/{exp_id}`: Side-by-side JSON payloads for forensic analysis.
