# TM4 Operator Console v1

## Objective

Define the canonical operator interface for TM4Server.

The Operator Console is a **web-based, server-hosted dashboard** that provides:

- Real-time system observability
- Run and artifact exploration
- Experiment interpretation (classification)
- Cross-run analysis (gradients)
- Governed control actions

This console is the **primary interface for interacting with TM4 in production**.

---

## Architecture Decision

### Canonical Model

- **Frontend:** Web UI served from TM4Server
- **Backend:** TM4Server APIs (source of truth)
- **Access:** Browser (local or remote)
- **Runtime:** VPS / server environment

### Principle

Run logic on the server. View it through the web.

### Local Development Mode

- Same frontend + backend stack
- Runs against local artifacts or dev server
- Must maintain full parity with production APIs

---

## System Layers

| Layer | Description |
|------|------------|
| Facts | Raw runtime state, runs, artifacts |
| Interpretations | Classification, confidence, trends |
| Actions | Operator-triggered control operations |

---

## Navigation Structure

### Tabs (V1)

1. Status
2. Runs
3. Classification
4. Gradients
5. Control

---

## 1. Status Tab

### Purpose

What is the system doing right now?

### Endpoint

GET /api/status

---

## 2. Runs Tab

### Purpose

What has run, what is running, and what artifacts exist?

### Endpoints

GET /api/runs  
GET /api/runs/{exp_id}

---

## 3. Classification Tab

### Purpose

What do completed runs mean?

### Endpoints

GET /api/classification/summary  
GET /api/classification/runs  

POST /api/control/classify  
POST /api/control/classify/{exp_id}

---

## 4. Gradients Tab

### Purpose

What patterns exist across runs?

### Endpoint

GET /api/gradients/summary

---

## 5. Control Tab

### Purpose

What can the operator safely do?

### Endpoints

POST /api/control/pause  
POST /api/control/resume  
POST /api/control/halt  
POST /api/control/aggregate  
POST /api/control/classify  
POST /api/control/refresh  

GET /api/control/state  
GET /api/control/history  

---

## Audit & Governance

All control actions must be logged:

/var/lib/tm4/control_history.jsonl

---

## Security (V1 Minimal)

- Reverse proxy (Nginx / Caddy)
- HTTPS required
- Optional IP allowlist or basic auth

---

## Build Phases

Phase A: Status, Runs, Control  
Phase B: Classification  
Phase C: Gradients  

---

## Design Principles

- Dense, information-first UI
- Clear timestamps everywhere
- Explicit state visibility
- Conservative control interactions

---

## Strategic Positioning

The Operator Console is a:

Governed Experiment Control Surface
