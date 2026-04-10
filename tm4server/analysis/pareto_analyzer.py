from typing import Any, Dict, List
from collections import defaultdict

class ParetoAnalyzer:
    """
    TM4 Model Pareto Analyzer (v1)
    
    Ranks models within each task based on a governance-first weighted composite score:
    - Optimization Power (35%)
    - Yield (25%)
    - Stability (20%)
    - Reliability (20%)
    
    Applies hard governance caps for risky regimes.
    """
    VERSION = "v1"
    
    # Weights for the composite score
    WEIGHTS = {
        "power": 0.35,
        "yield": 0.25,
        "stability": 0.20,
        "reliability": 0.20
    }
    
    # Governance Caps
    CAPS = {
        "FAILURE_PRONE": 0.45,
        "NOISY_REGIME": 0.60
    }

    def analyze_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a gradient report and returns a ranked Pareto comparison per task.
        """
        regimes = report.get("regimes", [])
        if not regimes:
            return {"version": self.VERSION, "tasks": {}}

        # 1. Group by Task
        task_groups = defaultdict(list)
        for r in regimes:
            task_groups[r["task"]].append(r)

        results = {}
        for task, task_regimes in task_groups.items():
            results[task] = self.process_task_cohort(task, task_regimes)

        return {
            "version": self.VERSION,
            "generated_at": report.get("generated_at"),
            "tasks": results
        }

    def process_task_cohort(self, task: str, regimes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Processes all model regimes for a single task.
        Performs cohort normalization for Power.
        """
        # Calculate Power cohort max for normalization
        max_power = max([r.get("mean_net_improvement", 0.0) for r in regimes] + [0.001])
        
        scored_regimes = []
        for r in regimes:
            # Axis 1: Optimization Power (normalized to best in task)
            raw_power = r.get("mean_net_improvement", 0.0)
            norm_power = raw_power / max_power
            
            # Axis 2: Yield (CONVERGENT ratio)
            counts = r.get("distribution_counts", {})
            total = r.get("run_count", 0)
            yield_score = counts.get("CONVERGENT", 0) / total if total > 0 else 0.0
            
            # Axis 3: Stability (1 - Unstable weighted share)
            # shares = weighted / total_weighted in GradientDetector
            dist_weighted = r.get("distribution_weighted", {})
            total_weighted = sum(dist_weighted.values())
            unstable_share = dist_weighted.get("UNSTABLE", 0.0) / total_weighted if total_weighted > 0 else 0.0
            stability_score = 1.0 - unstable_share
            
            # Axis 4: Reliability (1 - raw failure ratio)
            fail_count = counts.get("EXECUTION_FAILURE", 0)
            reliability_score = 1.0 - (fail_count / total if total > 0 else 0.0)
            
            # Calculate Base Composite
            base_score = (
                norm_power * self.WEIGHTS["power"] +
                yield_score * self.WEIGHTS["yield"] +
                stability_score * self.WEIGHTS["stability"] +
                reliability_score * self.WEIGHTS["reliability"]
            )
            
            # Apply Governance Penalties
            label = r.get("label", "UNCLASSIFIED")
            final_score = base_score
            penalty_applied = False
            
            if label in self.CAPS:
                if final_score > self.CAPS[label]:
                    final_score = self.CAPS[label]
                    penalty_applied = True
            
            is_provisional = label == "INSUFFICIENT_EVIDENCE"
            
            scored_regimes.append({
                "model": r["model"],
                "score": round(final_score, 3),
                "base_score": round(base_score, 3),
                "power": round(norm_power, 3),
                "yield": round(yield_score, 3),
                "stability": round(stability_score, 3),
                "reliability": round(reliability_score, 3),
                "label": label,
                "run_count": total,
                "is_provisional": is_provisional,
                "penalty_applied": penalty_applied,
                "reason": r.get("reason", "")
            })
            
        # Rank: non-provisional first, then by score desc
        # Provisional models stay at bottom
        scored_regimes.sort(key=lambda x: (not x["is_provisional"], x["score"]), reverse=True)
        
        return scored_regimes
