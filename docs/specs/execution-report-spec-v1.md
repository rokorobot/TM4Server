# TM4Server — Execution Report Specification v1

This document formalizes the contract for the TM4Server Execution Report. It defines the structure, data precedence, and evidence health standards required for forensics and auditability.

## 1. Structure (Canonical Skeleton)

The report MUST follow this exact section order:

1.  **Identity**: Identification details of the run and the experiment.
2.  **Execution**: High-level runtime status and timing.
3.  **Intent**: The original request details (workload, requester).
4.  **Artifact Health**: Governance evidence showing the integrity of raw artifacts.
5.  **Outcome**: Terminal results and error context.
6.  **Forensics**: Raw trace evidence (logs).
7.  **Audit**: Metadata about the report generation itself.

## 2. Field Precedence Rules

To ensure resilience against partial or corrupt data, fields are resolved using the following fallback chains:

| Field | Precedence Order | Default |
| :--- | :--- | :--- |
| **Run ID** | `run_summary` → `run_manifest` → `directory_name` | (required) |
| **Status** | `run_summary` → `status.json` → `run_manifest` | `unknown` |
| **Instance ID** | `status.json` → `run_summary` → `run_manifest` | `unknown` |
| **Exp ID** | `run_summary` → `run_manifest` → `status.json` | `unknown` |

## 3. Artifact Health Enums

The `Artifact Health` section MUST report on the state of `run_manifest.json`, `status.json`, and `run_summary.json`.

| State | Semantic Meaning | Optional Detail |
| :--- | :--- | :--- |
| **loaded** | File exists and contains a valid JSON object. | None |
| **missing** | File does not exist in the run directory. | None |
| **not-an-object** | File exists and is valid JSON, but is not a dictionary/object. | Optional explanation |
| **malformed** | File exists but could not be parsed as valid JSON. | Parser error detail |

**Detail Rendering**:
- Detail lines MUST be included if the state is `malformed`.
- Detail lines MAY be included if the state is `not-an-object`.

## 4. Forensics (Log Policy)

- **Section Header**: `## Forensics`
- **Sub-headers**: `### stdout.log tail` and `### stderr.log tail`
- **Tail Length**: Standardized at the last **80 lines**.
- **Rendering**: Logs MUST be enclosed in `text` fenced code blocks.
- **Missing Logs**: If a log file is not found, the block MUST contain: `--- No {name} available ---`.
- **Unreadable Logs**: If a log file is unreadable or errors occur during tailing, the block MUST contain: `--- Error reading {name} ---`.

## 5. Value Rendering Rules

- **Missing Data**: Render as `unknown` (lowercase, plain text).
- **Empty Trace**: Render as `None` (plain text) for outcome error fields.
- **Markdown Purity**: Avoid nesting fenced code blocks inside list items. Outcome errors MUST be placed in a standalone code block under the Outcome header.

## 6. Versioning & Governance

This standard is identified by its **Contract Version**.

- **Contract Version**: `spec-v1`
- **Specification Major Version**: `1`
- **Generator Implementation**: `v1.x`

**Versioning Rules**:
- **Patch** (e.g., 1.x.y): Internal implementation changes with NO report contract impact.
- **Minor** (e.g., 1.y.0): Additive changes to the report contract that do not break downstream parsers.
- **Major** (e.g., y.0.0): Breaking changes to the report contract (e.g., reordering headers, renaming keys, changing precedence).

---
*Governed by TM4 Reporting Standard: spec-v1*
