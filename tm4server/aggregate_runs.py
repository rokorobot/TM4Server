from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


AGGREGATE_SCHEMA_VERSION = "1.0"


CSV_COLUMNS = [
    "exp_id",
    "status",
    "validation_status",
    "validation_reason",
    "started_at",
    "completed_at",
    "duration_s",
    "instance_id",
    "execution_mode",
    "tm4_version",
    "tm4server_version",
    "generations",
    "fitness_max",
    "fitness_mean",
    "fitness_min",
    "ttc",
    "violations",
    "checkpoints",
    "commits",
    "artifact_root",
    "summary_path",
    "schema_version",
]


def safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ValueError(f"JSON file does not exist: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to read JSON from {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")

    return payload


def fmt_scalar(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def validate_summary_payload(payload: Dict[str, Any], path: Path) -> None:
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
        raise ValueError(f"{path} missing required keys: {missing}")


@dataclass
class AggregateResult:
    rows_written: int
    failed_files: int
    output_csv: Path
    output_json: Path | None


class RunAggregator:
    """
    Aggregates TM4 run_summary.json files into a flat cross-run ledger.
    """

    def __init__(self, runs_root: Path, output_csv: Path, output_json: Path | None = None) -> None:
        self.runs_root = runs_root.resolve()
        self.output_csv = output_csv.resolve()
        self.output_json = output_json.resolve() if output_json else None

    def find_summary_files(self) -> List[Path]:
        if not self.runs_root.exists() or not self.runs_root.is_dir():
            raise ValueError(f"Runs root does not exist or is not a directory: {self.runs_root}")

        summary_files: List[Path] = []
        for child in sorted(self.runs_root.iterdir()):
            if child.is_dir():
                candidate = child / "run_summary.json"
                if candidate.exists() and candidate.is_file():
                    summary_files.append(candidate)

        return summary_files

    def summary_to_row(self, summary: Dict[str, Any], summary_path: Path) -> Dict[str, Any]:
        validate_summary_payload(summary, summary_path)

        metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
        validation = summary.get("validation") if isinstance(summary.get("validation"), dict) else {}

        row = {
            "exp_id": fmt_scalar(summary.get("exp_id")),
            "status": fmt_scalar(summary.get("status")),
            "validation_status": fmt_scalar(validation.get("status")),
            "validation_reason": fmt_scalar(validation.get("reason")),
            "started_at": fmt_scalar(summary.get("started_at")),
            "completed_at": fmt_scalar(summary.get("completed_at")),
            "duration_s": fmt_scalar(summary.get("duration_s")),
            "instance_id": fmt_scalar(summary.get("instance_id")),
            "execution_mode": fmt_scalar(summary.get("execution_mode")),
            "tm4_version": fmt_scalar(summary.get("tm4_version")),
            "tm4server_version": fmt_scalar(summary.get("tm4server_version")),
            "generations": fmt_scalar(metrics.get("generations")),
            "fitness_max": fmt_scalar(metrics.get("fitness_max")),
            "fitness_mean": fmt_scalar(metrics.get("fitness_mean")),
            "fitness_min": fmt_scalar(metrics.get("fitness_min")),
            "ttc": fmt_scalar(metrics.get("ttc")),
            "violations": fmt_scalar(metrics.get("violations")),
            "checkpoints": fmt_scalar(metrics.get("checkpoints")),
            "commits": fmt_scalar(metrics.get("commits")),
            "artifact_root": fmt_scalar(summary.get("artifact_root")),
            "summary_path": str(summary_path),
            "schema_version": fmt_scalar(summary.get("schema_version")),
        }
        return row

    def aggregate(self) -> AggregateResult:
        summary_files = self.find_summary_files()

        rows: List[Dict[str, Any]] = []
        failures: List[Dict[str, str]] = []

        for summary_path in summary_files:
            try:
                summary = safe_read_json(summary_path)
                row = self.summary_to_row(summary, summary_path)
                rows.append(row)
            except Exception as exc:
                failures.append({
                    "summary_path": str(summary_path),
                    "error": str(exc),
                })

        rows.sort(key=lambda r: str(r.get("exp_id", "")))

        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with self.output_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        if self.output_json:
            payload = {
                "aggregate_schema_version": AGGREGATE_SCHEMA_VERSION,
                "rows_written": len(rows),
                "failed_files": len(failures),
                "runs_root": str(self.runs_root),
                "csv_columns": CSV_COLUMNS,
                "rows": rows,
                "failures": failures,
            }
            self.output_json.parent.mkdir(parents=True, exist_ok=True)
            self.output_json.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return AggregateResult(
            rows_written=len(rows),
            failed_files=len(failures),
            output_csv=self.output_csv,
            output_json=self.output_json,
        )
