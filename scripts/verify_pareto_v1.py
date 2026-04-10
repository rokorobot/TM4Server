import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tm4server.analysis.pareto_analyzer import ParetoAnalyzer

def verify_pareto_logic():
    print("--- Verifying Multi-Model Pareto Ranking (v1) ---")
    
    analyzer = ParetoAnalyzer()
    
    # Mock task report with multiple models
    mock_report = {
        "generated_at": "2026-04-10T04:20:00Z",
        "regimes": [
            # Model A: High Power but FAILURE_PRONE
            {
                "task": "task_a",
                "model": "model_a",
                "label": "FAILURE_PRONE",
                "mean_net_improvement": 1.2,
                "run_count": 5,
                "distribution_counts": {"CONVERGENT": 3, "EXECUTION_FAILURE": 2},
                "distribution_weighted": {"CONVERGENT": 3.0, "EXECUTION_FAILURE": 2.0}
            },
            # Model B: Moderate Power, High Reliability, Consistent
            {
                "task": "task_a",
                "model": "model_b",
                "label": "CONVERGENT_CLUSTER",
                "mean_net_improvement": 0.8,
                "run_count": 10,
                "distribution_counts": {"CONVERGENT": 8, "SIGNAL_ABSENT": 2},
                "distribution_weighted": {"CONVERGENT": 7.2, "SIGNAL_ABSENT": 1.8}
            },
            # Model C: NOISY
            {
                "task": "task_a",
                "model": "model_c",
                "label": "NOISY_REGIME",
                "mean_net_improvement": 1.5, # Highest raw power
                "run_count": 5,
                "distribution_counts": {"CONVERGENT": 2, "UNSTABLE": 3},
                "distribution_weighted": {"CONVERGENT": 1.0, "UNSTABLE": 2.5}
            }
        ]
    }
    
    analysis = analyzer.analyze_report(mock_report)
    task_a_ranks = analysis["tasks"]["task_a"]
    
    for r in task_a_ranks:
        print(f"Model {r['model']}: Score={r['score']} (Label={r['label']}, Penalty={r['penalty_applied']})")
        print(f"  - Power: {r['power']}, Yield: {r['yield']}, Stab: {r['stability']}, Reli: {r['reliability']}")
    
    # Assertions
    # 1. Model B should be #1 because it's stable and reliable
    assert task_a_ranks[0]["model"] == "model_b"
    
    # 2. Model A should have penalty applied (FAILURE_PRONE)
    model_a = next(r for r in task_a_ranks if r["model"] == "model_a")
    assert model_a["penalty_applied"] == True
    assert model_a["score"] <= 0.45
    
    # 3. Model C should have penalty applied (NOISY_REGIME)
    model_c = next(r for r in task_a_ranks if r["model"] == "model_c")
    assert model_c["penalty_applied"] == True
    assert model_c["score"] <= 0.60
    
    print("--- Pareto Logic Verified ---")

if __name__ == "__main__":
    verify_pareto_logic()
