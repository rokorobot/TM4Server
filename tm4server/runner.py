from __future__ import annotations
from pathlib import Path
import shutil
import traceback

from .config import (
    QUEUED_DIR,
    RUNNING_DIR,
    COMPLETED_DIR,
    FAILED_DIR,
    RUNS_DIR,
    STATUS_FILE,
    CURRENT_RUN_FILE,
)
from .utils import ensure_dir, read_json, write_json, utc_now_iso, append_line
from .runtime import run_experiment


def init_dirs() -> None:
    for d in [QUEUED_DIR, RUNNING_DIR, COMPLETED_DIR, FAILED_DIR, RUNS_DIR]:
        ensure_dir(d)
    write_json(STATUS_FILE, {
        "status": "idle",
        "ts_utc": utc_now_iso(),
        "current_run": None,
    })


def next_manifest_file() -> Path | None:
    if not QUEUED_DIR.exists():
        return None
    files = sorted(QUEUED_DIR.glob("*.json"))
    return files[0] if files else None


def process_one() -> bool:
    manifest_file = next_manifest_file()
    if manifest_file is None:
        write_json(STATUS_FILE, {
            "status": "idle",
            "ts_utc": utc_now_iso(),
            "current_run": None,
        })
        return False

    running_manifest = RUNNING_DIR / manifest_file.name
    shutil.move(str(manifest_file), str(running_manifest))

    manifest = read_json(running_manifest)
    exp_id = manifest["experiment_id"]
    run_dir = RUNS_DIR / exp_id
    ensure_dir(run_dir)

    # Required output files for each run
    write_json(run_dir / "manifest.json", manifest)
    
    write_json(CURRENT_RUN_FILE, {
        "experiment_id": exp_id,
        "ts_utc": utc_now_iso(),
        "manifest_file": str(running_manifest),
    })
    write_json(STATUS_FILE, {
        "status": "running",
        "ts_utc": utc_now_iso(),
        "current_run": exp_id,
    })

    stdout_log = run_dir / "stdout.log"

    try:
        append_line(stdout_log, f"[{utc_now_iso()}] Runner picked job")
        
        # Executes experiment (writes results.json internally)
        results = run_experiment(run_dir, manifest)

        # Final status.json
        write_json(run_dir / "status.json", {
            "experiment_id": exp_id,
            "status": "completed",
            "ts_utc": utc_now_iso(),
        })

        shutil.move(str(running_manifest), str(COMPLETED_DIR / running_manifest.name))

        write_json(STATUS_FILE, {
            "status": "idle",
            "ts_utc": utc_now_iso(),
            "current_run": None,
            "last_completed_run": exp_id,
        })
        return True

    except Exception as e:
        append_line(stdout_log, f"[{utc_now_iso()}] ERROR: {e}")
        append_line(stdout_log, traceback.format_exc())

        write_json(run_dir / "status.json", {
            "experiment_id": exp_id,
            "status": "failed",
            "ts_utc": utc_now_iso(),
            "error": str(e),
        })

        shutil.move(str(running_manifest), str(FAILED_DIR / running_manifest.name))

        write_json(STATUS_FILE, {
            "status": "idle",
            "ts_utc": utc_now_iso(),
            "current_run": None,
            "last_failed_run": exp_id,
        })
        return True
