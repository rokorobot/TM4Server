import sys
from pathlib import Path
import json
import shutil

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tm4server.analysis.classifier import ExperimentClassifier

def verify_scientific_logic():
    print("--- Verifying Scientific Classification Logic (v1) ---")
    
    classifier = ExperimentClassifier()
    
    # CASE 1: CONVERGENT (High improvement, stabilized)
    summary_conv = {
        "exp_id": "EXP-CONV-001",
        "status": "completed",
        "metrics": {
            "gen0_best": 0.2,
            "final_best": 0.6,
            "generations": 10,
            "fitness_min": 0.2,
            "fitness_max": 0.6,
        },
        "best_fitness_by_gen": [0.2, 0.25, 0.3, 0.4, 0.45, 0.5, 0.55, 0.58, 0.59, 0.6]
    }
    res_conv = classifier.classify(summary_conv)
    print(f"CONV: {res_conv['classification']['label']} (Conf: {res_conv['classification']['confidence']})")
    assert res_conv['classification']['label'] == "CONVERGENT"
    assert res_conv['classification']['evidence']['net_improvement'] == 0.4

    # CASE 2: UNSTABLE (Improvement but failed stabilization)
    summary_unst = {
        "exp_id": "EXP-UNST-001",
        "status": "completed",
        "metrics": {
            "gen0_best": 0.2,
            "final_best": 0.6,
            "generations": 10,
        },
        # High noise at the END
        "best_fitness_by_gen": [0.2, 0.21, 0.22, 0.23, 0.24, 0.6, 0.1, 0.7, 0.2, 0.6]
    }
    res_unst = classifier.classify(summary_unst)
    print(f"UNST (Noise): {res_unst['classification']['label']} (Reason: {res_unst['classification']['reason']})")
    assert res_unst['classification']['label'] == "UNSTABLE"

    # CASE 3: SIGNAL_ABSENT (Flatline)
    summary_flat = {
        "exp_id": "EXP-FLAT-001",
        "status": "completed",
        "metrics": {
            "gen0_best": 0.3,
            "final_best": 0.31,
            "generations": 5,
            "fitness_min": 0.3,
            "fitness_max": 0.31
        },
        "best_fitness_by_gen": [0.3, 0.3, 0.31, 0.3, 0.31]
    }
    res_flat = classifier.classify(summary_flat)
    print(f"FLAT: {res_flat['classification']['label']}")
    assert res_flat['classification']['label'] == "SIGNAL_ABSENT"

    # CASE 4: SATURATED
    summary_sat = {
        "exp_id": "EXP-SAT-001",
        "status": "completed",
        "metrics": {
            "gen0_best": 0.98,
            "final_best": 0.99,
        }
    }
    res_sat = classifier.classify(summary_sat)
    print(f"SAT: {res_sat['classification']['label']}")
    assert res_sat['classification']['label'] == "SATURATED"

    # CASE 5: EXECUTION_FAILURE
    summary_fail = {
        "status": "failed",
        "metrics": {"generations": 0}
    }
    res_fail = classifier.classify(summary_fail)
    print(f"FAIL: {res_fail['classification']['label']}")
    assert res_fail['classification']['label'] == "EXECUTION_FAILURE"

    print("--- Scientific Logic Verified ---")

if __name__ == "__main__":
    verify_scientific_logic()
