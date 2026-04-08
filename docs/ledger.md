# TM4Server Global Experiment Ledger (v1.1)

## Overview

The global ledger is the central analytical dataset of TM4Server. It denormalizes and aggregates every experiment conducted on the server into a single, query-ready format.

---

## Artifact Locations

The ledger is regenerated after every run in the documentation root:
- **CSV Format**: `docs/experiments/results.csv`
- **JSON Format**: `docs/experiments/results.json`

---

## Ledger Properties

- **Evergreen**: Automatically refreshed by the orchestrator at the end of every experiment lifecycle.
- **Ordered**: Entries are sorted deterministically by `experiment_id`.
- **Resilient**: Skips corrupt or partial run data to maintain the integrity of the total dataset.
- **Auditable**: Typically synchronized to Git alongside the visual Markdown reports.

---

## Row Structure

Each row in the ledger represents a snapshot of a completed experiment. Key dimensions include:

### 1. Identity & Context
- `exp_id`: Unique identifier (e.g., `EXP-AUT-0003`).
- `instance_id`: Target machine or environment ID.
- `execution_mode`: Context of the run (e.g., `vps`, `local`).

### 2. Operational Metrics
- `status`: High-level outcome (`success` / `failed`).
- `validation_status`: Logic-tier result (`passed` / `failed`).
- `duration_s`: Total execution time in seconds.

### 3. Version Traceability
- `tm4_version`: 40-character Git SHA of the core logic.
- `tm4server_version`: 40-character Git SHA of the execution spine.

### 4. Evolutionary Performance
- `generations`: Number of iterations performed.
- `fitness_max` / `fitness_mean`: Core quality metrics.
- `ttc`: Time-to-Convergence (if applicable).
- `violations`: Safety or constraint violation count.
- `commits`: Number of Git commits captured.

---

## Common Use Cases

### For Operators
- **Quick Status Audit**: Check `results.csv` to find which experiments failed without opening individual folders.
- **Performance Triage**: Sort by `duration_s` or `fitness_max` to find outliers.

### For Analysts
- **Pandas Integration**: Load `results.csv` directly for statistical analysis and visualization.
- **Trend Detection**: Compare `fitness_max` trends over different `tm4_version` hashes to verify improvements.

---

## Role in System

The ledger acts as the **Global Memory** of TM4Server. It transforms a collection of thousands of individual files into a single, cohesive research database.
