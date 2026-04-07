# TM4Server

Minimal experiment runner and queue for TM4.

## Overview
TM4Server provides a thin, path-independent backbone for experiment execution. It handles a simple JSON-based queue and manages dedicated run folders for each experiment.

## Local Development
1. **Bootstrap**: Run `bash scripts/bootstrap_local.sh` to initialize the local runtime structure.
2. **Submit a job**: `python -m tm4server.submit_run --exp-id EXP-AUT-0001`
3. **Run worker**: `python -m tm4server.worker` (or use `bash scripts/start_local_worker.sh`)

## Project Structure
- `tm4server/`: Core Python package.
- `scripts/`: Operational helpers (bootstrap, checks).
- `docs/`: Technical documentation.
- `local_runtime/`: Local simulation of the server state (gitignored).

## Deployment
See `docs/deployment.md` for instructions on migrating to a VPS using systemd.
