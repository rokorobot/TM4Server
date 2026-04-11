# EXP-SERVER-UI-0002 — Operator Console Surface Reality Map

## Objective
Identify which UI surfaces are fully implemented, partially implemented, or currently placeholders/not yet connected to server APIs. This maps the "Truth Gap" between the advanced backend and the nascent frontend.

## Surfaces

### 1. Status Surface
- **Status**: **FULL**
- **Endpoint**: `/api/status`
- **Notes**: Live API-backed, polling correctly. Shows accurate counts and instance identity.

### 2. Control Surface
- **Status**: **FULL**
- **Endpoint**: `/api/control/*`
- **Notes**: `RUN`, `PAUSE`, and `HALT` logic is fully wired and verified on the server-side.

### 3. Audit / History Surface
- **Status**: **PARTIAL**
- **Endpoint**: `/api/control/history`
- **Notes**: Rendering logic exists and shows previous actions. Requires deeper validation of timestamp ordering and source attribution under load.

### 4. Runs Explorer Surface
- **Status**: **NOT IMPLEMENTED / BROKEN**
- **Endpoint**: `/api/runs`
- **Notes**: UI structure may be present in `App.tsx`, but rendering is broken or inconsistent. Server returns 404 for this route on current VPS deployment or UI is not correctly calling it.

### 5. Scientific Analysis (Gradients / Pareto)
- **Status**: **NOT IMPLEMENTED**
- **Endpoint**: `/api/analysis/*`
- **Notes**: Renders as placeholders or fragments. Not yet wired to the research-grade logic in the backend.

### 6. Governance Bridge
- **Status**: **NOT IMPLEMENTED**
- **Endpoint**: `/api/analysis/decisions`
- **Notes**: UI structure exists but is not functional. Displays mock data or broken layouts.

---

## Conclusion (Phase 1B)
The **Backend** is currently at a significantly higher maturity level than the **UI**. The system is controllable and observable via raw API, but the dashboard is still under construction for anything beyond basic control-plane operations.

**Next Action**: Move to **Phase 2: Runtime Workload Validation** to prove the core execution spine.
