# TM4Server Git Synchronization (v1.1)

## Overview

The Git sync module enables automated, best-effort publication of experiment artifacts to a remote repository. It is designed to ensure that the remote global ledger and individual experiment reports are committed atomically.

---

## Purpose

- **Persistence**: Ensures experiment results are stored in version control, not just on the local server.
- **Auditability**: Enables remote stakeholders to track experiment history without server access.
- **Ledger Consistency**: Guarantees that the global summary files and individual reports are published together.

---

## Supported Artifacts

The system automatically targets the following files for synchronization:
- **Experiment Report**: `EXP-*.md`
- **Global CSV Ledger**: `results.csv`
- **Global JSON Ledger**: `results.json`

---

## Functionality

The core function `sync_artifacts_to_git(repo_path, file_paths, commit_msg, auto_push)` performs the following steps:

### 1. Symlink-Safe Filtering
- Uses `Path.resolve()` to normalize all paths.
- Verifies that each target artifact actually exists and resides within the repository tree.
- Prevents accidental staging of system files or external data.

### 2. Change Detection
- Executes `git status --porcelain -- <file>` for each target.
- If no material changes are detected across all files, the process stops with a `NO_CHANGE` status. This prevents empty, noisy commits.

### 3. Atomic Staging & Commitment
- Matches all target files in a single `git add` command.
- Commits all changes under a single message (e.g., `Experiment update: EXP-AUT-0003`).

### 4. Optional Push
- If `TM4_AUTO_PUSH_REPORTS=1` is set in `.env`, the system executes `git push`.
- Errors during pushing are captured and logged but do **not** revert the local commit.

---

## Return Schema

The function returns a dictionary providing high-fidelity diagnostic information:

```json
{
  "ok": true,
  "stage": "push",
  "changed": true,
  "message": "Pushed 3 artifacts",
  "stderr": ""
}
```

### Potential Stages:
- `precheck`: Initial path or repo existence validation.
- `check`: Change detection phase.
- `add`: Staging phase.
- `commit`: Identity/Commit phase.
- `push`: Remote transmission phase.

---

## Design Principles

- **Atomic**: Multiple artifacts synced in one transaction.
- **Noised-Reduced**: Only commits when files actually change.
- **Observable**: Detailed stage-specific failure reporting.
- **Safe**: Resolves symlinks and enforces repo boundaries.

---

## Role in TM4

This module bridges the gap between **local execution truth** and **globally visible records**. It is the final step in the "Autonomous Evidence Engine" lifecycle.
