# EXP-SERVER-UI-0001 — Operator Console Live Validation

## Objective
Validate the deployed TM4 Operator Console and control-plane behavior on the live VPS.

## Environment
- Host: tm4-core-1
- IP: 91.98.233.160
- TM4Server path: /opt/tm4server
- Service: tm4-api.service
- Deployed commit: 9d128a0
- TM4 core version: e668108

## Validation Performed
- Confirmed tm4-api.service is active and stable
- Confirmed deployed git commit matches runtime-reported version
- Confirmed `/api/status` returns live structured state
- Confirmed Operator Dashboard loads and polls live API
- Confirmed RUN transitions runtime_state from `paused` to `idle`
- Confirmed PAUSE transitions runtime_state from `idle` to `paused`

## Result
PASS — live Operator Console and control-plane state transitions are functioning on the VPS.

## Remaining Validation
- Validate real workload execution
- Confirm `idle` → `running` under active experiment
- Confirm HALT behavior during live work
