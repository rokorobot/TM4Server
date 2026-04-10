from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from tm4server.utils import (
    extract_fitness_series,
    safe_float,
    safe_int,
    split_early_late,
    variance,
)


AGGREGATE_SCHEMA_VERSION = "1.1"


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
    "gen0_best",
    "final_best",
    "best_fitness_by_gen",
    "net_improvement",
    "fitness_range",
    "early_variance",
    "late_variance",
    "improvement_density",
    "monotonicity_ratio",
    "collapse_count",
    "success_threshold",
    "anchor_regime",
    "validator_perturbation_pct",
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

        metrics_raw = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
        validation = summary.get("validation") if isinstance(summary.get("validation"), dict) else {}

        # Derived metrics v1
        series = extract_fitness_series(summary)
        
        gen0_best = safe_float(metrics_raw.get("gen0_best"))
        final_best = safe_float(metrics_raw.get("final_best"))
        fitness_max = safe_float(metrics_raw.get("fitness_max"))
        fitness_min = safe_float(metrics_raw.get("fitness_min"))
        generations = safe_int(metrics_raw.get("generations"))
        
        if series:
            if gen0_best is None: gen0_best = series[0]
            if final_best is None: final_best = series[-1]
            if fitness_max is None: fitness_max = max(series)
            if fitness_min is None: fitness_min = min(series)
            if generations is None: generations = len(series)

        net_improvement = safe_float(metrics_raw.get("net_improvement"))
        if net_improvement is None and gen0_best is not None and final_best is not None:
            net_improvement = final_best - gen0_best
            
        fitness_range = safe_float(metrics_raw.get("fitness_range"))
        if fitness_range is None and fitness_max is not None and fitness_min is not None:
            fitness_range = fitness_max - fitness_min

        early_variance = safe_float(metrics_raw.get("early_variance"))
        late_variance = safe_float(metrics_raw.get("late_variance"))
        if series and (early_variance is None or late_variance is None):
            early, late = split_early_late(series)
            if early_variance is None: early_variance = variance(early)
            if late_variance is None: late_variance = variance(late)

        improvement_density = safe_float(metrics_raw.get("improvement_density"))
        if improvement_density is None and len(series) > 1:
            new_highs = 0
            running_high = series[0]
            for val in series[1:]:
                if val > running_high:
                    new_highs += 1
                    running_high = val
            improvement_density = new_highs / (len(series) - 1)

        monotonicity_ratio = safe_float(metrics_raw.get("monotonicity_ratio"))
        if monotonicity_ratio is None and len(series) > 1:
            steps = sum(1 for i in range(1, len(series)) if series[i] >= series[i-1])
            monotonicity_ratio = steps / (len(series) - 1)

        collapse_count = safe_int(metrics_raw.get("collapse_count"))
        # We don't have collapse_delta here but we can assume 10.0 or just leave it if missing
        # Actually, let's just stick to what we can safely derive or what was already there.

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
            "generations": fmt_scalar(generations),
            "fitness_max": fmt_scalar(fitness_max),
            "fitness_mean": fmt_scalar(metrics_raw.get("fitness_mean")),
            "fitness_min": fmt_scalar(fitness_min),
            "ttc": fmt_scalar(metrics_raw.get("ttc")),
            "violations": fmt_scalar(metrics_raw.get("violations")),
            "checkpoints": fmt_scalar(metrics_raw.get("checkpoints")),
            "commits": fmt_scalar(metrics_raw.get("commits")),
            "gen0_best": fmt_scalar(gen0_best),
            "final_best": fmt_scalar(final_best),
            "best_fitness_by_gen": "|".join(map(str, series)) if series else "",
            "net_improvement": fmt_scalar(net_improvement),
            "fitness_range": fmt_scalar(fitness_range),
            "early_variance": fmt_scalar(early_variance),
            "late_variance": fmt_scalar(late_variance),
            "improvement_density": fmt_scalar(improvement_density),
            "monotonicity_ratio": fmt_scalar(monotonicity_ratio),
            "collapse_count": fmt_scalar(collapse_count),
            "success_threshold": fmt_scalar(metrics_raw.get("success_threshold")),
            "anchor_regime": fmt_scalar(summary.get("anchor_regime")),
            "validator_perturbation_pct": fmt_scalar(summary.get("validator_perturbation_pct")),
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
