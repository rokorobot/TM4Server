"""
TM4 Experiment Runtime (Subprocess Integration)
-----------------------------------------------
This module provides a robust wrapper around the real TM4 autonomy loop.
It executes the core TM4 logic as a subprocess, ensuring proper isolation
and capture of logs/results in the TM4Server run directory.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import os
import subprocess
import hashlib

from .utils import utc_now_iso, write_json, append_line
from .config import TM4_AUTONOMY_SCRIPT, TM4_CORE_PATH, TM4_PYTHON_BIN, TM4_AUTONOMY_EXTRA_ARGS


def _safe_git_hash(repo_path: Path) -> str | None:
    """Safely retrieves the git hash of a given repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def run_experiment(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """
    Executes the real TM4 autonomy loop via subprocess.
    Validates environment and paths before launch.
    """
    stdout_log = run_dir / "stdout.log"
    stderr_log = run_dir / "stderr.log"
    tm4_input_path = run_dir / "tm4_input_manifest.json"

    append_line(stdout_log, f"[{utc_now_iso()}] Initiating Phase 2 integration run")
    append_line(stdout_log, f"[{utc_now_iso()}] Experiment ID: {manifest['experiment_id']}")

    # 1. Preflight Validation
    errors = []
    if not TM4_CORE_PATH.exists():
        errors.append(f"TM4_CORE_PATH does not exist: {TM4_CORE_PATH}")
    if not TM4_AUTONOMY_SCRIPT.exists():
        errors.append(f"TM4_AUTONOMY_SCRIPT does not exist: {TM4_AUTONOMY_SCRIPT}")
    
    # Try to resolve python binary (minimal check)
    try:
        subprocess.run([TM4_PYTHON_BIN, "--version"], capture_output=True, check=True)
    except Exception as e:
        errors.append(f"TM4_PYTHON_BIN ({TM4_PYTHON_BIN}) verification failed: {e}")

    if errors:
        for err in errors:
            append_line(stderr_log, f"[{utc_now_iso()}] PREFLIGHT ERROR: {err}")
        
        write_json(run_dir / "status.json", {
            "experiment_id": manifest["experiment_id"],
            "status": "failed",
            "error_type": "preflight_validation",
            "errors": errors,
            "ts_utc": utc_now_iso(),
        })
        raise RuntimeError(f"Preflight validation failed for {manifest['experiment_id']}")

    # 2. Preparation
    tm4_payload = {
        "experiment_id": manifest["experiment_id"],
        "task": manifest.get("task"),
        "model": manifest.get("model"),
        "submitted_at": manifest.get("submitted_at"),
        "tm4server_received_at": utc_now_iso(),
        "parameters": manifest.get("parameters", {}),
    }
    write_json(tm4_input_path, tm4_payload)

    # 3. Environment & Command Setup
    env = os.environ.copy()
    env["TM4SERVER_RUN_DIR"] = str(run_dir)
    env["TM4SERVER_EXPERIMENT_ID"] = manifest["experiment_id"]
    env["TM4SERVER_INPUT_MANIFEST"] = str(tm4_input_path)
    env["TM4_OUTPUT_DIR"] = str(run_dir)

    cmd = [TM4_PYTHON_BIN, str(TM4_AUTONOMY_SCRIPT)] + TM4_AUTONOMY_EXTRA_ARGS

    append_line(stdout_log, f"[{utc_now_iso()}] Launching command: {' '.join(cmd)}")

    # 4. Spawning subprocess
    with stdout_log.open("a", encoding="utf-8") as out, stderr_log.open("a", encoding="utf-8") as err:
        proc = subprocess.run(
            cmd,
            cwd=str(TM4_CORE_PATH),
            env=env,
            stdout=out,
            stderr=err,
            text=True,
            check=False,
        )

    # 5. Post-run metadata & artifacts
    tm4_git_hash = _safe_git_hash(TM4_CORE_PATH)
    
    known_outputs = {}
    for filename in [
        "generation_meta.json",
        "run_manifest.json",
        "results.json",
        "scores.json",
        "config.json",
        "event_log.jsonl",
    ]:
        p = run_dir / filename
        known_outputs[filename] = p.exists()

    summary = {
        "experiment_id": manifest["experiment_id"],
        "task": manifest.get("task"),
        "model": manifest.get("model"),
        "status": "success" if proc.returncode == 0 else "failed",
        "return_code": proc.returncode,
        "completed_at": utc_now_iso(),
        "tm4_core_path": str(TM4_CORE_PATH),
        "tm4_script": str(TM4_AUTONOMY_SCRIPT),
        "tm4_git_hash": tm4_git_hash,
        "known_outputs": known_outputs,
    }

    result_hash = hashlib.sha256(
        json.dumps(summary, sort_keys=True).encode("utf-8")
    ).hexdigest()

    results = {
        "summary": summary,
        "result_hash": result_hash,
    }

    # Writes results.json (required output)
    write_json(run_dir / "results.json", results)

    # Final status.json (required output)
    write_json(run_dir / "status.json", {
        "experiment_id": manifest["experiment_id"],
        "status": results["summary"]["status"],
        "ts_utc": utc_now_iso(),
    })

    if proc.returncode == 0:
        append_line(stdout_log, f"[{utc_now_iso()}] TM4 subprocess completed successfully")
        return results

    append_line(stdout_log, f"[{utc_now_iso()}] TM4 subprocess failed with code {proc.returncode}")
    raise RuntimeError(f"TM4 subprocess failed with exit code {proc.returncode}")
