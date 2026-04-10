from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

class GradientDetector:
    """
    TM4 Cross-Run Gradient Detector (v1)
    
    Aggregates scientific classifications across an experiment regime (task/model)
    to detect optimization signals or failure patterns.
    """
    VERSION = "v1"

    def __init__(self, thresholds: Dict[str, float] | None = None):
        self.thresholds = {
            "min_runs_provisional": 3,
            "min_runs_high_confidence": 5,
            "failure_rate_threshold": 0.20,
            "saturated_weighted_threshold": 0.70,
            "signal_absent_weighted_threshold": 0.80,
            "unstable_weighted_threshold": 0.30,
            "convergent_weighted_threshold": 0.60,
            "confidence_floor": 0.60,
            "high_confidence_floor": 0.70,
        }
        if thresholds:
            self.thresholds.update(thresholds)

    def analyze_regime(self, task: str, model: str, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes a batch of runs for a specific regime.
        Input: List of classification objects.
        """
        regime_key = f"{task}__{model}"
        run_count = len(runs)
        
        # 1. Initialize distributions
        dist_counts: Dict[str, int] = {
            "EXECUTION_FAILURE": 0,
            "SATURATED": 0,
            "UNSTABLE": 0,
            "CONVERGENT": 0,
            "SIGNAL_ABSENT": 0,
            "UNCLASSIFIED": 0
        }
        dist_weighted: Dict[str, float] = {k: 0.0 for k in dist_counts.keys()}
        
        total_confidence = 0.0
        
        # 2. Aggregate
        for run in runs:
            # We assume 'run' is the 'classification' block from our schema
            label = run.get("label", "UNCLASSIFIED")
            confidence = run.get("confidence", 0.0)
            
            dist_counts[label] = dist_counts.get(label, 0) + 1
            dist_weighted[label] = dist_weighted.get(label, 0.0) + confidence
            total_confidence += confidence

        mean_confidence = total_confidence / run_count if run_count > 0 else 0.0
        
        # Calculate shares (weighted scores / total confidence)
        total_weighted_score = sum(dist_weighted.values())
        shares: Dict[str, float] = {}
        for k, v in dist_weighted.items():
            shares[k] = v / total_weighted_score if total_weighted_score > 0 else 0.0

        # Raw failure ratio
        raw_failure_ratio = dist_counts["EXECUTION_FAILURE"] / run_count if run_count > 0 else 0.0

        # 3. Rule Cascade (First-Match, Risk-First)
        label = "UNCLASSIFIED"
        reason = "Unable to determine stable regime pattern."

        # RULE 1: INSUFFICIENT_EVIDENCE
        if run_count < self.thresholds["min_runs_provisional"]:
            label = "INSUFFICIENT_EVIDENCE"
            reason = f"Regime has only {run_count} classified runs. Minimum {self.thresholds['min_runs_provisional']} required for detection."

        # RULE 2: FAILURE_PRONE
        elif raw_failure_ratio > self.thresholds["failure_rate_threshold"]:
            label = "FAILURE_PRONE"
            reason = f"High raw failure rate ({round(raw_failure_ratio * 100)}%) detected in this regime."

        # RULE 3: SATURATED_REGIME
        elif shares["SATURATED"] > self.thresholds["saturated_weighted_threshold"]:
            label = "SATURATED_REGIME"
            reason = "Regime is consistently reaching optimization ceiling immediately."

        # RULE 4: SIGNAL_ABSENT_REGIME
        elif shares["SIGNAL_ABSENT"] > self.thresholds["signal_absent_weighted_threshold"]:
            label = "SIGNAL_ABSENT_REGIME"
            reason = "No optimization gradient detected across the majority of runs (flat fitness)."

        # RULE 5: NOISY_REGIME
        elif shares["UNSTABLE"] > self.thresholds["unstable_weighted_threshold"] or mean_confidence < self.thresholds["confidence_floor"]:
            label = "NOISY_REGIME"
            reason = "Regime exhibited high variance or low mean confidence across evidence batch."

        # RULE 6: CONVERGENT_CLUSTER
        elif shares["CONVERGENT"] > self.thresholds["convergent_weighted_threshold"] and mean_confidence >= self.thresholds["high_confidence_floor"]:
            label = "CONVERGENT_CLUSTER"
            reason = "Majority convergent outcomes with high mean confidence, indicating a stable optimization signal."

        return {
            "regime_key": regime_key,
            "task": task,
            "model": model,
            "label": label,
            "mean_confidence": round(mean_confidence, 2),
            "run_count": run_count,
            "distribution_counts": dist_counts,
            "distribution_weighted": {k: round(v, 2) for k, v in dist_weighted.items()},
            "reason": reason,
            "version": self.VERSION,
            "analyzed_at": utc_now_iso()
        }

    def build_report(self, groupings: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Builds a full index of regimes.
        Input: Dictionary mapping (task, model) -> list of classification objects.
        """
        regimes = []
        for (task, model), classification_list in groupings.items():
            report = self.analyze_regime(task, model, classification_list)
            regimes.append(report)
            
        return {
            "gradient_version": self.VERSION,
            "generated_at": utc_now_iso(),
            "regimes": regimes
        }
