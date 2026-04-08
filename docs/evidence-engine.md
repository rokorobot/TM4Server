# TM4Server Evidence Engine (v1.1)

## Overview

TM4Server has evolved from an experiment runner into a **Self-Indexing Evidence Engine**. It doesn't just execute code; it automatically produces, organizes, and publishes the structured proof of Thinking Machine 4's evolutionary progress.

---

## The Core Loop

Every experiment handled by TM4Server follows a mandatory, hardened lifecycle:

1.  **Run**: TM4 core logic executes within a secured subprocess.
2.  **Capture**: All output (`stdout`, `stderr`, `config`) is snapshotted into a unique run directory.
3.  **Summarize**: A machine-readable `run_summary.json` is extracted, providing a stable data contract.
4.  **Report**: A human-readable Markdown report is generated for Git-based review.
5.  **Aggregate**: The global system ledger (`results.csv`) is automatically updated.
6.  **Publish**: All artifacts are committed and pushed to the central repository atomically.

---

## Key Capabilities

### 1. Autonomous Execution
Manages the complexity of TM4 core dependencies, environment variables, and subprocess lifecycle without manual intervention.

### 2. Forensic Evidence Generation
Every execution produces a guaranteed "black box" recording:
- Input manifests
- Final results & SHA hashes
- Full execution logs
- Orchestration event trails

### 3. High-Fidelity Reporting
Transforms raw JSON data into styled Markdown reports suitable for high-level technical review and archival.

### 4. Live System Memory
Maintains a denormalized cross-run ledger that allows for immediate statistical analysis of TTC (Time-to-Convergence), fitness plateaus, and safety violations across hundreds of runs.

---

## Guarantees

- **No Silent Failures**: Every step of the orchestration is logged to an independent `event_log.jsonl`.
- **Absolute Traceability**: Every run is pinned to specific Git SHAs of both the core logic and the server spine.
- **Data Preservation**: Internal orchestrator failures (like Git timeouts) are isolated; they never compromise the primary experiment record.

---

## Architectural Layers

- **Execution Layer** (`runtime.py`): Subprocess isolation and preflight safety.
- **Evidence Layer** (`run_summary.json`): Validated data contract.
- **Reporting Layer** (`experiment_report.py`): Human-readable visualization.
- **Aggregation Layer** (`aggregate_runs.py`): System-wide data consolidation.
- **Publication Layer** (`git_sync.py`): Atomic remote persistence.

---

## Outcome

TM4Server produces **defensible, structured, and analyzable evidence**. It is the bridge between a "black box" autonomy loop and a transparent, governed research platform.
