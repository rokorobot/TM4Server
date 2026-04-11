from __future__ import annotations

import json
import os
import socket
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


SUMMARY_SCHEMA_VERSION = "v1"
SUMMARY_GENERATOR_VERSION = "v1.1"


EXPECTED_ARTIFACTS = [
    "config.json",
    "event_log.jsonl",
    "run_manifest.json",
    "results.json",
    "status.json",
    "stdout.log",
    "stderr.log",
    "tm4_input_manifest.json",
]


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def dt_to_iso_z(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def safe_iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return

    try:
        with path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        yield payload
                except Exception:
                    continue
    except Exception:
        return


def git_rev_parse(repo_path: Optional[Path]) -> Optional[str]:
    if repo_path is None or not repo_path.exists():
        return None

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def detect_instance_id() -> str:
    return (
        os.environ.get("TM4_INSTANCE_ID")
        or os.environ.get("HOSTNAME")
        or socket.gethostname()
        or "unknown-instance"
    )


def detect_execution_mode() -> str:
    return os.environ.get("TM4_EXECUTION_MODE", "VPS")


def coerce_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def coerce_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def validate_summary_dict(payload: Dict[str, Any]) -> None:
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


@dataclass
class RunSummary:
    schema_version: str
    exp_id: str
    instance_id: str
    execution_mode: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_s: Optional[float]
    artifact_root: str
    tm4_version: Optional[str]
    tm4server_version: Optional[str]
    input: Dict[str, Any]
    artifacts: Dict[str, bool]
    metrics: Dict[str, Any]
    validation: Dict[str, Any]
    provenance: Dict[str, Any]
    warnings: list[str]


class RunSummaryExtractor:
    """
    Extracts a canonical run summary from a TM4 run artifact directory.
    """

    def __init__(
        self,
        run_dir: Path,
        tm4_core_repo: Optional[Path] = None,
        tm4server_repo: Optional[Path] = None,
    ) -> None:
        self.run_dir = run_dir.resolve()
        self.tm4_core_repo = tm4_core_repo.resolve() if tm4_core_repo else None
        self.tm4server_repo = tm4server_repo.resolve() if tm4server_repo else None

        self.config_path = self.run_dir / "config.json"
        self.event_log_path = self.run_dir / "event_log.jsonl"
        self.manifest_path = self.run_dir / "run_manifest.json"
        self.results_path = self.run_dir / "results.json"
        self.status_path = self.run_dir / "status.json"
        self.stdout_path = self.run_dir / "stdout.log"
        self.stderr_path = self.run_dir / "stderr.log"
        self.input_manifest_path = self.run_dir / "tm4_input_manifest.json"

        self.warnings: list[str] = []

    def extract(self) -> RunSummary:
        manifest = safe_read_json(self.manifest_path) or {}
        results = safe_read_json(self.results_path) or {}
        status_json = safe_read_json(self.status_path) or {}
        config = safe_read_json(self.config_path) or {}
        input_manifest = safe_read_json(self.input_manifest_path) or {}

        event_stats = self._extract_event_log_stats()
        timing = self._extract_timing(manifest, status_json, results, event_stats)
        metrics = self._extract_metrics(results, status_json, manifest, event_stats)
        status = self._extract_run_status(manifest, status_json, results, event_stats)
        validation = self._extract_validation(
            manifest, status_json, results, event_stats, status
        )

        exp_id = self._extract_exp_id(
            manifest=manifest,
            input_manifest=input_manifest,
            config=config,
            status_json=status_json,
            results=results,
        )
        if not exp_id:
            exp_id = self.run_dir.name
            self.warnings.append(
                "exp_id not found in artifacts; falling back to run directory name"
            )

        summary = RunSummary(
            schema_version=SUMMARY_SCHEMA_VERSION,
            exp_id=exp_id,
            instance_id=detect_instance_id(),
            execution_mode=detect_execution_mode(),
            status=status,
            started_at=dt_to_iso_z(timing["started_at"]),
            completed_at=dt_to_iso_z(timing["completed_at"]),
            duration_s=timing["duration_s"],
            artifact_root=str(self.run_dir),
            tm4_version=self._extract_tm4_version(
                manifest=manifest,
                input_manifest=input_manifest,
                config=config,
                results=results,
            ),
            tm4server_version=self._extract_tm4server_version(
                manifest=manifest,
                input_manifest=input_manifest,
                config=config,
                results=results,
            ),
            input={
                "config_path": str(self.config_path),
                "input_manifest_path": str(self.input_manifest_path),
            },
            artifacts={name: (self.run_dir / name).exists() for name in EXPECTED_ARTIFACTS},
            metrics=metrics,
            validation=validation,
            provenance={
                "summary_generated_at": utc_now_iso(),
                "summary_generator": "tm4server.run_summary",
                "summary_generator_version": SUMMARY_GENERATOR_VERSION,
            },
            warnings=self.warnings,
        )
        return summary

    def write(self, filename: str = "run_summary.json") -> Path:
        # Spec v1 Alignment: Summary extraction MUST use governed write
        summary = self.extract()
        payload = asdict(summary)
        
        from .execution import artifacts
        # Note: artifacts.write_summary handles atomic write, schema_version v1, 
        # and terminal status check.
        artifacts.write_summary(self.run_dir, payload)
        
        return self.run_dir / filename

    def _results_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        summary = results.get("summary")
        return summary if isinstance(summary, dict) else {}

    def _extract_exp_id(
        self,
        manifest: Dict[str, Any],
        input_manifest: Dict[str, Any],
        config: Dict[str, Any],
        status_json: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Optional[str]:
        results_summary = self._results_summary(results)
        return first_non_none(
            manifest.get("exp_id"),
            manifest.get("experiment_id"),
            manifest.get("run_id"),
            input_manifest.get("exp_id"),
            input_manifest.get("experiment_id"),
            input_manifest.get("run_id"),
            config.get("exp_id"),
            config.get("experiment_id"),
            config.get("run_id"),
            status_json.get("exp_id"),
            status_json.get("experiment_id"),
            results.get("exp_id"),
            results.get("experiment_id"),
            results_summary.get("exp_id"),
            results_summary.get("experiment_id"),
        )

    def _extract_tm4_version(
        self,
        manifest: Dict[str, Any],
        input_manifest: Dict[str, Any],
        config: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Optional[str]:
        results_summary = self._results_summary(results)
        return first_non_none(
            manifest.get("tm4_version"),
            manifest.get("tm4_git_hash"),
            input_manifest.get("tm4_version"),
            input_manifest.get("tm4_git_hash"),
            config.get("tm4_version"),
            config.get("tm4_git_hash"),
            results.get("tm4_version"),
            results.get("tm4_git_hash"),
            results_summary.get("tm4_version"),
            results_summary.get("tm4_git_hash"),
            git_rev_parse(self.tm4_core_repo),
        )

    def _extract_tm4server_version(
        self,
        manifest: Dict[str, Any],
        input_manifest: Dict[str, Any],
        config: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Optional[str]:
        results_summary = self._results_summary(results)
        return first_non_none(
            manifest.get("tm4server_version"),
            manifest.get("tm4server_git_hash"),
            input_manifest.get("tm4server_version"),
            input_manifest.get("tm4server_git_hash"),
            config.get("tm4server_version"),
            config.get("tm4server_git_hash"),
            results.get("tm4server_version"),
            results.get("tm4server_git_hash"),
            results_summary.get("tm4server_version"),
            results_summary.get("tm4server_git_hash"),
            git_rev_parse(self.tm4server_repo),
        )

    def _extract_event_log_stats(self) -> Dict[str, Any]:
        started_at: Optional[datetime] = None
        completed_at: Optional[datetime] = None
        generations: set[int] = set()
        fitness_values: list[float] = []
        violations = 0
        checkpoints = 0
        commits = 0
        ttc: Optional[int] = None
        terminal_status: Optional[str] = None

        for event in safe_iter_jsonl(self.event_log_path):
            ts = parse_iso8601(
                first_non_none(
                    event.get("ts"),
                    event.get("ts_utc"),
                    event.get("timestamp"),
                    event.get("time"),
                )
            )
            if ts:
                if started_at is None or ts < started_at:
                    started_at = ts
                if completed_at is None or ts > completed_at:
                    completed_at = ts

            event_type = str(
                first_non_none(event.get("event"), event.get("type"), "")
            ).lower()

            generation = coerce_int(
                first_non_none(event.get("generation"), event.get("gen"))
            )
            if generation is not None:
                generations.add(generation)

            fitness = coerce_float(
                first_non_none(
                    event.get("fitness"),
                    event.get("fitness_score"),
                    event.get("score"),
                    event.get("best_fitness"),
                )
            )
            if fitness is not None:
                fitness_values.append(fitness)

            if "violation" in event_type:
                violations += 1
            if "checkpoint" in event_type:
                checkpoints += 1
            if "commit" in event_type:
                commits += 1

            if ttc is None:
                candidate_ttc = self._extract_ttc_from_event(event)
                if candidate_ttc is not None:
                    ttc = candidate_ttc

            if event_type == "subprocess_completed":
                return_code = coerce_int(event.get("return_code"))
                if return_code == 0:
                    terminal_status = "success"
                elif return_code is not None:
                    terminal_status = "failed"
            elif event_type in {"run_completed", "completed", "success"}:
                terminal_status = "success"
            elif event_type in {"run_failed", "failed", "error", "preflight_failed"}:
                terminal_status = "failed"

        return {
            "started_at": started_at,
            "completed_at": completed_at,
            "generations": max(generations) if generations else None,
            "fitness_values": fitness_values,
            "violations": violations,
            "checkpoints": checkpoints,
            "commits": commits,
            "ttc": ttc,
            "terminal_status": terminal_status,
        }

    def _extract_ttc_from_event(self, event: Dict[str, Any]) -> Optional[int]:
        explicit = first_non_none(
            event.get("ttc"),
            event.get("time_to_convergence"),
            event.get("generations_to_first_100"),
        )
        explicit_int = coerce_int(explicit)
        if explicit_int is not None:
            return explicit_int

        generation = coerce_int(first_non_none(event.get("generation"), event.get("gen")))
        fitness = coerce_float(
            first_non_none(
                event.get("fitness"),
                event.get("fitness_score"),
                event.get("score"),
                event.get("best_fitness"),
            )
        )
        if generation is not None and fitness is not None and fitness >= 100.0:
            return generation

        return None

    def _extract_timing(
        self,
        manifest: Dict[str, Any],
        status_json: Dict[str, Any],
        results: Dict[str, Any],
        event_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        results_summary = self._results_summary(results)

        started_at = first_non_none(
            parse_iso8601(manifest.get("started_at")),
            parse_iso8601(status_json.get("started_at")),
            parse_iso8601(results.get("started_at")),
            parse_iso8601(results_summary.get("started_at")),
            event_stats.get("started_at"),
        )
        completed_at = first_non_none(
            parse_iso8601(manifest.get("completed_at")),
            parse_iso8601(status_json.get("completed_at")),
            parse_iso8601(results.get("completed_at")),
            parse_iso8601(results_summary.get("completed_at")),
            event_stats.get("completed_at"),
        )
        duration_s = coerce_float(
            first_non_none(
                manifest.get("duration_s"),
                status_json.get("duration_s"),
                results.get("duration_s"),
                results_summary.get("duration_s"),
            )
        )

        if duration_s is None and started_at and completed_at:
            duration_s = round((completed_at - started_at).total_seconds(), 3)

        return {
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_s": duration_s,
        }

    def _extract_metrics(
        self,
        results: Dict[str, Any],
        status_json: Dict[str, Any],
        manifest: Dict[str, Any],
        event_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        results_summary = self._results_summary(results)

        metrics_src: Dict[str, Any] = {}
        if isinstance(results.get("metrics"), dict):
            metrics_src = results["metrics"]
        elif isinstance(results_summary.get("metrics"), dict):
            metrics_src = results_summary["metrics"]

        fitness_values = list(event_stats.get("fitness_values", []))

        fitness_max = first_non_none(
            coerce_float(metrics_src.get("fitness_max")),
            coerce_float(results.get("fitness_max")),
            coerce_float(results_summary.get("fitness_max")),
            max(fitness_values) if fitness_values else None,
        )
        fitness_mean = first_non_none(
            coerce_float(metrics_src.get("fitness_mean")),
            coerce_float(results.get("fitness_mean")),
            coerce_float(results_summary.get("fitness_mean")),
            (sum(fitness_values) / len(fitness_values)) if fitness_values else None,
        )
        fitness_min = first_non_none(
            coerce_float(metrics_src.get("fitness_min")),
            coerce_float(results.get("fitness_min")),
            coerce_float(results_summary.get("fitness_min")),
            min(fitness_values) if fitness_values else None,
        )

        generations = first_non_none(
            coerce_int(metrics_src.get("generations")),
            coerce_int(results.get("generations")),
            coerce_int(results_summary.get("generations")),
            coerce_int(status_json.get("generation")),
            event_stats.get("generations"),
        )
        ttc = first_non_none(
            coerce_int(metrics_src.get("ttc")),
            coerce_int(results.get("ttc")),
            coerce_int(results_summary.get("ttc")),
            coerce_int(manifest.get("ttc")),
            event_stats.get("ttc"),
        )
        violations = first_non_none(
            coerce_int(metrics_src.get("violations")),
            coerce_int(results.get("violations")),
            coerce_int(results_summary.get("violations")),
            event_stats.get("violations"),
            0,
        )
        checkpoints = first_non_none(
            coerce_int(metrics_src.get("checkpoints")),
            coerce_int(results.get("checkpoints")),
            coerce_int(results_summary.get("checkpoints")),
            event_stats.get("checkpoints"),
            0,
        )
        commits = first_non_none(
            coerce_int(metrics_src.get("commits")),
            coerce_int(results.get("commits")),
            coerce_int(results_summary.get("commits")),
            event_stats.get("commits"),
            0,
        )

        return {
            "generations": generations,
            "fitness_max": fitness_max,
            "fitness_mean": round(fitness_mean, 3)
            if isinstance(fitness_mean, float)
            else fitness_mean,
            "fitness_min": fitness_min,
            "ttc": ttc,
            "violations": violations,
            "checkpoints": checkpoints,
            "commits": commits,
        }

    def _extract_validation(
        self,
        manifest: Dict[str, Any],
        status_json: Dict[str, Any],
        results: Dict[str, Any],
        event_stats: Dict[str, Any],
        run_status: str,
    ) -> Dict[str, Any]:
        results_summary = self._results_summary(results)

        results_validation = (
            results.get("validation") if isinstance(results.get("validation"), dict) else {}
        )
        results_summary_validation = (
            results_summary.get("validation")
            if isinstance(results_summary.get("validation"), dict)
            else {}
        )

        status = first_non_none(
            results.get("validation_status"),
            results_validation.get("status"),
            results_summary.get("validation_status"),
            results_summary_validation.get("status"),
            manifest.get("validation_status"),
            status_json.get("validation_status"),
        )
        reason = first_non_none(
            results.get("validation_reason"),
            results_validation.get("reason"),
            results_summary.get("validation_reason"),
            results_summary_validation.get("reason"),
            manifest.get("validation_reason"),
            status_json.get("validation_reason"),
        )

        if status is None:
            violations = event_stats.get("violations", 0)
            fitness_values = event_stats.get("fitness_values", [])
            max_fitness = max(fitness_values) if fitness_values else None

            if run_status == "failed":
                status = "INVALID"
                reason = "Run execution failed before successful completion."
            elif max_fitness is not None and max_fitness >= 100.0 and violations == 0:
                status = "VALID"
                reason = "First 100/100 achieved with zero detected governance violations."
            elif max_fitness is not None:
                status = "NO_GRADIENT"
                reason = "No convergent winning score detected in extracted artifacts."
            else:
                status = "UNKNOWN"
                reason = "Validation status could not be determined from available artifacts."

        return {
            "status": status,
            "reason": reason,
        }

    def _extract_run_status(
        self,
        manifest: Dict[str, Any],
        status_json: Dict[str, Any],
        results: Dict[str, Any],
        event_stats: Dict[str, Any],
    ) -> str:
        results_summary = self._results_summary(results)

        raw = first_non_none(
            manifest.get("status"),
            status_json.get("status"),
            results.get("status"),
            results_summary.get("status"),
            event_stats.get("terminal_status"),
        )

        if raw is None:
            if self.stderr_path.exists() and self.stderr_path.stat().st_size > 0:
                return "failed"
            return "unknown"

        mapping = {
            "ok": "success",
            "success": "success",
            "completed": "success",
            "done": "success",
            "failed": "failed",
            "error": "failed",
            "interrupted": "interrupted",
        }
        
        normalized = mapping.get(str(raw).strip().lower(), "failed")
        
        # Spec v1: Final summary must have terminal status
        if normalized not in {"success", "failed", "interrupted"}:
            return "failed"
            
        return normalized
