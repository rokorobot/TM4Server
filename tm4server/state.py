from __future__ import annotations

import json
import os
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        queue_depth: int = 0,
        last_completed_exp_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Writes the current runtime status atomically."""
        payload: dict[str, Any] = {
            "status_version": 1,
            "ts_utc": utc_now_iso(),
            "instance_id": socket.gethostname(),
            "runtime_state": runtime_state,
            "current_exp_id": current_exp_id,
            "queue_depth": queue_depth,
            "last_completed_exp_id": last_completed_exp_id,
            "worker_pid": os.getpid(),
            "tm4server_version": git_short_commit(self.tm4server_repo) if self.tm4server_repo else None,
            "tm4core_version": git_short_commit(self.tm4core_repo) if self.tm4core_repo else None,
        }
        if extra:
            payload.update(extra)
        
        atomic_write_json(self.paths.status_json, payload)
