# TM4 Server Filesystem Layout (Antigravity Deployment)

This document defines the canonical filesystem layout for the TM4 production VPS.

It provides a precise mapping between:
- GitHub repositories
- VPS deployment paths
- Runtime state directories
- Execution artifacts

This is the authoritative reference for all TM4 infrastructure documentation.

---

## 1. Conceptual Separation

TM4 infrastructure is divided into three layers:

| Layer | Description | Location |
|------|------------|---------|
| Source Code | Version-controlled repositories | GitHub |
| Deployment | Cloned repos on VPS | `/opt/` |
| Runtime State | Execution data, queue, artifacts | `/var/lib/tm4/` |
| Logs | Service and system logs | `/var/log/tm4/` |

---

## 2. Repository → VPS Mapping

### TM4Server (Control Plane)
- **GitHub repo**: `rokorobot/TM4Server`
- **Role**: submission, queue management, worker orchestration
- **VPS path**: `/opt/tm4server`

### TM4 Core (Execution Engine)
- **GitHub repo**: `rokorobot/TM4`
- **Role**: autonomy loop, governance, evaluation, experiments
- **VPS path**: `/opt/tm4-core`

---

## 3. Full VPS Filesystem Hierarchy

```text
/                               # root filesystem
├── opt/                        # deployed application code
│   ├── tm4server/              # TM4Server repo (control plane)
│   │   ├── tm4server/
│   │   ├── scripts/
│   │   ├── systemd/
│   │   ├── docs/
│   │   └── venv/               # Python virtual environment
│   │
│   └── tm4-core/               # TM4 core repo (execution engine)
│       ├── mvp/
│       ├── Experiments/
│       ├── Governance/
│       ├── server/
│       ├── tests/
│       └── ...
│
├── var/                        # variable runtime data
│   ├── lib/
│   │   └── tm4/                # TM4 runtime root
│   │       ├── queue/          # job lifecycle management
│   │       │   ├── pending/
│   │       │   ├── running/
│   │       │   ├── completed/
│   │       │   └── failed/
│   │       │
│   │       ├── runs/           # per-run execution outputs
│   │       │   ├── EXP-AUT-SERVER-0001/
│   │       │   ├── EXP-AUT-SERVER-0002/
│   │       │   └── ...
│   │       │
│   │       ├── artifacts/      # shared artifacts (optional)
│   │       └── state/          # runtime/system state (optional)
│   │
│   └── log/
│       └── tm4/                # TM4 service logs
│
├── etc/
│   └── systemd/
│       └── system/
│           └── tm4-runner.service   # worker service definition
│
└── home/
    └── <user>/                # SSH user environment (optional)
```

## 4. Directory Roles

### /opt/tm4server
Deployed TM4Server codebase.
Contains:
- submission CLI (`tm4server.submit_run`)
- queue management logic
- worker/service integration
- deployment scripts
- environment configuration

This is a clone of the TM4Server GitHub repository.

### /opt/tm4-core
Deployed TM4 core engine.
Contains:
- autonomy loop execution
- L4 governance (tournaments)
- mutation and selection logic
- evaluation/scoring
- experiment definitions

This is a clone of the TM4 Core repository.

### /var/lib/tm4
Runtime execution root.
This directory is not version-controlled and exists only on the VPS.
Contains:
- queue state
- run artifacts
- execution logs (per run)
- system state

### /var/log/tm4
Service-level logs for TM4.
Used for:
- debugging
- monitoring
- system diagnostics

## 5. Queue Lifecycle
Queue files are stored under:
`/var/lib/tm4/queue/`

Lifecycle:
`pending` → `running` → `completed` / `failed`

### Example completed job
`/var/lib/tm4/queue/completed/EXP-AUT-SERVER-0002.json`

This file:
- confirms job execution completion
- contains execution metadata
- exists only on the VPS runtime filesystem

## 6. Run Artifacts
Each experiment run produces a dedicated directory:
`/var/lib/tm4/runs/<EXP-ID>/`

### Example
`/var/lib/tm4/runs/EXP-AUT-SERVER-0002/`

Typical contents:
- `config.json`
- `event_log.jsonl`
- `manifest.json`
- `results.json`
- `status.json`
- `stdout.log`
- `stderr.log`
- `tm4_input_manifest.json`

## 7. Systemd Service
Worker execution is managed by:
`/etc/systemd/system/tm4-runner.service`

This service:
- polls the queue
- executes TM4 runs
- ensures continuous autonomous operation

## 8. Local vs VPS Path Mapping

| Function | Local (example) | VPS |
|---|---|---|
| TM4Server repo | `C:\Users\Robert\TM4Server` | `/opt/tm4server` |
| TM4 core repo | `C:\Users\Robert\TM4` | `/opt/tm4-core` |
| Queue | `local_runtime/queue` | `/var/lib/tm4/queue` |
| Runs | `local_runtime/runs` | `/var/lib/tm4/runs` |
| Logs | `local_runtime/logs` | `/var/log/tm4` |

## 9. Documentation Rule
All experiment documentation must clearly specify:
- execution environment (VPS)
- deployment paths (`/opt/...`)
- runtime paths (`/var/lib/...`)

### Recommended phrasing:
> Executed on VPS using deployment path `/opt/tm4server`
> Runtime artifacts written to `/var/lib/tm4/runs/<EXP-ID>/`

## 10. Canonical Deployment (Antigravity)
Current production configuration:
- **TM4Server** → `/opt/tm4server`
- **TM4 Core** → `/opt/tm4-core`
- **Runtime root** → `/var/lib/tm4`
- **Logs** → `/var/log/tm4`

This is the canonical Antigravity deployment layout.
