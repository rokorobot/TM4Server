"""
TM4 Experiment Runtime (Subprocess Integration)
-----------------------------------------------
This module provides a robust wrapper around the real TM4 autonomy loop.
It executes the core TM4 logic as a subprocess, ensuring proper isolation
and capture of logs/results in the TM4Server run directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .aggregate_runs import RunAggregator
from .config import (
    RUNS_DIR,
    TM4_AUTO_PUSH_REPORTS,
    TM4_AUTONOMY_EXTRA_ARGS,
    TM4_AUTONOMY_SCRIPT,
    TM4_CORE_PATH,
    TM4_DOCS_ROOT,
    TM4_PYTHON_BIN,
)
from .experiment_report import ExperimentReportGenerator
from .git_sync import sync_report_to_git
from .run_summary import RunSummaryExtractor
from .utils import append_line, utc_now_iso, write_json


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


def _emit_event(event_log: Path, event: str, **kwargs: Any) -> None:
    """Appends a single TM4Server event to the run's event_log.jsonl."""
    entry = {"ts_utc": utc_now_iso(), "event": event, **kwargs}
    append_line(event_log, json.dumps(entry, ensure_ascii=False))


def run_experiment(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """
    Executes the real TM4 autonomy loop via subprocess.
    Validates environment and paths before launch.
    """
    stdout_log = run_dir / "stdout.log"
    stderr_log = run_dir / "stderr.log"
    event_log = run_dir / "event_log.jsonl"
    tm4_input_path = run_dir / "tm4_input_manifest.json"
    exp_id = manifest["experiment_id"]

    started_at = utc_now_iso()
    started_ts = time.monotonic()

    append_line(stdout_log, f"[{started_at}] Initiating run")
    append_line(stdout_log, f"[{started_at}] Experiment ID: {exp_id}")

    _emit_event(event_log, "job_picked", experiment_id=exp_id)

    try:
        # 1. Preflight Validation
        errors = []
        if not TM4_CORE_PATH.exists():
            errors.append(f"TM4_CORE_PATH does not exist: {TM4_CORE_PATH}")
        if not TM4_AUTONOMY_SCRIPT.exists():
            errors.append(f"TM4_AUTONOMY_SCRIPT does not exist: {TM4_AUTONOMY_SCRIPT}")
        try:
            subprocess.run([TM4_PYTHON_BIN, "--version"], capture_output=True, check=True)
        except Exception as e:
            errors.append(f"TM4_PYTHON_BIN ({TM4_PYTHON_BIN}) verification failed: {e}")

        if errors:
            for err in errors:
                append_line(stderr_log, f"[{utc_now_iso()}] PREFLIGHT ERROR: {err}")
            _emit_event(event_log, "preflight_failed", errors=errors)
            write_json(run_dir / "status.json", {
                "experiment_id": exp_id,
                "status": "failed",
                "preflight_status": "failed",
                "preflight_errors": errors,
                "ts_utc": utc_now_iso(),
            })
            raise RuntimeError(f"Preflight validation failed for {exp_id}")

        _emit_event(event_log, "preflight_passed")

        # 2. Capture git hashes
        tm4_git_hash = _safe_git_hash(TM4_CORE_PATH)
        tm4server_git_hash = _safe_git_hash(Path(__file__).parent.parent)

        # 3. Write config.json (resolved run configuration snapshot)
        config_snapshot = {
            "experiment_id": exp_id,
            "task": manifest.get("task"),
            "model": manifest.get("model"),
            "parameters": manifest.get("parameters", {}),
            "tm4_core_path": str(TM4_CORE_PATH),
            "tm4_script": str(TM4_AUTONOMY_SCRIPT),
            "tm4_python_bin": TM4_PYTHON_BIN,
            "tm4_extra_args": TM4_AUTONOMY_EXTRA_ARGS,
            "tm4_git_hash": tm4_git_hash,
            "tm4server_git_hash": tm4server_git_hash,
            "submitted_at": manifest.get("submitted_at"),
            "started_at": started_at,
        }
        write_json(run_dir / "config.json", config_snapshot)

        # 4. Write tm4_input_manifest.json
        tm4_payload = {
            "experiment_id": exp_id,
            "task": manifest.get("task"),
            "model": manifest.get("model"),
            "submitted_at": manifest.get("submitted_at"),
            "tm4server_received_at": started_at,
            "parameters": manifest.get("parameters", {}),
        }
        write_json(tm4_input_path, tm4_payload)

        # 5. Environment & Command Setup
        env = os.environ.copy()
        env["TM4SERVER_RUN_DIR"] = str(run_dir)
        env["TM4SERVER_EXPERIMENT_ID"] = exp_id
        env["TM4SERVER_INPUT_MANIFEST"] = str(tm4_input_path)
        env["TM4_OUTPUT_DIR"] = str(run_dir)

        cmd = [TM4_PYTHON_BIN, str(TM4_AUTONOMY_SCRIPT)] + TM4_AUTONOMY_EXTRA_ARGS
        append_line(stdout_log, f"[{utc_now_iso()}] Launching command: {' '.join(cmd)}")

        _emit_event(event_log, "subprocess_started", command=cmd[0], script=str(TM4_AUTONOMY_SCRIPT))

        # 6. Spawn subprocess
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

        completed_at = utc_now_iso()
        duration_s = round(time.monotonic() - started_ts, 2)

        _emit_event(
            event_log, "subprocess_completed",
            return_code=proc.returncode,
            duration_s=duration_s,
        )

        # 7. Native artifact detection (read-only)
        known_outputs = {}
        for filename in [
            "generation_meta.json",
            "run_manifest.json",
            "scores.json",
            "event_log.jsonl",  # TM4 core's own event log if it exists
        ]:
            known_outputs[filename] = (run_dir / filename).exists()

        run_status = "success" if proc.returncode == 0 else "failed"

        # 8. Write results.json
        summary = {
            "experiment_id": exp_id,
            "task": manifest.get("task"),
            "model": manifest.get("model"),
            "status": run_status,
            "return_code": proc.returncode,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_s": duration_s,
            "tm4_git_hash": tm4_git_hash,
            "tm4server_git_hash": tm4server_git_hash,
            "known_outputs": known_outputs,
        }

        result_hash = hashlib.sha256(
            json.dumps(summary, sort_keys=True).encode("utf-8")
        ).hexdigest()

        write_json(run_dir / "results.json", {
            "summary": summary,
            "result_hash": result_hash,
        })

        # 9. Write final status.json
        write_json(run_dir / "status.json", {
            "experiment_id": exp_id,
            "status": run_status,
            "preflight_status": "passed",
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_s": duration_s,
            "ts_utc": completed_at,
        })

        if proc.returncode == 0:
            append_line(stdout_log, f"[{completed_at}] Run completed successfully in {duration_s}s")
            return {"summary": summary, "result_hash": result_hash}

        append_line(stdout_log, f"[{completed_at}] Run failed with code {proc.returncode} after {duration_s}s")
        raise RuntimeError(f"TM4 subprocess failed with exit code {proc.returncode}")

    finally:
        # --- BEST EFFORT POST-RUN ORCHESTRATION ---
        
        # A. Run Summary Extraction
        summary_path = None
        try:
            summary_path = RunSummaryExtractor(
                run_dir=run_dir,
                tm4_core_repo=TM4_CORE_PATH,
                tm4server_repo=Path(__file__).parent.parent,
            ).write()
            append_line(stdout_log, f"[{utc_now_iso()}] Wrote run summary: {summary_path}")
            _emit_event(event_log, "run_summary_written", path=str(summary_path))
        except Exception as exc:
            append_line(stderr_log, f"[{utc_now_iso()}] RUN_SUMMARY ERROR: {exc}")
            _emit_event(event_log, "run_summary_failed", error=str(exc))

        # B. Experiment Report Generation
        report_path = None
        if summary_path:
            try:
                report_path = ExperimentReportGenerator(
                    summary_path=summary_path,
                    docs_root=TM4_DOCS_ROOT,
                    deployment_path="/opt/tm4server",
                    tm4_core_path=str(TM4_CORE_PATH),
                    runtime_root=str(RUNS_DIR.parent),
                ).write()
                append_line(stdout_log, f"[{utc_now_iso()}] Wrote experiment report: {report_path}")
                _emit_event(event_log, "experiment_report_written", path=str(report_path))
            except Exception as exc:
                append_line(stderr_log, f"[{utc_now_iso()}] EXPERIMENT_REPORT ERROR: {exc}")
                _emit_event(event_log, "experiment_report_failed", error=str(exc))

        # C. Global Aggregation Refresh (includes results.csv / results.json)
        ledger_paths: list[Path] = []
        try:
            output_csv = TM4_DOCS_ROOT / "results.csv"
            output_json = TM4_DOCS_ROOT / "results.json"
            
            agg_result = RunAggregator(
                runs_root=RUNS_DIR,
                output_csv=output_csv,
                output_json=output_json,
            ).aggregate()
            
            ledger_paths = [output_csv, output_json]
            append_line(
                stdout_log,
                f"[{utc_now_iso()}] AGGREGATE_UPDATED: {agg_result.rows_written} runs indexed"
            )
            _emit_event(
                event_log,
                "aggregate_updated",
                rows_written=agg_result.rows_written,
                failed_files=agg_result.failed_files
            )
        except Exception as exc:
            append_line(stderr_log, f"[{utc_now_iso()}] AGGREGATE_ERROR: {exc}")
            _emit_event(event_log, "aggregate_failed", error=str(exc))

        # D. Git Synchronization (Report + Ledger)
        if TM4_AUTO_PUSH_REPORTS:
            sync_targets = []
            if report_path:
                sync_targets.append(report_path)
            sync_targets.extend(ledger_paths)
            
            if sync_targets:
                try:
                    success = sync_report_to_git(
                        repo_path=Path(__file__).parent.parent,
                        file_paths=sync_targets,
                        commit_msg=f"Experiment update: {exp_id}",
                        auto_push=True
                    )
                    
                    if success:
                        append_line(stdout_log, f"[{utc_now_iso()}] GIT_SYNC OK: {len(sync_targets)} artifacts synchronized")
                        _emit_event(event_log, "git_sync_completed", ok=True, count=len(sync_targets))
                    else:
                        append_line(stderr_log, f"[{utc_now_iso()}] GIT_SYNC FAILED: Check git logs for details")
                        _emit_event(event_log, "git_sync_completed", ok=False)
                except Exception as exc:
                    append_line(stderr_log, f"[{utc_now_iso()}] GIT_SYNC ERROR: {exc}")
                    _emit_event(event_log, "git_sync_failed", error=str(exc))
        elif report_path:
            append_line(stdout_log, f"[{utc_now_iso()}] GIT_SYNC SKIPPED: TM4_AUTO_PUSH_REPORTS disabled")
            _emit_event(event_log, "git_sync_skipped", reason="TM4_AUTO_PUSH_REPORTS disabled")
