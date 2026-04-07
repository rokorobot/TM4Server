# TM4Server

Experiment runner and queue backbone for TM4 (Thinking Machine 4).

## What It Does

TM4Server is a thin, path-independent execution spine that:
- Manages a file-based job queue (`queued → running → completed/failed`)
- Creates isolated run folders per experiment with standardized outputs
- Invokes the real TM4 autonomy loop as a controlled subprocess
- Captures stdout, stderr, git hashes, duration, and event trails per run
- Runs identically locally (`./local_runtime/`) and on the VPS (`/var/lib/tm4/`)

## Quick Start (Local)

```bash
# 1. Bootstrap the local runtime structure
bash scripts/bootstrap_local.sh

# 2. Submit a job
python -m tm4server.submit_run --exp-id EXP-AUT-0001 --task sanity_check --model qwen2.5:3b

# 3. Process it
python -m tm4server.worker
```

## Output Files per Run

Each run in `local_runtime/runs/<EXP-ID>/`:

| File | Description |
|---|---|
| `manifest.json` | Original job manifest |
| `tm4_input_manifest.json` | Sanitised input handed to TM4 core |
| `config.json` | Resolved config snapshot (paths, git hashes, params) |
| `stdout.log` | Combined execution log |
| `stderr.log` | TM4 core subprocess stderr |
| `event_log.jsonl` | TM4Server event trail |
| `results.json` | Summary with duration, git hashes, artifact inventory |
| `status.json` | Final status with `preflight_status` and timing |

## Project Structure

```text
TM4Server/
├── tm4server/          # Core Python package
│   ├── config.py       # Environment-driven path config
│   ├── utils.py        # JSON, logging, timestamps
│   ├── runtime.py      # Subprocess wrapper around TM4 core
│   ├── runner.py       # Queue state machine
│   ├── worker.py       # Poll loop entrypoint
│   └── submit_run.py   # CLI job submission
├── scripts/
│   ├── bootstrap_local.sh    # Initialize local_runtime/
│   ├── bootstrap_server.sh   # Full VPS setup (idempotent)
│   ├── deploy_server.sh      # Pull + restart service
│   ├── start_local_worker.sh # Run worker locally
│   └── check_runtime.sh      # Show queue state
├── docs/
│   ├── deployment.md         # VPS deployment guide
│   ├── operator-workflow.md  # Day-to-day operations
│   └── runtime-structure.md  # Directory layout reference
├── systemd/
│   └── tm4-runner.service    # Systemd unit template
├── examples/
│   └── manifests/            # Example experiment manifests
└── local_runtime/            # Gitignored local runtime state
```

## Key Design Principle

The runtime path is controlled entirely by `TM4_BASE_PATH`:

| Environment | `TM4_BASE_PATH` |
|---|---|
| Local dev | `./local_runtime` (default) |
| VPS | `/var/lib/tm4` |

Same codebase. Different environment variable.

## VPS Deployment

See [docs/deployment.md](docs/deployment.md) for full instructions.

Quick version:
```bash
bash scripts/bootstrap_server.sh
sudo systemctl enable tm4-runner
sudo systemctl start tm4-runner
```
