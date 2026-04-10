import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tm4server.analysis.pareto_analyzer import ParetoAnalyzer
from tm4server.analysis.decision_engine import DecisionEngine
from tm4server.api.operator_console import detect_drift

def verify_decision_v2_logic():
    print("--- Verifying Triple-View Decision Logic (v1.5.1 / v2) ---")
    
    analyzer = ParetoAnalyzer()
    engine = DecisionEngine()
    
    # 1. Base Setup: Create a typical "PROMOTE" scenario
    regimes = [
        {"task": "autonomy", "model": "model_a", "label": "CONVERGENT_CLUSTER", "mean_net_improvement": 1.0, 
         "run_count": 10, "distribution_counts": {"CONVERGENT": 10}, "distribution_weighted": {"CONVERGENT": 10.0}},
        {"task": "autonomy", "model": "model_b", "label": "CONVERGENT_CLUSTER", "mean_net_improvement": 0.5, 
         "run_count": 10, "distribution_counts": {"CONVERGENT": 10}, "distribution_weighted": {"CONVERGENT": 10.0}}
    ]
    ranks = analyzer.process_task_cohort("autonomy", regimes)
    projected = engine.evaluate_task("autonomy", ranks)
    
    # Test 1: NO_DRIFT
    # Lock is identical to projection
    locked = projected.copy()
    locked["locked"] = True
    drift, dtype, dreason = detect_drift(projected, locked)
    print(f"TEST 1 (NO_DRIFT): drift={drift}, type={dtype}")
    assert drift == False

    # Test 2: WINNER_CHANGED
    # Locked says model_b was the winner
    locked_winner = locked.copy()
    locked_winner["winner_model"] = "model_b"
    drift, dtype, dreason = detect_drift(projected, locked_winner)
    print(f"TEST 2 (WINNER_CHANGED): drift={drift}, type={dtype}")
    assert drift == True
    assert dtype == "WINNER_CHANGED"

    # Test 3: STATUS_CHANGED
    # Locked says HOLD, but projected now says PROMOTE
    locked_status = locked.copy()
    locked_status["promotion_status"] = "HOLD"
    drift, dtype, dreason = detect_drift(projected, locked_status)
    print(f"TEST 3 (STATUS_CHANGED): drift={drift}, type={dtype}")
    assert drift == True
    assert dtype == "STATUS_CHANGED"

    # Test 4: GATES_DEGRADED
    # Both are HOLD, but locked had stability PASSED, projected has stability FAILED
    locked_hold = locked.copy()
    locked_hold["promotion_status"] = "HOLD"
    locked_hold["checks"] = locked["checks"].copy()
    locked_hold["checks"]["stability_pass"] = True
    
    projected_hold = projected.copy()
    projected_hold["promotion_status"] = "HOLD"
    projected_hold["checks"] = projected["checks"].copy()
    projected_hold["checks"]["stability_pass"] = False
    
    drift, dtype, dreason = detect_drift(projected_hold, locked_hold)
    print(f"TEST 4 (GATES_DEGRADED): drift={drift}, type={dtype}")
    assert drift == True
    assert dtype == "GATES_DEGRADED"

    print("--- Verifier Passed: Triple-View Drift Detection Certified ---")

if __name__ == "__main__":
    verify_decision_v2_logic()
