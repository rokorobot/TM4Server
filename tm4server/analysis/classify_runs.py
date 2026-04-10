from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from tm4server.utils import (
    safe_float,
    safe_int,
    split_early_late,
    utc_now_iso,
    variance,
)


RULES_VERSION_DEFAULT = "v1"
EPSILON = 1e-9


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_FATAL_IO = 1
EXIT_SCHEMA_ERROR = 2
EXIT_HAS_UNCLASSIFIED = 3
EXIT_NO_VALID_RUNS = 4


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGER = logging.getLogger("tm4server.classify_runs")


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(message)s",
    )


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ThresholdConfig:
    success_threshold: float = 100.0
    saturation_threshold: float = 95.0
    min_meaningful_improvement: float = 10.0
    max_flat_range: float = 3.0
    max_flat_net_improvement: float = 5.0
    max_ttc_for_saturation: int = 1
    max_violation_rate_for_convergent: float = 0.0
    unstable_violation_rate: float = 0.05
    unstable_fitness_std: float = 15.0
    unstable_late_variance: float = 20.0
    collapse_delta: float = 10.0
    min_generations_for_convergence: int = 3
    min_improvement_density_for_convergent: float = 0.2
    min_monotonicity_ratio_for_convergent: float = 0.6


@dataclass(slots=True)
class ClassificationMetrics:
    gen0_best: float | None = None
    final_best: float | None = None
    net_improvement: float | None = None
    fitness_max: float | None = None
    fitness_min: float | None = None
    fitness_mean: float | None = None
    fitness_std: float | None = None
    fitness_range: float | None = None
    generation_count: int | None = None
    ttc: int | None = None
    violations: int | None = None
    violation_rate: float | None = None
    invalid_candidate_rate: float | None = None
    early_variance: float | None = None
    late_variance: float | None = None
    late_stability_ratio: float | None = None
    improvement_density: float | None = None
    monotonicity_ratio: float | None = None
    collapse_count: int | None = None
    reached_success: bool | None = None
    near_ceiling_start: bool | None = None
    flatness_flag: bool | None = None
    instability_flag: bool | None = None
    data_completeness: float | None = None


@dataclass(slots=True)
class ClassificationResult:
    classification: str
    confidence: float
    reason: str
    rules_version: str
    triggered_rules: list[str] = field(default_factory=list)
    metrics: ClassificationMetrics = field(default_factory=ClassificationMetrics)
    backfill_mode: str = "none"
    thresholds: dict[str, Any] = field(default_factory=dict)
    classified_at: str = field(default_factory=lambda: utc_now_iso())


@dataclass(slots=True)
class RunRecord:
    raw: dict[str, Any]

    @property
    def exp_id(self) -> str:
        value = self.raw.get("exp_id")
        return str(value) if value is not None else "UNKNOWN"

    @property
    def status(self) -> str:
        value = self.raw.get("status")
        return str(value).strip() if value is not None else ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass(slots=True)
class ClassificationSummary:
    rules_version: str
    generated_at: str
    total_runs: int
    counts: dict[str, int]


@dataclass(slots=True)
class CLIArgs:
    input_json: Path | None
    input_csv: Path | None
    run_dir: Path | None
    input_format: str
    output_json: Path | None
    output_csv: Path | None
    summary_json: Path | None
    in_place: bool
    success_threshold: float
    saturation_threshold: float
    min_meaningful_improvement: float
    max_flat_range: float
    max_flat_net_improvement: float
    unstable_violation_rate: float
    unstable_late_variance: float
    collapse_delta: float
    rules_version: str
    fail_on_missing_fields: bool
    allow_unclassified: bool
    pretty: bool
    verbose: bool
    dry_run: bool
    exp_id: str | None
    status: str | None
    execution_mode: str | None


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(val, hi))


def get_nested(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> CLIArgs:
    parser = argparse.ArgumentParser(
        description="Classify TM4 experiment runs into semantic outcome classes."
    )

    input_group = parser.add_argument_group("input")
    input_group.add_argument("--input-json", type=Path, help="Path to aggregate results.json")
    input_group.add_argument("--input-csv", type=Path, help="Path to aggregate results.csv")
    input_group.add_argument("--run-dir", type=Path, help="Path to a single run directory")
    input_group.add_argument(
        "--input-format",
        choices=["auto", "json", "csv", "run-dir"],
        default="auto",
        help="Override input format detection",
    )

    output_group = parser.add_argument_group("output")
    output_group.add_argument("--output-json", type=Path, help="Path to classified JSON output")
    output_group.add_argument("--output-csv", type=Path, help="Path to classified CSV output")
    output_group.add_argument("--summary-json", type=Path, help="Path to classification summary JSON")
    output_group.add_argument(
        "--in-place",
        action="store_true",
        help="Enrich existing JSON output path in place when supported",
    )

    thresholds_group = parser.add_argument_group("thresholds")
    thresholds_group.add_argument("--success-threshold", type=float, default=100.0)
    thresholds_group.add_argument("--saturation-threshold", type=float, default=95.0)
    thresholds_group.add_argument("--min-meaningful-improvement", type=float, default=10.0)
    thresholds_group.add_argument("--max-flat-range", type=float, default=3.0)
    thresholds_group.add_argument("--max-flat-net-improvement", type=float, default=5.0)
    thresholds_group.add_argument("--unstable-violation-rate", type=float, default=0.05)
    thresholds_group.add_argument("--unstable-late-variance", type=float, default=20.0)
    thresholds_group.add_argument("--collapse-delta", type=float, default=10.0)

    behavior_group = parser.add_argument_group("behavior")
    behavior_group.add_argument("--rules-version", default=RULES_VERSION_DEFAULT)
    behavior_group.add_argument("--fail-on-missing-fields", action="store_true")
    behavior_group.add_argument("--allow-unclassified", action="store_true")
    behavior_group.add_argument("--pretty", action="store_true")
    behavior_group.add_argument("--verbose", action="store_true")
    behavior_group.add_argument("--dry-run", action="store_true")

    filter_group = parser.add_argument_group("filters")
    filter_group.add_argument("--exp-id", help="Only classify a specific exp_id")
    filter_group.add_argument("--status", help="Only classify rows matching status")
    filter_group.add_argument("--execution-mode", help="Only classify rows matching execution_mode")

    ns = parser.parse_args(argv)

    return CLIArgs(
        input_json=ns.input_json,
        input_csv=ns.input_csv,
        run_dir=ns.run_dir,
        input_format=ns.input_format,
        output_json=ns.output_json,
        output_csv=ns.output_csv,
        summary_json=ns.summary_json,
        in_place=ns.in_place,
        success_threshold=ns.success_threshold,
        saturation_threshold=ns.saturation_threshold,
        min_meaningful_improvement=ns.min_meaningful_improvement,
        max_flat_range=ns.max_flat_range,
        max_flat_net_improvement=ns.max_flat_net_improvement,
        unstable_violation_rate=ns.unstable_violation_rate,
        unstable_late_variance=ns.unstable_late_variance,
        collapse_delta=ns.collapse_delta,
        rules_version=ns.rules_version,
        fail_on_missing_fields=ns.fail_on_missing_fields,
        allow_unclassified=ns.allow_unclassified,
        pretty=ns.pretty,
        verbose=ns.verbose,
        dry_run=ns.dry_run,
        exp_id=ns.exp_id,
        status=ns.status,
        execution_mode=ns.execution_mode,
    )


def build_threshold_config(args: CLIArgs) -> ThresholdConfig:
    return ThresholdConfig(
        success_threshold=args.success_threshold,
        saturation_threshold=args.saturation_threshold,
        min_meaningful_improvement=args.min_meaningful_improvement,
        max_flat_range=args.max_flat_range,
        max_flat_net_improvement=args.max_flat_net_improvement,
        unstable_violation_rate=args.unstable_violation_rate,
        unstable_late_variance=args.unstable_late_variance,
        collapse_delta=args.collapse_delta,
    )


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def detect_input_format(args: CLIArgs) -> str:
    if args.input_format != "auto":
        return args.input_format
    if args.input_json is not None:
        return "json"
    if args.input_csv is not None:
        return "csv"
    if args.run_dir is not None:
        return "run-dir"
    raise ValueError("No input source provided. Use --input-json, --input-csv, or --run-dir.")


def load_runs(args: CLIArgs) -> list[RunRecord]:
    input_format = detect_input_format(args)

    if input_format == "json":
        if args.input_json is None:
            raise ValueError("--input-json is required for input-format=json")
        return load_runs_from_json(args.input_json)

    if input_format == "csv":
        if args.input_csv is None:
            raise ValueError("--input-csv is required for input-format=csv")
        return load_runs_from_csv(args.input_csv)

    if input_format == "run-dir":
        if args.run_dir is None:
            raise ValueError("--run-dir is required for input-format=run-dir")
        return [load_single_run_from_dir(args.run_dir)]

    raise ValueError(f"Unsupported input format: {input_format}")


def load_runs_from_json(path: Path) -> list[RunRecord]:
    LOGGER.info("Loading runs from JSON: %s", path)
    # Use utf-8-sig to handle Windows BOMs
    data = json.loads(path.read_text(encoding="utf-8-sig"))

    if isinstance(data, list):
        runs = data
    elif isinstance(data, dict):
        if isinstance(data.get("runs"), list):
            runs = data["runs"]
        # Compatibility with current aggregate structure
        elif isinstance(data.get("rows"), list):
            runs = data["rows"]
        else:
            raise ValueError("JSON input must be a list of runs or a dict with key 'runs' or 'rows'.")
    else:
        raise ValueError("JSON input has unsupported top-level structure.")

    return [RunRecord(raw=dict(item)) for item in runs if isinstance(item, dict)]


def load_runs_from_csv(path: Path) -> list[RunRecord]:
    LOGGER.info("Loading runs from CSV: %s", path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [RunRecord(raw=dict(row)) for row in reader]


def load_single_run_from_dir(run_dir: Path) -> RunRecord:
    summary_path = run_dir / "run_summary.json"
    LOGGER.info("Loading single run from directory: %s", run_dir)
    if not summary_path.exists():
        raise FileNotFoundError(f"run_summary.json not found in {run_dir}")
    data = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("run_summary.json must contain a JSON object.")
    return RunRecord(raw=dict(data))


def apply_filters(runs: list[RunRecord], args: CLIArgs) -> list[RunRecord]:
    filtered = runs

    if args.exp_id:
        filtered = [r for r in filtered if r.exp_id == args.exp_id]

    if args.status:
        filtered = [r for r in filtered if str(r.raw.get("status", "")).strip() == args.status]

    if args.execution_mode:
        filtered = [
            r for r in filtered
            if str(r.raw.get("execution_mode", "")).strip() == args.execution_mode
        ]

    return filtered


# ---------------------------------------------------------------------------
# Metrics extraction and derivation
# ---------------------------------------------------------------------------

def extract_fitness_series(run_data: dict[str, Any]) -> list[float]:
    """
    Best-effort fitness series extraction from a run summary dictionary.
    """
    direct_series = run_data.get("best_fitness_by_gen")
    if isinstance(direct_series, list):
        return [float(x) for x in direct_series if safe_float(x) is not None]

    generation_summaries = run_data.get("generation_summaries")
    if isinstance(generation_summaries, list):
        series: list[float] = []
        for item in generation_summaries:
            if not isinstance(item, dict):
                continue
            value = safe_float(item.get("best_fitness"))
            if value is not None:
                series.append(value)
        if series:
            return series

    return []


def compute_data_completeness(run: RunRecord, metrics: ClassificationMetrics) -> float:
    required = [
        metrics.fitness_max,
        metrics.fitness_min,
        metrics.generation_count,
        metrics.violations,
    ]
    optional = [
        metrics.gen0_best,
        metrics.final_best,
        metrics.net_improvement,
        metrics.early_variance,
        metrics.late_variance,
        metrics.improvement_density,
        metrics.monotonicity_ratio,
        metrics.collapse_count,
    ]
    total_slots = len(required) + len(optional)
    present = sum(value is not None for value in required + optional)
    return round(present / total_slots, 4) if total_slots else 1.0


def compute_derived_metrics(run: RunRecord, thresholds: ThresholdConfig) -> ClassificationMetrics:
    raw = run.raw
    series = extract_fitness_series(run)

    fitness_max = safe_float(raw.get("fitness_max"))
    fitness_min = safe_float(raw.get("fitness_min"))
    fitness_mean = safe_float(raw.get("fitness_mean"))
    fitness_std = safe_float(raw.get("fitness_std"))
    generation_count = safe_int(raw.get("generation_count"))
    if generation_count is None:
        # Fallback to 'generations' key if using old ledger
        generation_count = safe_int(raw.get("generations"))

    ttc = safe_int(raw.get("ttc"))
    violations = safe_int(raw.get("violations"))
    violation_rate = safe_float(raw.get("violation_rate"))
    invalid_candidate_rate = safe_float(raw.get("invalid_candidate_rate"))

    gen0_best = safe_float(raw.get("gen0_best"))
    final_best = safe_float(raw.get("final_best"))
    improvement_density = safe_float(raw.get("improvement_density"))
    monotonicity_ratio = safe_float(raw.get("monotonicity_ratio"))
    collapse_count = safe_int(raw.get("collapse_count"))
    early_variance = safe_float(raw.get("early_variance"))
    late_variance = safe_float(raw.get("late_variance"))

    if series:
        if gen0_best is None:
            gen0_best = series[0]
        if final_best is None:
            final_best = series[-1]
        if generation_count is None:
            generation_count = len(series)
        if fitness_max is None:
            fitness_max = max(series)
        if fitness_min is None:
            fitness_min = min(series)
        if fitness_mean is None:
            fitness_mean = sum(series) / len(series)
        if fitness_std is None:
            mean_val = sum(series) / len(series)
            fitness_std = math.sqrt(sum((x - mean_val) ** 2 for x in series) / len(series))

        early, late = split_early_late(series)
        if early_variance is None:
            early_variance = variance(early)
        if late_variance is None:
            late_variance = variance(late)

        if improvement_density is None and len(series) > 1:
            new_highs = 0
            running_high = series[0]
            for value in series[1:]:
                if value > running_high:
                    new_highs += 1
                    running_high = value
            improvement_density = new_highs / max(1, len(series) - 1)

        if monotonicity_ratio is None and len(series) > 1:
            non_decreasing_steps = sum(1 for i in range(1, len(series)) if series[i] >= series[i - 1])
            monotonicity_ratio = non_decreasing_steps / (len(series) - 1)

        if collapse_count is None and len(series) > 1:
            collapse_count = sum(
                1 for i in range(1, len(series))
                if (series[i - 1] - series[i]) >= thresholds.collapse_delta
            )

    if violation_rate is None and violations is not None and generation_count and generation_count > 0:
        violation_rate = violations / generation_count

    net_improvement = None
    if gen0_best is not None and final_best is not None:
        net_improvement = final_best - gen0_best

    fitness_range = None
    if fitness_max is not None and fitness_min is not None:
        fitness_range = fitness_max - fitness_min

    late_stability_ratio = None
    if early_variance is not None and late_variance is not None:
        late_stability_ratio = early_variance / max(late_variance, EPSILON)

    reached_success = None
    if fitness_max is not None:
        reached_success = fitness_max >= thresholds.success_threshold

    near_ceiling_start = None
    if gen0_best is not None:
        near_ceiling_start = gen0_best >= thresholds.saturation_threshold

    flatness_flag = None
    if fitness_range is not None and net_improvement is not None:
        flatness_flag = (
            fitness_range <= thresholds.max_flat_range
            and abs(net_improvement) <= thresholds.max_flat_net_improvement
        )

    instability_flag = None
    instability_conditions: list[bool] = []
    if violation_rate is not None:
        instability_conditions.append(violation_rate > thresholds.unstable_violation_rate)
    if late_variance is not None:
        instability_conditions.append(late_variance >= thresholds.unstable_late_variance)
    if collapse_count is not None:
        instability_conditions.append(collapse_count >= 2)
    if fitness_std is not None:
        instability_conditions.append(fitness_std >= thresholds.unstable_fitness_std)
    instability_flag = any(instability_conditions) if instability_conditions else None

    metrics = ClassificationMetrics(
        gen0_best=gen0_best,
        final_best=final_best,
        net_improvement=net_improvement,
        fitness_max=fitness_max,
        fitness_min=fitness_min,
        fitness_mean=fitness_mean,
        fitness_std=fitness_std,
        fitness_range=fitness_range,
        generation_count=generation_count,
        ttc=ttc,
        violations=violations,
        violation_rate=violation_rate,
        invalid_candidate_rate=invalid_candidate_rate,
        early_variance=early_variance,
        late_variance=late_variance,
        late_stability_ratio=late_stability_ratio,
        improvement_density=improvement_density,
        monotonicity_ratio=monotonicity_ratio,
        collapse_count=collapse_count,
        reached_success=reached_success,
        near_ceiling_start=near_ceiling_start,
        flatness_flag=flatness_flag,
        instability_flag=instability_flag,
    )
    metrics.data_completeness = compute_data_completeness(run, metrics)
    return metrics


# ---------------------------------------------------------------------------
# Classification rule helpers
# ---------------------------------------------------------------------------

def is_failed_execution(run: RunRecord, metrics: ClassificationMetrics) -> tuple[bool, list[str], str]:
    status = run.status.lower()

    if status and status != "success":
        return True, ["failed.status_non_success"], f"Run status was {run.status!r}, not 'success'."

    if metrics.generation_count == 0:
        return True, ["failed.zero_generations"], "Generation count was 0, indicating failed execution."

    return False, [], ""


def is_saturated(metrics: ClassificationMetrics, thresholds: ThresholdConfig) -> tuple[bool, list[str], str]:
    triggered: list[str] = []

    strong_start = (
        metrics.gen0_best is not None
        and metrics.gen0_best >= thresholds.saturation_threshold
        and metrics.net_improvement is not None
        and metrics.net_improvement <= thresholds.max_flat_net_improvement
    )
    early_ceiling = (
        metrics.ttc is not None
        and metrics.ttc <= thresholds.max_ttc_for_saturation
        and metrics.fitness_range is not None
        and metrics.fitness_range <= thresholds.max_flat_range
    )
    persistent_ceiling = (
        metrics.fitness_mean is not None
        and metrics.fitness_mean >= thresholds.saturation_threshold
        and metrics.fitness_range is not None
        and metrics.fitness_range <= thresholds.max_flat_range
    )

    if strong_start:
        triggered.append("saturated.near_ceiling_start")
    if early_ceiling:
        triggered.append("saturated.early_ceiling")
    if persistent_ceiling:
        triggered.append("saturated.persistent_ceiling")

    if triggered:
        reason = (
            f"Run appears saturated: gen0_best={metrics.gen0_best}, "
            f"ttc={metrics.ttc}, fitness_range={metrics.fitness_range}, "
            f"net_improvement={metrics.net_improvement}."
        )
        return True, triggered, reason

    return False, [], ""


def is_unstable(metrics: ClassificationMetrics, thresholds: ThresholdConfig) -> tuple[bool, list[str], str]:
    triggered: list[str] = []

    if metrics.violation_rate is not None and metrics.violation_rate > thresholds.unstable_violation_rate:
        triggered.append("unstable.violation_rate")

    if metrics.late_variance is not None and metrics.late_variance >= thresholds.unstable_late_variance:
        triggered.append("unstable.late_variance")

    if metrics.collapse_count is not None and metrics.collapse_count >= 2:
        triggered.append("unstable.repeated_collapse")

    if (
        metrics.net_improvement is not None
        and metrics.net_improvement >= thresholds.min_meaningful_improvement
        and metrics.early_variance is not None
        and metrics.late_variance is not None
        and metrics.late_variance > metrics.early_variance
    ):
        triggered.append("unstable.late_variance_expansion")

    if triggered:
        reason = (
            f"Run appears unstable: violation_rate={metrics.violation_rate}, "
            f"late_variance={metrics.late_variance}, collapse_count={metrics.collapse_count}."
        )
        return True, triggered, reason

    return False, [], ""


def is_convergent(metrics: ClassificationMetrics, thresholds: ThresholdConfig) -> tuple[bool, list[str], str]:
    triggered: list[str] = []

    if metrics.generation_count is None or metrics.generation_count < thresholds.min_generations_for_convergence:
        return False, [], ""

    if metrics.net_improvement is None or metrics.net_improvement < thresholds.min_meaningful_improvement:
        return False, [], ""

    triggered.append("convergent.meaningful_improvement")

    success_evidence = False
    if metrics.reached_success:
        success_evidence = True
        triggered.append("convergent.reached_success")
    if (
        metrics.improvement_density is not None
        and metrics.improvement_density >= thresholds.min_improvement_density_for_convergent
    ):
        success_evidence = True
        triggered.append("convergent.improvement_density")
    if (
        metrics.monotonicity_ratio is not None
        and metrics.monotonicity_ratio >= thresholds.min_monotonicity_ratio_for_convergent
    ):
        triggered.append("convergent.monotonicity")

    stabilization_evidence = False
    if (
        metrics.early_variance is not None
        and metrics.late_variance is not None
        and metrics.late_variance <= metrics.early_variance
    ):
        stabilization_evidence = True
        triggered.append("convergent.stabilized")

    if (
        metrics.violation_rate is not None
        and metrics.violation_rate <= thresholds.max_violation_rate_for_convergent
    ):
        triggered.append("convergent.zero_or_acceptable_violations")

    if not success_evidence:
        return False, [], ""

    if not stabilization_evidence and (
        metrics.monotonicity_ratio is None
        or metrics.monotonicity_ratio < thresholds.min_monotonicity_ratio_for_convergent
    ):
        return False, [], ""

    reason = (
        f"Best fitness improved from {metrics.gen0_best} to {metrics.final_best} "
        f"over {metrics.generation_count} generations with "
        f"late_variance={metrics.late_variance} and violation_rate={metrics.violation_rate}."
    )
    return True, triggered, reason


def is_no_gradient(metrics: ClassificationMetrics, thresholds: ThresholdConfig) -> tuple[bool, list[str], str]:
    triggered: list[str] = []

    low_improvement = (
        metrics.net_improvement is not None
        and metrics.net_improvement < thresholds.min_meaningful_improvement
    )
    flat_range = (
        metrics.fitness_range is not None
        and metrics.fitness_range <= thresholds.max_flat_range
    )
    low_density = (
        metrics.improvement_density is not None
        and metrics.improvement_density < thresholds.min_improvement_density_for_convergent
    )
    below_success = (
        metrics.fitness_max is not None
        and metrics.fitness_max < thresholds.success_threshold
    )

    if low_improvement:
        triggered.append("no_gradient.low_net_improvement")
    if flat_range:
        triggered.append("no_gradient.flat_range")
    if low_density:
        triggered.append("no_gradient.low_improvement_density")
    if below_success:
        triggered.append("no_gradient.below_success_threshold")

    if low_improvement and (flat_range or low_density):
        reason = (
            f"Run shows no meaningful gradient: net_improvement={metrics.net_improvement}, "
            f"fitness_range={metrics.fitness_range}, improvement_density={metrics.improvement_density}."
        )
        return True, triggered, reason

    return False, [], ""


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def compute_confidence(
    classification: str,
    triggered_rules: list[str],
    metrics: ClassificationMetrics,
) -> float:
    base_scores = {
        "FAILED_EXECUTION": 0.98,
        "SATURATED": 0.90,
        "UNSTABLE": 0.84,
        "CONVERGENT": 0.86,
        "NO_GRADIENT": 0.82,
        "UNCLASSIFIED": 0.40,
    }
    base = base_scores.get(classification, 0.50)

    completeness_bonus = 0.10 * float(metrics.data_completeness or 0.0)
    rule_bonus = min(0.08, 0.02 * len(triggered_rules))

    ambiguity_penalty = 0.0
    if classification == "UNCLASSIFIED":
        ambiguity_penalty = 0.05

    return round(clamp(base + completeness_bonus + rule_bonus - ambiguity_penalty, 0.0, 1.0), 4)


# ---------------------------------------------------------------------------
# Classification engine
# ---------------------------------------------------------------------------

def classify_run(
    run: RunRecord,
    thresholds: ThresholdConfig,
    rules_version: str,
    fail_on_missing_fields: bool = False,
) -> ClassificationResult:
    metrics = compute_derived_metrics(run, thresholds)
    
    backfill_mode = "none"
    if extract_fitness_series(run):
        backfill_mode = "full_series"
    elif metrics.gen0_best is not None or metrics.final_best is not None:
        backfill_mode = "heuristic"

    if fail_on_missing_fields:
        required_missing = []
        if metrics.fitness_max is None:
            required_missing.append("fitness_max")
        if metrics.fitness_min is None:
            required_missing.append("fitness_min")
        if metrics.generation_count is None:
            required_missing.append("generation_count")
        if required_missing:
            raise ValueError(
                f"Run {run.exp_id} missing required fields: {', '.join(required_missing)}"
            )

    failed, rules, reason = is_failed_execution(run, metrics)
    if failed:
        classification = "FAILED_EXECUTION"
        return ClassificationResult(
            classification=classification,
            confidence=compute_confidence(classification, rules, metrics),
            reason=reason,
            rules_version=rules_version,
            triggered_rules=rules,
            metrics=metrics,
            backfill_mode=backfill_mode,
            thresholds=asdict(thresholds),
        )

    saturated, rules, reason = is_saturated(metrics, thresholds)
    if saturated:
        classification = "SATURATED"
        return ClassificationResult(
            classification=classification,
            confidence=compute_confidence(classification, rules, metrics),
            reason=reason,
            rules_version=rules_version,
            triggered_rules=rules,
            metrics=metrics,
            backfill_mode=backfill_mode,
            thresholds=asdict(thresholds),
        )

    unstable, rules, reason = is_unstable(metrics, thresholds)
    if unstable:
        classification = "UNSTABLE"
        return ClassificationResult(
            classification=classification,
            confidence=compute_confidence(classification, rules, metrics),
            reason=reason,
            rules_version=rules_version,
            triggered_rules=rules,
            metrics=metrics,
            backfill_mode=backfill_mode,
            thresholds=asdict(thresholds),
        )

    convergent, rules, reason = is_convergent(metrics, thresholds)
    if convergent:
        classification = "CONVERGENT"
        return ClassificationResult(
            classification=classification,
            confidence=compute_confidence(classification, rules, metrics),
            reason=reason,
            rules_version=rules_version,
            triggered_rules=rules,
            metrics=metrics,
            backfill_mode=backfill_mode,
            thresholds=asdict(thresholds),
        )

    no_gradient, rules, reason = is_no_gradient(metrics, thresholds)
    if no_gradient:
        classification = "NO_GRADIENT"
        return ClassificationResult(
            classification=classification,
            confidence=compute_confidence(classification, rules, metrics),
            reason=reason,
            rules_version=rules_version,
            triggered_rules=rules,
            metrics=metrics,
            backfill_mode=backfill_mode,
            thresholds=asdict(thresholds),
        )

    classification = "UNCLASSIFIED"
    rules = ["unclassified.insufficient_or_ambiguous_signal"]
    reason = "Insufficient or ambiguous evidence to classify run confidently."
    return ClassificationResult(
        classification=classification,
        confidence=compute_confidence(classification, rules, metrics),
        reason=reason,
        rules_version=rules_version,
        triggered_rules=rules,
        metrics=metrics,
        backfill_mode=backfill_mode,
        thresholds=asdict(thresholds),
    )


def enrich_run_record(run: RunRecord, result: ClassificationResult) -> dict[str, Any]:
    enriched = run.to_dict()
    enriched["classification_analysis"] = {
        "classification": result.classification,
        "confidence": result.confidence,
        "reason": result.reason,
        "rules_version": result.rules_version,
        "triggered_rules": result.triggered_rules,
        "metrics": asdict(result.metrics),
        "backfill_mode": result.backfill_mode,
        "thresholds": result.thresholds,
        "classified_at": result.classified_at,
    }
    return enriched


def classify_runs(
    runs: list[RunRecord],
    thresholds: ThresholdConfig,
    rules_version: str,
    fail_on_missing_fields: bool = False,
) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []

    for run in runs:
        result = classify_run(
            run=run,
            thresholds=thresholds,
            rules_version=rules_version,
            fail_on_missing_fields=fail_on_missing_fields,
        )
        LOGGER.info(
            "Classified %s as %s (%.2f)",
            run.exp_id,
            result.classification,
            result.confidence,
        )
        classified.append(enrich_run_record(run, result))

    return classified


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any, pretty: bool = False) -> None:
    ensure_parent_dir(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2 if pretty else None, ensure_ascii=False)
        handle.write("\n")


def flatten_classified_record(record: dict[str, Any]) -> dict[str, Any]:
    output = dict(record)

    analysis = output.pop("classification_analysis", {}) or {}
    metrics = analysis.get("metrics", {}) or {}

    output["classification"] = analysis.get("classification")
    output["classification_confidence"] = analysis.get("confidence")
    output["classification_reason"] = analysis.get("reason")
    output["classification_rules_version"] = analysis.get("rules_version")
    output["classification_triggered_rules"] = "|".join(analysis.get("triggered_rules", []))

    for key, value in metrics.items():
        output[key] = value

    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent_dir(path)

    flattened = [flatten_classified_record(row) for row in rows]
    fieldnames: list[str] = []
    for row in flattened:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in flattened:
            writer.writerow(row)


def build_summary(classified_runs: list[dict[str, Any]], rules_version: str) -> ClassificationSummary:
    counts: dict[str, int] = {}
    for row in classified_runs:
        analysis = row.get("classification_analysis", {}) or {}
        label = str(analysis.get("classification", "UNCLASSIFIED"))
        counts[label] = counts.get(label, 0) + 1

    return ClassificationSummary(
        rules_version=rules_version,
        generated_at=utc_now_iso(),
        total_runs=len(classified_runs),
        counts=counts,
    )


def write_outputs(
    classified_runs: list[dict[str, Any]],
    args: CLIArgs,
    input_format: str,
) -> None:
    if args.dry_run:
        LOGGER.info("Dry run enabled; no files written.")
        return

    if args.output_json:
        write_json(args.output_json, classified_runs, pretty=args.pretty)
        LOGGER.info("Wrote JSON output: %s", args.output_json)

    if args.output_csv:
        write_csv(args.output_csv, classified_runs)
        LOGGER.info("Wrote CSV output: %s", args.output_csv)

    if args.summary_json:
        summary = build_summary(classified_runs, args.rules_version)
        write_json(args.summary_json, asdict(summary), pretty=args.pretty)
        LOGGER.info("Wrote summary JSON: %s", args.summary_json)

    if args.in_place and input_format == "json" and args.input_json:
        write_json(args.input_json, classified_runs, pretty=args.pretty)
        LOGGER.info("Updated input JSON in place: %s", args.input_json)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        input_format = detect_input_format(args)
        thresholds = build_threshold_config(args)

        runs = load_runs(args)
        runs = apply_filters(runs, args)

        if not runs:
            LOGGER.warning("No valid runs found after loading/filtering.")
            return EXIT_NO_VALID_RUNS

        LOGGER.info("Loaded %d run(s) for classification.", len(runs))

        classified_runs = classify_runs(
            runs=runs,
            thresholds=thresholds,
            rules_version=args.rules_version,
            fail_on_missing_fields=args.fail_on_missing_fields,
        )

        write_outputs(classified_runs, args, input_format)

        unclassified_count = sum(
            1
            for row in classified_runs
            if get_nested(row, "classification_analysis", "classification") == "UNCLASSIFIED"
        )

        if unclassified_count > 0 and not args.allow_unclassified:
            LOGGER.warning("Classification completed with %d UNCLASSIFIED run(s).", unclassified_count)
            return EXIT_HAS_UNCLASSIFIED

        return EXIT_OK

    except FileNotFoundError as exc:
        LOGGER.error("File not found: %s", exc)
        return EXIT_FATAL_IO
    except json.JSONDecodeError as exc:
        LOGGER.error("Invalid JSON: %s", exc)
        return EXIT_SCHEMA_ERROR
    except ValueError as exc:
        LOGGER.error("Validation error: %s", exc)
        return EXIT_SCHEMA_ERROR
    except OSError as exc:
        LOGGER.error("I/O error: %s", exc)
        return EXIT_FATAL_IO


if __name__ == "__main__":
    sys.exit(main())
