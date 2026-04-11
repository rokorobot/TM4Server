from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


REPORT_GENERATOR_VERSION = "1.1"
FORENSIC_LOG_TAIL_LINES = 80


def safe_get(data: Any, key: str, default: Any = None) -> Any:
    if not isinstance(data, dict):
        return default
    return data.get(key, default)


class ExperimentReportGenerator:
    """
    Generates a deterministic markdown experiment report from run artifacts.
    Governed by Execution Report Specification v1.
    """

    def __init__(
        self,
        summary_path: Path,
        docs_root: Path,
        deployment_path: str = "/opt/tm4server",
        tm4_core_path: str = "/opt/tm4-core",
        runtime_root: str = "/var/lib/tm4",
    ) -> None:
        self.summary_path = summary_path.resolve()
        self.docs_root = docs_root.resolve()
        self.run_dir = self.summary_path.parent
        self.deployment_path = deployment_path
        self.tm4_core_path = tm4_core_path
        self.runtime_root = runtime_root

        # Artifact Health Tracking (Spec v1)
        self.load_states: Dict[str, str] = {}
        self.load_details: Dict[str, str] = {}

        # Load Multi-File Artifact Set
        self.summary = self._load_json(self.summary_path)
        self.manifest = self._load_json(self.run_dir / "run_manifest.json")
        self.status = self._load_json(self.run_dir / "status.json")

        # Centralized Run ID Resolution (Triple-fallback as per Spec v1)
        self.run_id = (
            safe_get(self.summary, "run_id") 
            or safe_get(self.manifest, "run_id") 
            or self.run_dir.name
        )

    def _load_json(self, path: Path) -> Dict[str, Any]:
        name = path.name
        if not path.exists():
            self.load_states[name] = "missing"
            return {}
        
        try:
            raw = path.read_text(encoding="utf-8-sig")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                self.load_states[name] = "not-an-object"
                self.load_details[name] = "JSON root is not an object"
                return {}
            
            self.load_states[name] = "loaded"
            return payload
        except Exception as exc:
            self.load_states[name] = "malformed"
            self.load_details[name] = str(exc)
            return {}

    def _read_log(self, name: str, max_lines: int = FORENSIC_LOG_TAIL_LINES) -> str:
        p = self.run_dir / name
        if not p.exists():
            return f"--- No {name} available ---"
        try:
            from collections import deque
            with p.open("r", encoding="utf-8", errors="replace") as f:
                lines = deque(f, maxlen=max_lines)
                return "".join(lines)
        except Exception:
            return f"--- Error reading {name} ---"

    @property
    def output_path(self) -> Path:
        # Spec v1: Use unified run_id for absolute filename consistency
        return self.docs_root / f"{self.run_id}.md"

    def generate_markdown(self) -> str:
        sum_data = self.summary
        man_data = self.manifest
        sta_data = self.status

        # Metadata Fallback Chains (Spec v1)
        # status: summary -> status -> manifest -> unknown
        status = (
            safe_get(sum_data, "status")
            or safe_get(sta_data, "status")
            or safe_get(man_data, "status")
            or "unknown"
        )

        # instance_id: status -> summary -> manifest -> unknown
        instance_id = (
            safe_get(sta_data, "instance_id")
            or safe_get(sum_data, "instance_id")
            or safe_get(man_data, "instance_id")
            or "unknown"
        )

        # exp_id: summary -> manifest -> status -> unknown
        exp_id = (
            safe_get(sum_data, "exp_id")
            or safe_get(man_data, "exp_id")
            or safe_get(sta_data, "exp_id")
            or "unknown"
        )

        run_id = self.run_id
        duration = safe_get(sum_data, "duration_s")
        duration_display = f"{duration}s" if duration is not None else "unknown"
        exit_code = safe_get(sum_data, "exit_code", "unknown")
        
        workload = safe_get(man_data, "workload_type", safe_get(man_data, "task", "unknown"))
        requested_by = safe_get(man_data, "requested_by", "unknown")
        error = safe_get(sum_data, "error") or safe_get(sum_data, "failure_reason")

        stdout = self._read_log("stdout.log")
        stderr = self._read_log("stderr.log")

        # Artifact Health Section (Spec v1)
        health_lines = []
        for name in ["run_manifest.json", "status.json", "run_summary.json"]:
            state = self.load_states.get(name, "missing")
            health_lines.append(f"- **{name}**: `{state}`")
            if detail := self.load_details.get(name):
                health_lines.append(f"- **{name} Detail**: `{detail}`")
        health_section = "\n".join(health_lines)

        # Canonical Skeleton (Spec v1)
        body = f"""# {run_id} — Execution Report

## Identity
- **Run ID**: `{run_id}`
- **Experiment**: `{exp_id}`
- **Instance**: `{instance_id}`

## Execution
- **Status**: `{status}`
- **Duration**: `{duration_display}`
- **Exit Code**: `{exit_code}`

## Intent
- **Workload**: `{workload}`
- **Requested By**: `{requested_by}`

## Artifact Health
{health_section}

## Outcome
**Execution Error**
```text
{error or "None"}
```

## Forensics
### stdout.log tail
```text
{stdout}
```

### stderr.log tail
```text
{stderr}
```

## Audit
- **Deployment Path**: `{self.deployment_path}`
- **Runtime Root**: `{self.runtime_root}`
- **TM4 Core Path**: `{self.tm4_core_path}`
- **Generated At**: {safe_get(sum_data.get("provenance", {}), "summary_generated_at", "unknown")}
- **Generator Version**: {REPORT_GENERATOR_VERSION}
"""
        return body.strip() + "\n"

    def write(self) -> Path:
        self.docs_root.mkdir(parents=True, exist_ok=True)
        content = self.generate_markdown()
        out_path = self.output_path
        
        # Atomic Write
        tmp_path = out_path.with_suffix(".md.tmp")
        try:
            tmp_path.write_text(content, encoding="utf-8")
            import os
            os.replace(tmp_path, out_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise
            
        return out_path
