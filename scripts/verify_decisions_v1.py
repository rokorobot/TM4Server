import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tm4server.analysis.pareto_analyzer import ParetoAnalyzer
from tm4server.analysis.decision_engine import DecisionEngine

def verify_decision_taxonomy():
    print("--- Verifying Multi-Model Decision Taxonomy (v1.5) ---")
    
    analyzer = ParetoAnalyzer()
    engine = DecisionEngine()
    
    # 1. CASE: PROMOTE
    # Winner clears all gates and margin
    case_promote = {
        "regimes": [
            {"task": "task_promote", "model": "winner", "label": "CONVERGENT_CLUSTER", "mean_net_improvement": 1.0, "run_count": 10, "distribution_counts": {"CONVERGENT": 10}, "distribution_weighted": {"CONVERGENT": 10.0}},
            {"task": "task_promote", "model": "runner", "label": "CONVERGENT_CLUSTER", "mean_net_improvement": 0.5, "run_count": 10, "distribution_counts": {"CONVERGENT": 10}, "distribution_weighted": {"CONVERGENT": 10.0}}
        ]
    }
    ranks_p = analyzer.process_task_cohort("task_promote", case_promote["regimes"])
    dec_p = engine.evaluate_task("task_promote", ranks_p)
    print(f"CASE PROMOTE: {dec_p['promotion_status']} (Reason: {dec_p['reason']})")
    assert dec_p["promotion_status"] == "PROMOTE"

    # 2. CASE: HOLD (Margin)
    # Winner is good but runner-up is too close (< 0.15)
    case_margin = {
        "regimes": [
            {"task": "task_margin", "model": "winner", "label": "CONVERGENT_CLUSTER", "mean_net_improvement": 0.82, "run_count": 10, "distribution_counts": {"CONVERGENT": 10}, "distribution_weighted": {"CONVERGENT": 10.0}},
            {"task": "task_margin", "model": "runner", "label": "CONVERGENT_CLUSTER", "mean_net_improvement": 0.80, "run_count": 10, "distribution_counts": {"CONVERGENT": 10}, "distribution_weighted": {"CONVERGENT": 10.0}}
        ]
    }
    ranks_m = analyzer.process_task_cohort("task_margin", case_margin["regimes"])
    dec_m = engine.evaluate_task("task_margin", ranks_m)
    print(f"CASE HOLD (Margin): {dec_m['promotion_status']} (Reason: {dec_m['reason']})")
    assert dec_m["promotion_status"] == "HOLD"
    assert dec_m["checks"]["margin_pass"] == False

    # 3. CASE: HOLD (Reliability)
    # Winner has high power but reliability < 0.90
    case_reli = {
        "regimes": [
            {"task": "task_reli", "model": "winner", "label": "CONVERGENT_CLUSTER", "mean_net_improvement": 2.0, "run_count": 10, "distribution_counts": {"CONVERGENT": 8, "EXECUTION_FAILURE": 2}, "distribution_weighted": {"CONVERGENT": 8.0, "EXECUTION_FAILURE": 2.0}}
        ]
    }
    ranks_r = analyzer.process_task_cohort("task_reli", case_reli["regimes"])
    dec_r = engine.evaluate_task("task_reli", ranks_r)
    print(f"CASE HOLD (Reliability): {dec_r['promotion_status']} (Reason: {dec_r['reason']})")
    assert dec_r["promotion_status"] == "HOLD"
    assert dec_r["checks"]["reliability_pass"] == False

    # 4. CASE: REJECT (Unsafe)
    # Winner is failure-prone and no one else is viable
    case_reject = {
        "regimes": [
            {"task": "task_reject", "model": "unsafe", "label": "FAILURE_PRONE", "mean_net_improvement": 1.0, "run_count": 10, "distribution_counts": {"CONVERGENT": 5, "EXECUTION_FAILURE": 5}, "distribution_weighted": {"CONVERGENT": 5.0, "EXECUTION_FAILURE": 5.0}}
        ]
    }
    ranks_rej = analyzer.process_task_cohort("task_reject", case_reject["regimes"])
    dec_rej = engine.evaluate_task("task_reject", ranks_rej)
    print(f"CASE REJECT (Unsafe): {dec_rej['promotion_status']} (Reason: {dec_rej['reason']})")
    assert dec_rej["promotion_status"] == "REJECT"

    # 5. CASE: INSUFFICIENT
    case_insuf = {
        "regimes": [
             {"task": "task_insuf", "model": "model_a", "label": "CONVERGENT_CLUSTER", "mean_net_improvement": 1.0, "run_count": 3, "distribution_counts": {"CONVERGENT": 3}, "distribution_weighted": {"CONVERGENT": 3.0}}
        ]
    }
    ranks_i = analyzer.process_task_cohort("task_insuf", case_insuf["regimes"])
    dec_i = engine.evaluate_task("task_insuf", ranks_i)
    print(f"CASE INSUFFICIENT: {dec_i['promotion_status']} (Reason: {dec_i['reason']})")
    assert dec_i["promotion_status"] == "INSUFFICIENT_EVIDENCE"

    print("--- Decision Logic Verified (Full Battery) ---")

if __name__ == "__main__":
    verify_decision_taxonomy()
