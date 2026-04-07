"""
TM4 Experiment Runtime (Demo Executor)
--------------------------------------
This file contains the logic for executing a single job.
It is currently structured as a DEMO EXECUTOR but can be swapped
for the real TM4 execution logic later.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib
import json
import time

from .utils import utc_now_iso, write_json, append_line


def run_experiment(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """
    Minimal demo runtime.
    Replace this later with your actual TM4 execution entrypoint.
    """
    stdout_log = run_dir / "stdout.log"

    append_line(stdout_log, f"[{utc_now_iso()}] Starting run")
    append_line(stdout_log, f"[{utc_now_iso()}] Experiment ID: {manifest['experiment_id']}")
    append_line(stdout_log, f"[{utc_now_iso()}] Model: {manifest.get('model', 'unknown')}")
    append_line(stdout_log, f"[{utc_now_iso()}] Task: {manifest.get('task', 'demo_task')}")

    # Simulated work
    time.sleep(2)

    payload = {
        "experiment_id": manifest["experiment_id"],
        "task": manifest.get("task", "demo_task"),
        "model": manifest.get("model", "demo-model"),
        "score": 73,
        "status": "success",
        "completed_at": utc_now_iso(),
    }

    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    results = {
        "summary": payload,
        "result_hash": payload_hash,
    }

    # Writes results.json (required output)
    write_json(run_dir / "results.json", results)

    append_line(stdout_log, f"[{utc_now_iso()}] Run completed successfully")
    return results
