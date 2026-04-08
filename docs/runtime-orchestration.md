# TM4Server Runtime Orchestration (v1.1)

## Overview

The runtime module is the execution spine of TM4Server. It manages the full lifecycle of an experiment from job acquisition to artifact publication.

---

## Execution Flow

```text
1. Preflight validation (Repo/Script/Python checks)
2. Subprocess execution (Launch TM4 core autonomy loop)
3. Artifact capture (Capture logs, results, and metadata)
4. run_summary.json generation (Unified experiment record)
5. Markdown report generation (Human-readable summaries)
6. Ledger aggregation (Cross-run data consolidation)
7. Git synchronization (Atomic publication of reports + ledgers)
```

---

## Key Guarantees

### 1. Truthful Execution Status
- Experiment success/failure is determined **ONLY** by the subprocess return code.
- Reporting or synchronization failures are logged as side-effects and **cannot** override the experiment outcome.

### 2. Non-Blocking Post-Run Phase
- All post-run steps are wrapped in isolated `try/except` blocks:
    - Summary extraction
    - Report generation
    - Global aggregation
    - Git synchronization
- Failure in one step (e.g., a Git push timeout) does **NOT** affect the integrity of other saved artifacts.

### 3. Deterministic Artifact Set
Each run directory is guaranteed to contain:
- `config.json`: Snapshot of paths/env used.
- `tm4_input_manifest.json`: Precise inputs given to TM4.
- `results.json`: Summary and hash of the run.
- `status.json`: High-level success/fail indicator.
- `stdout.log` / `stderr.log`: Full tool output.
- `event_log.jsonl`: Machine-readable audit trail of the orchestrator's actions.
- `run_summary.json`: Validated dataset for aggregation.

---

## Event Logging

All orchestration events are recorded in `event_log.jsonl` with UTC timestamps:
- `job_picked`
- `subprocess_started`
- `subprocess_completed`
- `run_summary_written`
- `experiment_report_written`
- `aggregate_updated`
- `git_sync_completed` (includes `stage` and `stderr` on failure)

---

## Design Principles

- **Isolation**: Experiments run in clean subprocesses with explicit environment propagation.
- **Full Audit Trail**: Every decision made by the orchestrator is logged.
- **Idempotent Artifacts**: Reports and summaries can be regenerated safely.
- **Production-Safe**: Handles partial system availability (e.g., offline Git remote) without losing data.

---

## Role in System

This module ensures that **Every Run becomes permanent, auditable, and analyzable evidence.** It is the transition point where raw execution becomes governed research.
