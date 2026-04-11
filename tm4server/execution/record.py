import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional
from collections import deque

from .intelligence import SignalProcessor

def tail_log(path: Path, max_lines: int = 50, max_bytes: int = 16384) -> dict[str, Any]:
    """
    Dual-Constraint Log Tailing Model.
    Returns tail content with truncation and encoding metadata.
    """
    if not path.exists():
        return {
            "content": "",
            "truncated_by": None,
            "lines": 0,
            "bytes": 0,
            "encoding": "utf-8",
            "replacement_char_used": False
        }

    # 1. Byte-level constraint
    file_size = path.stat().st_size
    read_size = min(file_size, max_bytes)
    
    with path.open("rb") as f:
        if file_size > max_bytes:
            f.seek(file_size - max_bytes)
        else:
            f.seek(0)
        
        raw_tail = f.read(read_size)

    # 2. Line-level constraint
    # We decode and split into lines
    content_str = raw_tail.decode("utf-8", errors="replace")
    replacement_char_used = "\ufffd" in content_str
    
    lines = content_str.splitlines(keepends=True)
    
    truncated_by = None
    if file_size > max_bytes:
        truncated_by = "bytes"
    
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
        truncated_by = "lines" # line constraint takes precedence in report visibility

    final_content = "".join(lines)
    
    return {
        "content": final_content,
        "truncated_by": truncated_by,
        "lines": len(lines),
        "bytes": len(final_content.encode("utf-8")),
        "encoding": "utf-8",
        "replacement_char_used": replacement_char_used
    }

def validate_identity_consensus(manifest: dict, status: dict, summary: dict) -> list[str]:
    """
    Spec v1 Identity Consensus Check.
    Enforces that all artifacts in a run directory belong to the same logical run.
    """
    errors = []
    m_run_id = manifest.get("run_id")
    m_exp_id = manifest.get("exp_id")

    if not m_run_id:
        errors.append("manifest missing run_id")
    
    if status:
        s_run_id = status.get("run_id")
        if s_run_id and s_run_id != m_run_id:
            errors.append(f"run_id mismatch: status ({s_run_id}) vs manifest ({m_run_id})")
    
    if summary:
        sum_run_id = summary.get("run_id")
        sum_exp_id = summary.get("exp_id")
        
        if sum_run_id and sum_run_id != m_run_id:
            errors.append(f"run_id mismatch: summary ({sum_run_id}) vs manifest ({m_run_id})")
        
        if sum_exp_id and sum_exp_id != m_exp_id:
            errors.append(f"exp_id mismatch: summary ({sum_exp_id}) vs manifest ({m_exp_id})")
            
    return errors

class RunRecordBuilder:
    """
    Canonical Builder for speculative and terminal Run Records.
    Enforces Spec v1 and validates identity consensus.
    """
    
    def __init__(self, runs_root: Path):
        self.runs_root = runs_root

    def _read_json(self, path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return None

    def build_record(self, run_id: str, strict: bool = True) -> Optional[dict]:
        """
        Builds a full, structured Run Record from a directory.
        Returns None if strict mode is violated.
        """
        run_dir = self.runs_root / run_id
        if not run_dir.exists():
            return None

        # 1. Load Core Artifacts
        manifest = self._read_json(run_dir / "run_manifest.json")
        status_data = self._read_json(run_dir / "status.json")
        summary = self._read_json(run_dir / "run_summary.json")

        # 2. Survival Check (Manifest is required for a record to exist)
        if not manifest:
            if strict: return None
            manifest = {"run_id": run_id, "is_fragment": True}

        # 3. Identity Consensus
        val_errors = validate_identity_consensus(manifest, status_data, summary)
        if strict and val_errors:
            return None

        # 4. Status Authority Resolution
        # (run_summary (terminal) > status (live) > manifest fallback)
        is_terminal = False
        outcome_status = "unknown"
        if summary:
            outcome_status = summary.get("status", "unknown")
            is_terminal = True
        elif status_data:
            outcome_status = status_data.get("status", "unknown")
            is_terminal = (outcome_status in {"success", "failed", "interrupted"})
        
        # 5. Build Intent (Manifest)
        intent = {
            "workload_type": manifest.get("workload_type", "unknown"),
            "requested_by": manifest.get("requested_by", "unknown"),
            "created_at": manifest.get("created_at") or manifest.get("submitted_at"), # compatibility fallback
        }
        
        # Compat check for created_at
        conformance = "spec_v1"
        is_legacy = False
        fallbacks = []
        
        if not manifest.get("created_at"):
            if strict: return None
            is_legacy = True
            conformance = "non_spec_v1"
            if manifest.get("submitted_at"):
                fallbacks.append("submitted_at->created_at")

        # 6. Build Execution (Live Status)
        execution = {
            "status": outcome_status,
            "is_terminal": is_terminal,
            "instance_id": (summary or status_data or {}).get("instance_id", "unknown"),
            "worker_pid": (status_data or {}).get("worker_pid") or (status_data or {}).get("pid"),
            "started_at": (summary or status_data or {}).get("started_at") or manifest.get("started_at"),
            "updated_at": (status_data or {}).get("updated_at") or (status_data or {}).get("ts_utc"),
            "completed_at": (summary or status_data or {}).get("completed_at"),
            "phase": (status_data or {}).get("phase"),
            "progress": (status_data or {}).get("progress"),
            "attempt": (status_data or {}).get("attempt", 1),
        }

        # 7. Build Outcome (Terminal Summary)
        outcome = {
            "status": outcome_status if is_terminal else None,
            "exit_code": (summary or {}).get("exit_code"),
            "duration_s": (summary or {}).get("duration_s"),
        }

        # 8. Build Log Matrix
        logs = {
            "stdout": tail_log(run_dir / "stdout.log"),
            "stderr": tail_log(run_dir / "stderr.log"),
        }

        # 9. Intelligence (Phase 2D.2)
        # We build a partial record first to satisfy the classifier requirements
        partial_record = {
            "identity": {"run_id": manifest.get("run_id", run_id), "exp_id": manifest.get("exp_id")},
            "intent": intent,
            "execution": execution,
            "outcome": outcome,
            "logs": logs,
            "governance": {
                "conformance": conformance,
                "is_legacy": is_legacy,
                "validation_errors": val_errors,
                "fallbacks_used": fallbacks
            },
            "artifacts_meta": {
                "summary_present": (run_dir / "run_summary.json").exists()
            }
        }
        intelligence = SignalProcessor.classify(partial_record)

        # 10. Assemble Run Record
        return {
            "schema_version": "v1",
            "mode": "strict" if strict else "compat",
            "identity": partial_record["identity"],
            "intent": intent,
            "execution": execution,
            "outcome": outcome,
            "intelligence": intelligence,
            "logs": logs,
            "artifacts_meta": {
                "manifest_present": (run_dir / "run_manifest.json").exists(),
                "status_present": (run_dir / "status.json").exists(),
                "summary_present": (run_dir / "run_summary.json").exists(),
                "stdout_present": (run_dir / "stdout.log").exists(),
                "stderr_present": (run_dir / "stderr.log").exists(),
                "aux_runtime_status_present": (run_dir / "tm4_runtime_status.json").exists(),
            },
            "governance": partial_record["governance"]
        }
