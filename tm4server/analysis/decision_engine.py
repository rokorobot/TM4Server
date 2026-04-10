from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

class DecisionEngine:
    """
    TM4 Model Decision Gate (v1.5)
    
    Formalizes the transition from selection-capable to decision-governed.
    Evaluates model cohorts for Promotion, Hold, or Rejection.
    """
    VERSION = "v1"
    
    # Governance Gates (Configurable)
    THRESHOLDS = {
        "evidence_floor": 5,
        "reliability_min": 0.90,
        "stability_min": 0.70,
        "margin_min": 0.15
    }

    def evaluate_task(self, task: str, ranks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates a ranked task cohort to produce a formal Decision Artifact.
        """
        if not ranks:
            return self._build_decision(task, "INSUFFICIENT_EVIDENCE", reason="No model regimes detected for this task.")

        # 1. Identify Raw Winner and Runner Up
        # Ranks are already sorted by score DESC from ParetoAnalyzer
        raw_winner = ranks[0]
        raw_runner_up = ranks[1] if len(ranks) > 1 else None
        
        # 2. Evidence Check
        if raw_winner["run_count"] < self.THRESHOLDS["evidence_floor"]:
            return self._build_decision(task, "INSUFFICIENT_EVIDENCE", 
                                      winner=raw_winner, 
                                      runner_up=raw_runner_up,
                                      reason=f"Winner {raw_winner['model']} has insufficient evidence ({raw_winner['run_count']} runs).")

        # 3. Evaluate Gates for Raw Winner
        reliability_pass = raw_winner["reliability"] >= self.THRESHOLDS["reliability_min"]
        stability_pass = raw_winner["stability"] >= self.THRESHOLDS["stability_min"]
        gov_clear = raw_winner["label"] not in ["FAILURE_PRONE", "NOISY_REGIME"]
        
        # Margin Check (Winner vs Runner Up)
        margin = (raw_winner["score"] - raw_runner_up["score"]) if raw_runner_up else 1.0 # Default to 1.0 if uncontested
        margin_pass = margin >= self.THRESHOLDS["margin_min"]
        
        # 4. Determine Promotion Status
        status = "HOLD"
        reason = "Awaiting further evidence or margin stabilization."
        
        all_checks_passed = (reliability_pass and stability_pass and gov_clear and margin_pass)
        
        if all_checks_passed:
            status = "PROMOTE"
            reason = f"Model {raw_winner['model']} cleared all promotion gates with {round(margin, 3)} margin."
        elif not gov_clear or raw_winner["label"] == "FAILURE_PRONE":
            # Check if there's any other ELIGIBLE candidate that might be better than this failure-prone winner
            eligible_candidates = [r for r in ranks if r["reliability"] >= self.THRESHOLDS["reliability_min"] 
                                   and r["label"] not in ["FAILURE_PRONE", "NOISY_REGIME"]]
            
            if not eligible_candidates:
                status = "REJECT"
                reason = "Entire cohort is structurally unsafe or dominated by execution failures."
            else:
                best_eligible = eligible_candidates[0]
                status = "HOLD"
                reason = f"Top model {raw_winner['model']} is unsafe. Evaluating eligible runner-up {best_eligible['model']}."
        else:
            # Failed on margin or reliability/stability thresholds but not structurally broken
            failed_gates = []
            if not reliability_pass: failed_gates.append(f"Reliability ({raw_winner['reliability']})")
            if not stability_pass: failed_gates.append(f"Stability ({raw_winner['stability']})")
            if not margin_pass: failed_gates.append(f"Margin ({round(margin, 3)})")
            
            status = "HOLD"
            reason = f"Winner held. Failed gates: {', '.join(failed_gates)}."

        return self._build_decision(
            task, status, 
            winner=raw_winner, 
            runner_up=raw_runner_up,
            margin=margin,
            checks={
                "evidence_pass": raw_winner["run_count"] >= self.THRESHOLDS["evidence_floor"],
                "reliability_pass": reliability_pass,
                "stability_pass": stability_pass,
                "margin_pass": margin_pass,
                "governance_clear": gov_clear
            },
            reason=reason
        )

    def _build_decision(self, task: str, status: str, 
                       winner: Optional[Dict] = None, 
                       runner_up: Optional[Dict] = None,
                       margin: float = 0.0,
                       checks: Optional[Dict] = None,
                       reason: str = "") -> Dict[str, Any]:
        """Helper to construct the decision artifact schema."""
        decision = {
            "decision_version": self.VERSION,
            "task": task,
            "promotion_status": status,
            "reason": reason,
            "locked_at": utc_now_iso(),
            "thresholds_used": self.THRESHOLDS
        }
        
        if winner:
            decision.update({
                "winner_model": winner["model"],
                "winner_score": winner["score"],
                "winner_snapshot": {
                    "label": winner["label"],
                    "run_count": winner["run_count"],
                    "power": winner["power"],
                    "yield": winner["yield"],
                    "stability": winner["stability"],
                    "reliability": winner["reliability"]
                }
            })
            
        if runner_up:
            decision.update({
                "runner_up_model": runner_up["model"],
                "runner_up_score": runner_up["score"],
                "margin": round(margin, 3)
            })
            
        if checks:
            decision["checks"] = checks
            
        return decision
