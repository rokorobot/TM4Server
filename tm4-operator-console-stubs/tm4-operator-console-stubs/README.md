# TM4 Operator Console Stubs

This bundle includes repo-ready starter files aligned to `docs/operator-console-v1.md`.

## Files

- `server/api/operator_console.py`
  - FastAPI route stubs for:
    - `/api/status`
    - `/api/runs`
    - `/api/runs/{exp_id}`
    - `/api/classification/*`
    - `/api/gradients/summary`
    - `/api/control/*`

- `web/components/TM4OperatorConsoleLayout.tsx`
  - React + Tailwind operator console layout
  - Includes tabs for:
    - Status
    - Runs
    - Classification
    - Gradients
    - Control

## Intended next integration

1. Mount `router` into your existing FastAPI app.
2. Replace mock payloads with adapters over:
   - `/var/lib/tm4`
   - run summaries
   - classification outputs
   - control history
3. Connect the React component to real fetch calls.
4. Add auth/reverse proxy protection before exposing remotely.
