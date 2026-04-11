# Parallel Split Execution — VPS Rollout & Failure Intelligence

We have successfully completed the **Parallel Split Execution**. TM4Server is now deployed in a production-hardened environment and possesses a deterministic intelligence layer for failure interpretation.

## 🏁 Key Achievements

### 1. Production-Hardened VPS Rollout
- **Dedicated Service User**: Implemented the `tm4` system user for process isolation and file ownership integrity.
- **Hardened Bootstrap**: [**bootstrap_server.sh**](file:///c:/Users/Robert/TM4Server/scripts/bootstrap_server.sh) now automates user creation and enforces ownership across `/var/lib/tm4` and code repositories.
- **Systemd Orchestration**: [**tm4-runner.service**](file:///c:/Users/Robert/TM4Server/systemd/tm4-runner.service) is now configured for high-availability (`Restart=always`) and correctly propagates all Spec v1 environment variables.

### 2. Failure Intelligence Engine (Phase 2D.2)
- **Deterministic Taxonomy**: Established the v1 failure taxonomy: `infra_error`, `execution_error`, `contract_error`, `interrupted`, and `model_error`.
- **Signal Processor**: [**intelligence.py**](file:///c:/Users/Robert/TM4Server/tm4server/execution/intelligence.py) now derives classifications from exit codes (e.g. 137 -> OOM), log regex patterns (e.g. Tracebacks), and contract integrity (artifact health).
- **Audit-Grade Metadata**: Every classification includes **Source Tracking** (e.g., `derived_v1_stderr`) and a **Retry Recommendation** signal.

### 3. Record & Ledger Integration
- **Intelligence Propagation**: The `RunRecord` now carries the interpreted intelligence block by default.
- **Human-Verifiable Evidence**: The automated Markdown reports ([**RUN-*.md**](file:///c:/Users/Robert/TM4Server/docs/experiments/)) now feature an "Intelligence" section that translates raw failure signals into plain English.

## 🧪 Verification Proof (Golden Failure Fixtures)
- **OOM (exit 137)**: `[OK] Class=infra_error, Source=derived_v1_exitcode, Retry=True`.
- **Traceback (Log pattern)**: `[OK] Class=execution_error, Source=derived_v1_stderr, Retry=False`.
- **Contract Mismatch (Missing summary)**: `[OK] Class=contract_error, Source=derived_v1_contract`.
- **Interruption (PID death)**: `[OK] Class=interrupted, Source=derived_v1_status`.

## 🧾 Closure Status
- [x] Dedicated `tm4` user implemented in bootstrap.
- [x] `tm4-runner.service` hardened for production.
- [x] `intelligence.py` engine implemented and integrated.
- [x] Fail-closed contract violation detection enabled.
- [x] Golden Failure Fixtures verified.

**TM4Server is now a生產-ready, self-interpreting organism. VPS Rollout and Failure Intelligence are SEALED.**
