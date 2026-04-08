from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


REPORT_GENERATOR_VERSION = "1.0"


def safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Summary file does not exist: {path}")

    try:
        # Use utf-8-sig to handle possible BOM from Windows/PowerShell
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to read JSON from {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Summary file does not contain a JSON object: {path}")

    return payload


def fmt(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    if isinstance(value, float):
        return str(round(value, 3))
    return str(value)


def yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def code_path(value: Any) -> str:
    return f"`{value}`" if value else "`unknown`"


def validate_summary_payload(payload: Dict[str, Any]) -> None:
    required = [
        "schema_version",
        "exp_id",
        "instance_id",
        "execution_mode",
        "status",
        "artifact_root",
        "input",
        "artifacts",
        "metrics",
        "validation",
        "provenance",
        "warnings",
    ]
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"run_summary missing required keys: {missing}")


class ExperimentReportGenerator:
    """
    Generates a deterministic markdown experiment report from run_summary.json.
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
        self.deployment_path = deployment_path
        self.tm4_core_path = tm4_core_path
        self.runtime_root = runtime_root

        self.summary = safe_read_json(self.summary_path)
        validate_summary_payload(self.summary)

    @property
    def exp_id(self) -> str:
        value = self.summary.get("exp_id")
        if not value:
            raise ValueError(f"run_summary missing exp_id: {self.summary_path}")
        return str(value)

    @property
    def output_path(self) -> Path:
        return self.docs_root / f"{self.exp_id}.md"

    def generate_markdown(self) -> str:
        s = self.summary

        input_block = s.get("input") if isinstance(s.get("input"), dict) else {}
        artifacts = s.get("artifacts") if isinstance(s.get("artifacts"), dict) else {}
        metrics = s.get("metrics") if isinstance(s.get("metrics"), dict) else {}
        validation = s.get("validation") if isinstance(s.get("validation"), dict) else {}
        provenance = s.get("provenance") if isinstance(s.get("provenance"), dict) else {}
        warnings = s.get("warnings") if isinstance(s.get("warnings"), list) else []

        artifact_lines = []
        for name in sorted(artifacts.keys()):
            artifact_lines.append(f"- `{name}`: {yes_no(artifacts.get(name))}")
        artifact_section = "\n".join(artifact_lines) if artifact_lines else "- None"

        warning_lines = "\n".join(f"- {str(w)}" for w in warnings) if warnings else "- None"

        body = f"""# {self.exp_id} — VPS Execution Report

## Objective
Execution record for TM4Server run `{self.exp_id}`.

## Execution Context
- Environment: {fmt(s.get("execution_mode"))}
- Instance ID: {fmt(s.get("instance_id"))}
- Status: {fmt(s.get("status"))}
- TM4 Version: {fmt(s.get("tm4_version"))}
- TM4Server Version: {fmt(s.get("tm4server_version"))}

## Timing
- Started At: {fmt(s.get("started_at"))}
- Completed At: {fmt(s.get("completed_at"))}
- Duration (s): {fmt(s.get("duration_s"))}

## Artifact Root
- {code_path(s.get("artifact_root"))}

## Input References
- Config: {code_path(input_block.get("config_path"))}
- Input Manifest: {code_path(input_block.get("input_manifest_path"))}

## Artifact Presence
{artifact_section}

## Metrics
- Generations: {fmt(metrics.get("generations"))}
- Fitness Max: {fmt(metrics.get("fitness_max"))}
- Fitness Mean: {fmt(metrics.get("fitness_mean"))}
- Fitness Min: {fmt(metrics.get("fitness_min"))}
- TTC: {fmt(metrics.get("ttc"))}
- Violations: {fmt(metrics.get("violations"))}
- Checkpoints: {fmt(metrics.get("checkpoints"))}
- Commits: {fmt(metrics.get("commits"))}

## Validation
- Status: {fmt(validation.get("status"))}
- Reason: {fmt(validation.get("reason"))}

## Provenance
- Summary Generated At: {fmt(provenance.get("summary_generated_at"))}
- Summary Generator: {fmt(provenance.get("summary_generator"))}
- Summary Generator Version: {fmt(provenance.get("summary_generator_version"))}
- Report Source: `{self.summary_path.name}`
- Report Generator Version: {REPORT_GENERATOR_VERSION}

## Warnings
{warning_lines}

## Canonical Paths
- Deployment Path: `{self.deployment_path}`
- TM4 Core Path: `{self.tm4_core_path}`
- Runtime Root: `{self.runtime_root}`
"""
        return body.strip() + "\n"

    def write(self) -> Path:
        self.docs_root.mkdir(parents=True, exist_ok=True)
        content = self.generate_markdown()
        out_path = self.output_path
        out_path.write_text(content, encoding="utf-8")
        return out_path
