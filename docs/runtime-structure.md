# TM4 Runtime Structure

The TM4Server uses a standardized directory structure for managing experiments and persistent state.

## Base Path
By default, the runtime lives in:
- Local: `./local_runtime/`
- Server: `/var/lib/tm4/`

## Directory Tree
```text
/var/lib/tm4/
├── queue/               # Job queue management
│   ├── queued/          # Incoming manifests (.json)
│   ├── running/         # Currently active job
│   ├── completed/       # Finished jobs (manifests moved here)
│   └── failed/          # Jobs that crashed (manifests moved here)
├── runs/                # Dedicated run folders
│   └── EXP-AUT-XXXX/    # One folder per experiment ID
│       ├── manifest.json
│       ├── status.json
│       ├── stdout.log
│       └── results.json
├── state/               # Global server state
│   ├── status.json      # Current idle/running status
│   └── current_run.json # Details about the active experiment
├── artifacts/           # Bulk data, model weights, large outputs
├── logs/                # System-level logs
└── snapshots/           # Point-in-time state backups
```

## State Definitions
- **Idle**: No jobs in queue.
- **Running**: One job is being processed.
- **Crashed/Failed**: Job stopped unexpectedly, error captured in `stdout.log`.
