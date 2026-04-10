# TM4 Control Plane Semantics

## Purpose
Define the meaning of control-plane actions and runtime states in TM4Server to ensure clear separation between execution permission and workload creation.

## Execution Mode vs. Workload Creation

### Control Actions
The control plane manages the *permission to execute*, not the workload itself.
- `run` — execution is permitted; the worker should process the queue if work is present.
- `pause` — execution is temporarily suspended; the worker should finish the current task but not start a new one (or pause at next safe checkpoint).
- `halt` — execution is stopped; the worker should stop immediately/gracefully and stay stopped.

These actions modify **control state** only. They do **not** create or launch a new experiment.

## Core Invariant
Execution occurs **if and only if**:
- `control.mode = "run"`
- AND `queue_depth > 0`

Otherwise, the system remains in `idle`. This invariant must hold across all future implementations and is the primary logic for the Runner bootstrap.

### Runtime Interpretation
The worker/daemon may remain `idle` while the control mode is `run` if there is no queued work.

**Example State:**
- `control.mode = "run"`
- `queue_depth = 0`
- `runtime_state = "idle"`

This is the expected behavior. "Run" does not imply "Worker is currently busy"; it implies "Worker has permission to be busy."

## Current v1 Behavior
The Operator Console v1 is strictly an observer and execution-permission controller. It supports:
- **Observing** runtime state (State, Exp ID, Queue Depth).
- **Changing** control mode (Run/Pause/Halt).
- **Viewing** audit history (Who changed what and when).
- **Viewing** system identity (Versions and Roots).

The Operator Console v1 does **not** yet support:
- Launching a new experiment.
- Queueing a new run.
- Selecting or editing run configurations.

## Responsibility Boundary

### Control Plane (API + UI)
- **Writes** control state (`control.json`).
- **Does not** execute workloads or manage the queue.
- **Observes** status for operator display.

### Worker / Runner
- **Reads** control state (`control.json`).
- **Consumes** the workload queue.
- **Executes** experiments.
- **Writes** runtime status (`status.json`).

## State Flow (Simplified)
`UI (Operator Console) → API (FastAPI) → control.json → Runner Loop → status.json → API → UI`

## Future Roadmap: Workload Management
A separate lifecycle path (Launch) will be introduced to handle workload creation.
- **Example:** `POST /api/runs/launch`

This "Launch" path will create/queue the workload, while the existing "Run/Pause/Halt" controls will remain strictly execution-state permissions. This separation ensures that an operator can set the system to "Run" mode *before* any experiments are even planned, or "Halt" the system while keeping a full queue intact for later.
