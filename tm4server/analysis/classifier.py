from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from tm4server.utils import extract_fitness_series, safe_float, safe_int, variance, split_early_late

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

class ExperimentClassifier:
    """
    TM4 Deterministic Scientific Classifier (v1)
    
    Converts raw experiment artifacts (summaries) into semantic scientific labels.
    Decoupled from execution; pure interpretation layer.
    """
    VERSION = "v1"
    EPSILON = 1e-9

    def __init__(self, thresholds: Dict[str, float] | None = None):
        # Default thresholds
        self.thresholds = {
            "saturation_threshold": 0.95,
            "min_meaningful_improvement": 0.15,
            "min_improvement_density": 0.4,
            "max_flat_improvement": 0.02,
            "max_flat_range": 0.05,
            "unstable_violation_rate": 0.10,
            "stability_variance_ratio": 2.0, # early / late must be >= 2.0 for stabilization signal
            "absolute_instability_threshold": 5.0, # late_v > 5.0 is objectively noisy
        }
        if thresholds:
            self.thresholds.update(thresholds)

    def classify(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assigns a semantic label to the run based on strict first-match logic.
        Returns a structurally self-describing wrapper.
        """
        exp_id = summary.get("exp_id", "unknown")
        metrics = summary.get("metrics", {})
        status = summary.get("status", "unknown")
        
        # 1. Extract/Derive Metrics
        series = extract_fitness_series(summary)
        gen0_best = safe_float(metrics.get("gen0_best"))
        final_best = safe_float(metrics.get("final_best"))
        generations = safe_int(metrics.get("generations"))
        
        # Fallbacks for missing summary fields
        if series:
            if gen0_best is None: gen0_best = series[0]
            if final_best is None: final_best = series[-1]
            if generations is None: generations = len(series)

        net_improvement = (final_best - gen0_best) if (gen0_best is not None and final_best is not None) else 0.0
        fitness_min = safe_float(metrics.get("fitness_min"))
        fitness_max = safe_float(metrics.get("fitness_max"))
        fitness_range = (fitness_max - fitness_min) if (fitness_max is not None and fitness_min is not None) else 0.0
        
        violation_rate = safe_float(metrics.get("violation_rate", 0.0)) or 0.0
        collapse_count = safe_int(metrics.get("collapse_count", 0)) or 0
        
        early_v = 0.0
        late_v = 0.0
        if series:
            early, late = split_early_late(series)
            early_v = variance(early) or 0.0
            late_v = variance(late) or 0.0

        improvement_density = 0.0
        if series and len(series) > 1:
            new_highs = 0
            running_high = series[0]
            for val in series[1:]:
                if val > running_high:
                    new_highs += 1
                    running_high = val
            improvement_density = new_highs / (len(series) - 1)

        # 2. Evidence Block
        evidence = {
            "net_improvement": round(net_improvement, 3),
            "improvement_density": round(improvement_density, 3),
            "early_variance": round(early_v, 6),
            "late_variance": round(late_v, 6),
            "violation_rate": round(violation_rate, 3),
            "generations": generations,
            "fitness_range": round(fitness_range, 3),
            "data_points": len(series)
        }

        # 3. Rule Cascade (First-Match)
        label = "UNCLASSIFIED"
        reason = "Insufficient evidence to assign a confident label."
        confidence = 0.4 

        # RULE 1: EXECUTION_FAILURE
        if status not in ["completed", "success"] or generations == 0:
            label = "EXECUTION_FAILURE"
            reason = f"Run status is terminal but non-successful ({status}) or zero generations recorded."
            confidence = 1.0

        # RULE 2: SATURATED
        elif gen0_best is not None and gen0_best >= self.thresholds["saturation_threshold"]:
            label = "SATURATED"
            reason = f"Run reached performance ceiling ({round(gen0_best, 3)}) immediately at Generation 0."
            confidence = 0.9

        # RULE 3: UNSTABLE
        elif (violation_rate > self.thresholds["unstable_violation_rate"] or 
              collapse_count > 0 or 
              late_v > self.thresholds["absolute_instability_threshold"] or
              (len(series) >= 10 and late_v > early_v * 1.5)):
            label = "UNSTABLE"
            reason = f"Run exhibited instability (Violations: {violation_rate}, Collapses: {collapse_count}, Late Variance: {round(late_v, 4)})."
            confidence = 0.85

        # RULE 4: CONVERGENT
        elif (net_improvement >= self.thresholds["min_meaningful_improvement"] and 
              improvement_density >= self.thresholds["min_improvement_density"]):
            
            # Stabilization requirement: late variance must be lower than early variance OR below stability ratio
            is_stabilized = (late_v < early_v) or (early_v / max(late_v, self.EPSILON) >= self.thresholds["stability_variance_ratio"])
            
            if is_stabilized:
                label = "CONVERGENT"
                confidence = 0.8 + (min(improvement_density, 1.0) * 0.1)
                reason = f"Meaningful directional improvement ({round(net_improvement, 3)}) with high signal density and stabilization."
            else:
                # Drift into UNSTABLE if improvement was high but noise increased
                label = "UNSTABLE"
                reason = "Meaningful improvement detected but failed stabilization requirement (late noise > early noise)."
                confidence = 0.7

        # RULE 5: SIGNAL_ABSENT (Flatline)
        elif abs(net_improvement) < self.thresholds["max_flat_improvement"] and fitness_range < self.thresholds["max_flat_range"]:
            label = "SIGNAL_ABSENT"
            reason = "Terminal run completed but no significant optimization signal was detected (flat fitness)."
            confidence = 0.8

        # FINAL: Confidence adjustment for low data
        if len(series) < 5 and label != "EXECUTION_FAILURE":
            confidence *= 0.5
            reason += " (Low confidence due to sparse data series)"

        return {
            "exp_id": exp_id,
            "source_summary_status": status,
            "classification": {
                "label": label,
                "version": self.VERSION,
                "confidence": round(confidence, 2),
                "evidence": evidence,
                "reason": reason,
                "classified_at": utc_now_iso()
            }
        }
