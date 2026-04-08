# TM4Server — Evidence Engine

## What this system is

TM4Server is a self-indexing experimental platform that converts autonomous runs into structured, analyzable evidence. It handles the full lifecycle of an experiment from execution to global publication.

---

## Core Loop

**Run** → **Summarize** → **Report** → **Aggregate** → **Publish**

---

## Where to start

- **Runtime Logic**: [docs/runtime-orchestration.md](file:///c:/Users/Robert/TM4Server/docs/runtime-orchestration.md)
- **Global Ledger**: [docs/ledger.md](file:///c:/Users/Robert/TM4Server/docs/ledger.md)
- **Aggregation Layer**: [docs/aggregation.md](file:///c:/Users/Robert/TM4Server/docs/aggregation.md)
- **Git Sync Module**: [docs/git-sync.md](file:///c:/Users/Robert/TM4Server/docs/git-sync.md)
- **System Overview**: [docs/evidence-engine.md](file:///c:/Users/Robert/TM4Server/docs/evidence-engine.md)

---

## Key Artifacts

The system automatically generates and organizes artifacts in `docs/experiments/`:

- `EXP-*.md`: Individual experiment reports.
- `results.csv`:denormalized global ledger for data science.
- `results.json`: Structured global ledger with diagnostic metadata.

---

## One-line mental model

TM4Server = execution engine + permanent memory + publication layer.
