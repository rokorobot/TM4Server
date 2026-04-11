# TM4Server — Run Artifact Specification v1

This document defines the formal contract for TM4Server run artifacts. It is the source of truth for how execution metadata is written, updated, and consumed across the runtime, reporting, dashboard, and audit layers.

This specification governs the three canonical per-run artifacts:

- `run_manifest.json` — intent and launch identity
- `status.json` — live mutable execution state
- `run_summary.json` — terminal outcome and completion evidence

This standard is designed to ensure that downstream systems, including the Execution Report Specification v1, operate on a stable, high-integrity metadata surface.

---

## 1. Contract Identity

- **Contract Version**: `spec-v1`
- **Specification Major Version**: `1`
- **Applies To**: all modern `RUN-*` execution directories
- **Primary Run Root Pattern**: `/var/lib/tm4/runs/<RUN-ID>/`

All artifacts governed by this specification MUST include:

```json
{
  "schema_version": "v1"
}
```

This is required for forward compatibility and future migrations.

## 2. Canonical Run Directory Layout

A conforming modern run directory MUST use this layout:

```text
/var/lib/tm4/runs/<RUN-ID>/
├── run_manifest.json
├── status.json
├── run_summary.json
├── stdout.log
└── stderr.log
```

Notes:
- `run_manifest.json` and `status.json` MUST exist for all active runs.
- `run_summary.json` MUST exist for all terminally completed runs.
- `stdout.log` and `stderr.log` SHOULD exist for all runs, but may be absent in failure or legacy edge cases.
- Legacy directories such as `EXP-*` are outside this specification unless explicitly migrated.

## 3. Artifact Roles

### 3.1 run_manifest.json
**Purpose**: immutable launch intent and identity record.
This artifact captures what was requested, who requested it, and the canonical identity assigned at run creation.

### 3.2 status.json
**Purpose**: mutable live execution state.
This artifact captures what is happening now, where it is running, and when it was last updated.

### 3.3 run_summary.json
**Purpose**: immutable terminal outcome record.
This artifact captures the final result of the run, completion timing, and report-grade provenance.

## 4. Artifact Immutability Rules

### 4.1 run_manifest.json
- MUST be written exactly once at run creation.
- MUST be treated as immutable after creation.
- MUST NOT be overwritten, patched, or mutated after initial write.

### 4.2 status.json
- MUST be mutable during run execution.
- MUST be updated through governed writes only.
- MUST always reflect the latest known live state.
- MUST include a refreshed `updated_at` on every write.

### 4.3 run_summary.json
- MUST be written exactly once when the run reaches a terminal state.
- MUST be treated as immutable after creation.
- MUST NOT be rewritten after terminalization except by an explicit migration tool.

## 5. Write Authority Rules

No component may write governed artifacts directly as ad hoc JSON files. All writes MUST go through the centralized artifact authority layer (e.g., `artifacts.py`).

### 5.1 Allowed logical ownership
| Component | Allowed Logical Responsibility |
| :--- | :--- |
| **launcher / scheduler** | create manifest |
| **runner / worker** | update status, write summary |
| **artifacts.py** | enforce schema, timestamps, atomic writes, and defaults |

### 5.2 Prohibited behavior
- Direct `write_text()` / `json.dump()` writes to governed artifact paths outside the artifact governance layer.
- Maintaining parallel per-run state files such as `runtime_state.json`.
- Mutating `run_manifest.json` after creation.
- Mutating `run_summary.json` after terminal write.

## 6. Atomic Write Requirement

All governed artifact writes MUST be atomic.
**Required write pattern**:
1. Write complete JSON to a temporary file in the same directory.
2. `fsync` or flush as appropriate for implementation.
3. Replace target file atomically.

A non-atomic write to a governed artifact is non-conformant.

## 7. JSON Encoding Rules

All governed artifacts MUST:
- be valid JSON objects at the root.
- be UTF-8 encoded.
- use a top-level JSON object, never a list or scalar.
- avoid duplicate keys, avoid comments, avoid trailing commas.

## 8. Global Field Rules

### 8.1 Timestamp format
All timestamps MUST be **ISO-8601 UTC suffixed with Z**.
Example: `2026-04-11T18:13:25Z`

### 8.2 Identity rules
- `run_id` MUST be the canonical primary identity for the run directory.
- `run_id` MUST match the directory name for conforming `RUN-*` directories.

### 8.3 Instance resolution
`instance_id` is mandatory. It MUST be resolved using this precedence:
1. `TM4_INSTANCE_ID` environment variable
2. `hostname`
3. Explicit runtime configuration override

### 8.4 Status vocabulary
Allowed status values: `queued`, `running`, `success`, `failed`, `interrupted`, `unknown`.

## 9. Lifecycle State Model

`queued` → `running` → (`success` | `failed` | `interrupted`)

- `run_manifest.json` is created at the transition to `queued`.
- `status.json` MUST reflect live progression.
- `run_summary.json` MUST only be written for terminal states (`success`, `failed`, `interrupted`).

## 10. Canonical Artifact Schemas

### 10.1 run_manifest.json
| Field | Type | Description |
| :--- | :--- | :--- |
| **schema_version** | string | MUST be `v1` |
| **run_id** | string | Canonical run identity |
| **exp_id** | string | Experiment lineage identity |
| **workload_type** | string | Logical workload class |
| **requested_by** | string | Request originator |
| **created_at** | string | UTC ISO-8601 Z timestamp |

### 10.2 status.json
| Field | Type | Description |
| :--- | :--- | :--- |
| **schema_version** | string | MUST be `v1` |
| **run_id** | string | Canonical run identity |
| **status** | string | One of allowed status enums |
| **instance_id** | string | Execution node identity |
| **worker_pid** | integer | Process ID |
| **started_at** | string | UTC ISO-8601 Z start timestamp |
| **updated_at** | string | UTC ISO-8601 Z last update timestamp |

### 10.3 run_summary.json
| Field | Type | Description |
| :--- | :--- | :--- |
| **schema_version** | string | MUST be `v1` |
| **run_id** | string | Canonical run identity |
| **status** | string | Terminal status |
| **duration_s** | number | Wall-clock duration |
| **exit_code** | integer | Process exit code |
| **provenance** | object | Mandatory block |
| **provenance.summary_generated_at** | string | UTC ISO-8601 Z timestamp |

## 11. Cross-Artifact Consistency Rules
If present in multiple artifacts, `run_id`, `exp_id`, and `instance_id` MUST agree across all artifacts.

## 12. Deprecation of Legacy Per-Run State Files
`runtime_state.json` is deprecated. New conforming runs MUST NOT create it.

---
*Governed by TM4 Artifact Standard: spec-v1*
