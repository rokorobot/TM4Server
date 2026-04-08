# TM4Server Cross-Run Aggregation Layer (v1.0)

## Overview

The aggregation layer transforms individual experiment outputs (`run_summary.json`) into a unified, machine-readable ledger. It enables system-level analysis across all experiments.

---

## Purpose

Without aggregation:
- Each run is isolated
- No global insight is possible

With aggregation:
- All runs are indexed
- Metrics become comparable
- System behavior becomes analyzable

---

## Inputs

- Source: `/var/lib/tm4/runs/<EXP-ID>/run_summary.json`
- Format: validated JSON schema

---

## Outputs

### CSV Ledger
`docs/experiments/results.csv`
Flat, denormalized structure for:
- Excel
- Pandas
- SQL import

### JSON Ledger
`docs/experiments/results.json`
Structured format including:
- rows
- failures
- schema metadata

---

## Schema

Key fields extracted:
- `exp_id`
- `status`
- `validation_status`
- `duration_s`
- `instance_id`
- `execution_mode`
- `tm4_version`
- `tm4server_version`
- `generations`
- `fitness_max` / `mean` / `min`
- `ttc` (Time to Convergence)
- `violations`
- `checkpoints`
- `commits`

---

## Behavior

- Scans all run directories in a single pass.
- Validates each summary against the expected schema.
- Skips malformed or partial entries without stopping the batch.
- Sorts output deterministically by `experiment_id`.

---

## Failure Handling

- **Invalid JSON**: Logged in the output JSON `failures` block.
- **Missing Keys**: Handled gracefully (defaults to `None` or `0`).
- **Resilience**: A single corrupt run folder cannot break the global ledger.

---

## CLI Usage

```bash
python -m tm4server.cli.aggregate_runs
```

Optional arguments:
- `--runs-root /custom/path`
- `--output-csv custom.csv`
- `--no-json`

---

## Design Principles

- **Deterministic**: Same input always produces same ledger.
- **Non-blocking**: Designed to run after every experiment in the background.
- **Portable**: Outputs are standard CSV/JSON.
- **Analytics-first**: Fields are chosen for immediate graphing.
