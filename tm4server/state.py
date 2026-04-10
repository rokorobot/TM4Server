from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Union
from contextlib import contextmanager


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomic write using a temporary file and rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


@contextmanager
def atomic_lock(lock_file: Path, timeout: float = 10.0) -> Iterator[None]:
    """Simple filesystem-based lock using O_EXCL."""
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    while True:
        try:
            # os.O_EXCL ensures the call fails if the file already exists (atomic on most FS)
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, str(os.getpid()).encode())
                yield
                return
            finally:
                os.close(fd)
                try:
                    os.remove(lock_file)
                except OSError:
                    pass
        except FileExistsError:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Could not acquire lock on {lock_file} after {timeout} seconds")
            time.sleep(0.1)


def read_json_strict(path: Path) -> dict[str, Any]:
    """Strictly reads JSON from path. 
    Raises FileNotFoundError, JSONDecodeError, or other OSErrors.
    """
    # utf-8-sig handles potential BOM from Windows/PowerShell
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_json_safe(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    """Safe read that only handles FileNotFoundError (returning default).
    Raises JSONDecodeError, PermissionError, and other IO errors.
    """
    try:
        return read_json_strict(path)
    except FileNotFoundError:
        return default.copy()


def git_short_commit(repo_path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception:
        return None
    return None


@dataclass(slots=True)
class StatePaths:
    root: Path
    status_json: Path
    control_json: Path
    control_history_jsonl: Path

    @classmethod
    def from_runtime_root(cls, runtime_root: Path) -> "StatePaths":
        state_root = runtime_root / "state"
        return cls(
            root=state_root,
            status_json=state_root / "status.json",
            control_json=state_root / "control.json",
            control_history_jsonl=state_root / "control_history.jsonl",
        )


class StateManager:
    def __init__(self, runtime_root: Path, tm4server_repo: Path | None = None, tm4core_repo: Path | None = None):
        self.paths = StatePaths.from_runtime_root(runtime_root)
        self.tm4server_repo = tm4server_repo
        self.tm4core_repo = tm4core_repo
        # Initialization must be read-only.
        # Defaults are ensured during explicit bootstrap or writer startup (e.g. worker).

    def ensure_defaults(self) -> None:
        """Ensures that the control.json file exists with a valid default."""
        if not self.paths.control_json.exists():
            self.set_control_mode("run", source="system_init")

    def read_control_mode(self) -> str:
        """Reads current control mode. 
        Returns 'run' if file is missing.
        Raises JSONDecodeError/ValueError if file is corrupted or semantically invalid.
        """
        payload = read_json_safe(
            self.paths.control_json,
            {"control_version": 1, "mode": "run"},
        )
        
        mode = payload.get("mode")
        if mode not in {"run", "pause", "halt"}:
            raise ValueError(f"Invalid or missing control mode in state file: {mode}")
        
        return mode

    def set_control_mode(self, mode: str, source: str = "manual") -> None:
        if mode not in {"run", "pause", "halt"}:
            raise ValueError(f"Invalid control mode: {mode}")

        atomic_write_json(
            self.paths.control_json,
            {
                "control_version": 1,
                "mode": mode,
                "updated_at_utc": utc_now_iso(),
                "source": source,
            },
        )
        append_jsonl(
            self.paths.control_history_jsonl,
            {
                "ts_utc": utc_now_iso(),
                "action": mode,
                "source": source,
                "result": "accepted",
            },
        )

    def read_status(self) -> dict[str, Any]:
        """Reads current status from disk. Returns empty dict if missing.
        Raises JSONDecodeError if corrupted.
        """
        return read_json_safe(self.paths.status_json, {})

    def read_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Reads latest control history entries from JSONL.
        Zero-tolerance policy: any malformed line raises JSONDecodeError.
        """
        if not self.paths.control_history_jsonl.exists():
            return []
        
        # Hard cap for performance
        limit = min(max(1, limit), 500)
        
        with self.paths.control_history_jsonl.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            history = []
            for line in reversed(lines):
                # Strict parsing: failure here propagates as JSONDecodeError
                entry = json.loads(line)
                
                # Semantic check
                required = {"ts_utc", "action", "source", "result"}
                if not all(k in entry for k in required):
                    raise ValueError(f"Malformed history entry: missing fields. Entry: {line}")
                
                history.append(entry)
                if len(history) >= limit:
                    break
            return history

    def write_status(
        self,
        runtime_state: str,
        current_exp_id: str | None = None,
        queue_depth: int | None = None,
        last_completed_exp_id: str | None = None,
        extra: dict[str, Any] | None = None,
        reset_current: bool = False # Explicit flag to clear current_exp_id
    ) -> None:
        """Writes the current runtime status atomically, carrying forward existing fields where appropriate."""
        current = self.read_status()
        
        payload: dict[str, Any] = {
            "status_version": 1,
            "ts_utc": utc_now_iso(),
            "instance_id": socket.gethostname(),
            "worker_pid": os.getpid(),
            "tm4server_version": git_short_commit(self.tm4server_repo) if self.tm4server_repo else current.get("tm4server_version"),
            "tm4core_version": git_short_commit(self.tm4core_repo) if self.tm4core_repo else current.get("tm4core_version"),
            "runtime_state": runtime_state,
        }

        # current_exp_id: Use provided, or clear if reset_current, or carry forward
        if current_exp_id is not None:
            payload["current_exp_id"] = current_exp_id
        elif reset_current:
            payload["current_exp_id"] = None
        else:
            payload["current_exp_id"] = current.get("current_exp_id")

        # queue_depth: Use provided or carry forward
        payload["queue_depth"] = queue_depth if queue_depth is not None else current.get("queue_depth", 0)
        
        # last_completed_exp_id: Use provided or carry forward (NEVER clear automatically)
        payload["last_completed_exp_id"] = last_completed_exp_id if last_completed_exp_id is not None else current.get("last_completed_exp_id")

        # Merge extra
        payload_extra = current.get("extra", {}).copy()
        if extra:
            payload_extra.update(extra)
        payload["extra"] = payload_extra
        
        atomic_write_json(self.paths.status_json, payload)

    def allocate_next_exp_id(self, runs_dir: Path, prefix: str = "EXP-SER") -> str:
        """Atomically allocates the next sequential experiment ID and creates its directory."""
        lock_file = runs_dir / ".lock"
        with atomic_lock(lock_file):
            # Scan existing directories
            runs_dir.mkdir(parents=True, exist_ok=True)
            existing_ids = []
            for d in runs_dir.iterdir():
                if d.is_dir() and d.name.startswith(prefix):
                    try:
                        suffix = int(d.name[len(prefix)+1:])
                        existing_ids.append(suffix)
                    except ValueError:
                        continue
            
            next_val = max(existing_ids, default=0) + 1
            next_id = f"{prefix}-{next_val:04d}"
            
            # Create the directory within the lock to ensure atomicity
            (runs_dir / next_id).mkdir(parents=True, exist_ok=False)
            return next_id

    def get_workload_summary(self, runs_dir: Path) -> dict[str, int]:
        """Scans runs_dir and returns counts for pending, running, and completed/failed runs."""
        summary = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "interrupted": 0}
        if not runs_dir.exists():
            return summary
            
        for d in runs_dir.iterdir():
            if not d.is_dir() or not d.name.startswith("EXP"):
                continue
                
            state_file = d / "runtime_state.json"
            summary_file = d / "run_summary.json"
            
            if summary_file.exists():
                # Terminal state
                try:
                    data = read_json_strict(summary_file)
                    status = data.get("status", "unknown")
                    if status == "completed" or status == "success":
                        summary["completed"] += 1
                    elif status == "failed":
                        summary["failed"] += 1
                    else:
                        summary["completed"] += 1 # Default to completed for summary existence
                except Exception:
                    summary["completed"] += 1
                continue
                
            if state_file.exists():
                try:
                    state = read_json_strict(state_file)
                    status = state.get("status")
                    if status == "running":
                        summary["running"] += 1
                    elif status == "queued":
                        summary["pending"] += 1
                    elif status == "interrupted":
                        summary["interrupted"] += 1
                except Exception:
                    summary["pending"] += 1
            else:
                # Dir exists but no state file yet (race or partial creation)
                summary["pending"] += 1
        
        return summary

    def get_next_pending_run(self, runs_dir: Path) -> Path | None:
        """Finds the oldest run directory that is currently 'queued'."""
        if not runs_dir.exists():
            return None
            
        pending_runs = []
        for d in runs_dir.iterdir():
            if not d.is_dir() or not d.name.startswith("EXP"):
                continue
            
            # Terminal check
            if (d / "run_summary.json").exists():
                continue
                
            state_file = d / "runtime_state.json"
            if not state_file.exists():
                # Partial dir creation or legacy queued run?
                # We prioritize folders with a proper manifest
                if (d / "run_manifest.json").exists():
                    pending_runs.append(d)
                continue
                
            try:
                state = read_json_strict(state_file)
                if state.get("status") == "queued":
                    pending_runs.append(d)
            except Exception:
                continue
        
        if not pending_runs:
            return None
            
        # Deterministic ordering by created_at in manifest
        def sort_key(p: Path):
            manifest_path = p / "run_manifest.json"
            if not manifest_path.exists():
                return utc_now_iso()
            try:
                m = read_json_strict(manifest_path)
                return m.get("created_at", utc_now_iso())
            except Exception:
                return utc_now_iso()
                
        pending_runs.sort(key=sort_key)
        return pending_runs[0]

    def scan_for_interrupted_runs(self, runs_dir: Path) -> int:
        """Identifies 'running' runs that lack an active worker PID and marks them as interrupted."""
        if not runs_dir.exists():
            return 0
            
        interrupted_count = 0
        for d in runs_dir.iterdir():
            if not d.is_dir() or not d.name.startswith("EXP"):
                continue
                
            state_file = d / "runtime_state.json"
            summary_file = d / "run_summary.json"
            
            # If summary exists, it's terminal.
            if summary_file.exists():
                continue
                
            if not state_file.exists():
                continue
                
            try:
                state = read_json_strict(state_file)
                if state.get("status") == "running":
                    worker_pid = state.get("worker_pid")
                    
                    # Check if process is alive
                    alive = False
                    if worker_pid:
                        try:
                            # os.kill(pid, 0) is the standard existence check
                            os.kill(worker_pid, 0)
                            alive = True
                        except OSError:
                            alive = False
                    
                    if not alive:
                        # Mark as interrupted
                        state["status"] = "interrupted"
                        state["interrupted_at"] = utc_now_iso()
                        state["updated_at"] = utc_now_iso()
                        state["failure_reason"] = "Worker process died or was killed before completion."
                        atomic_write_json(state_file, state)
                        interrupted_count += 1
            except Exception:
                continue
        
        return interrupted_count

    def list_runs(self, runs_dir: Path, limit: int = 50) -> list[dict[str, Any]]:
        """Scans runs_dir and returns a list of normalized run metadata objects."""
        if not runs_dir.exists():
            return []
            
        runs = []
        for d in runs_dir.iterdir():
            if not d.is_dir() or not d.name.startswith("EXP"):
                continue
                
            manifest_path = d / "run_manifest.json"
            state_path = d / "runtime_state.json"
            summary_path = d / "run_summary.json"
            
            # 1. Base Metadata from Manifest
            manifest = read_json_safe(manifest_path, {})
            state = read_json_safe(state_path, {})
            summary = read_json_safe(summary_path, {})
            
            # 2. Strict Status Precedence
            # failed (summary) > completed (summary) > running (state) > interrupted (state) > queued (state) > unknown
            status = "unknown"
            if summary_path.exists():
                s_status = summary.get("status")
                if s_status == "failed":
                    status = "failed"
                else: # covers 'completed' and 'success'
                    status = "completed"
            elif state.get("status") == "running":
                status = "running"
            elif state.get("status") == "interrupted":
                status = "interrupted"
            elif state.get("status") == "queued":
                status = "queued"
            
            # 3. Read Classification (Cached)
            classification_data = read_json_safe(d / "classification.json", {})
            classification = classification_data.get("classification", {})
            
            # 4. Normalized Row
            run = {
                "exp_id": d.name,
                "status": status,
                "classification_label": classification.get("label"),
                "classification_confidence": classification.get("confidence"),
                "created_at": manifest.get("created_at") or manifest.get("submitted_at"),
                "started_at": state.get("started_at"),
                "completed_at": summary.get("ts_utc") or state.get("completed_at") or state.get("failed_at"),
                "task": manifest.get("task", "unknown"),
                "model": manifest.get("model", "unknown"),
                "requested_by": manifest.get("requested_by", "unknown"),
                "failure_reason": summary.get("error") or state.get("failure_reason") or state.get("error"),
                "has_summary": summary_path.exists(),
                "has_results": (d / "results.json").exists(),
                "has_stdout": (d / "stdout.log").exists(),
                "has_stderr": (d / "stderr.log").exists(),
                "duration_s": None # TODO: calculate if needed
            }
            runs.append(run)
            
        # 4. Sort newest first by manifest created_at
        def sort_key(r):
            return r.get("created_at") or "0"
            
        runs.sort(key=sort_key, reverse=True)
        return runs[:limit]

    def get_run_detail(self, runs_dir: Path, exp_id: str) -> dict[str, Any]:
        """Returns the full raw JSON payloads for a specific run."""
        run_dir = runs_dir / exp_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {exp_id}")
            
        return {
            "exp_id": exp_id,
            "manifest": read_json_safe(run_dir / "run_manifest.json", {}),
            "runtime_state": read_json_safe(run_dir / "runtime_state.json", {}),
            "summary": read_json_safe(run_dir / "run_summary.json", {}),
            "classification": read_json_safe(run_dir / "classification.json", {}).get("classification")
        }

    def build_regime_index(self, runs_dir: Path) -> dict[str, Any]:
        """
        Scans all runs, groups them by (task, model) regime, and 
        returns a research-grade gradient index.
        """
        from .analysis.gradient_detector import GradientDetector
        
        if not runs_dir.exists():
            return {"gradient_version": "v1", "generated_at": utc_now_iso(), "regimes": []}
            
        # Groupings: (task, model) -> list of classification blocks
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        
        for d in runs_dir.iterdir():
            if not d.is_dir() or not d.name.startswith("EXP"):
                continue
                
            manifest_path = d / "run_manifest.json"
            class_path = d / "classification.json"
            
            if not manifest_path.exists():
                continue
                
            manifest = read_json_safe(manifest_path, {})
            task = manifest.get("task", "unknown")
            model = manifest.get("model", "unknown")
            class_payload = read_json_safe(class_path, {})
            classification = class_payload.get("classification")
            
            # 1. Auto-classify on-the-fly if missing and summary exists
            if not classification:
                summary_path = d / "run_summary.json"
                if summary_path.exists():
                    from .analysis.classifier import ExperimentClassifier
                    summary = read_json_safe(summary_path, {})
                    try:
                        classifier = ExperimentClassifier()
                        result = classifier.classify(summary)
                        classification = result.get("classification")
                        
                        # Persist the inferred classification for future truth consistency
                        if classification:
                            atomic_write_json(class_path, result)
                    except Exception:
                        pass
            
            # 2. Skip if still no classification (failed or incomplete)
            if not classification:
                continue
                
            key = (task, model)
            if key not in groups:
                 groups[key] = []
            groups[key].append(classification)
            
        detector = GradientDetector()
        return detector.build_report(groups)
