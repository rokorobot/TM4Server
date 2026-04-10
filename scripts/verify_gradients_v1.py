import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tm4server.analysis.gradient_detector import GradientDetector

def verify_gradient_logic():
    print("--- Verifying Gradient Detection Logic (v1) ---")
    
    detector = GradientDetector()
    
    # CASE 1: CONVERGENT_CLUSTER (Majority high-confidence convergent)
    runs_conv = [
        {"label": "CONVERGENT", "confidence": 0.9},
        {"label": "CONVERGENT", "confidence": 0.85},
        {"label": "CONVERGENT", "confidence": 0.9},
        {"label": "UNSTABLE", "confidence": 0.4},
    ]
    res_conv = detector.analyze_regime("task1", "model1", runs_conv)
    print(f"CASE 1 (CONV): {res_conv['label']} (Conf: {res_conv['mean_confidence']})")
    assert res_conv['label'] == "CONVERGENT_CLUSTER"

    # CASE 2: NOISY_REGIME (Mixed with low confidence or unstable presence)
    # 2 high-conf unstable + 3 low-conf convergent
    runs_noisy = [
        {"label": "UNSTABLE", "confidence": 0.9},
        {"label": "UNSTABLE", "confidence": 0.8},
        {"label": "CONVERGENT", "confidence": 0.4},
        {"label": "CONVERGENT", "confidence": 0.4},
        {"label": "CONVERGENT", "confidence": 0.4},
    ]
    res_noisy = detector.analyze_regime("task1", "model1", runs_noisy)
    print(f"CASE 2 (NOISY): {res_noisy['label']} (Reason: {res_noisy['reason']})")
    assert res_noisy['label'] == "NOISY_REGIME"

    # CASE 3: FAILURE_PRONE (Raw count check)
    runs_fail = [
        {"label": "EXECUTION_FAILURE", "confidence": 1.0},
        {"label": "CONVERGENT", "confidence": 0.9},
        {"label": "CONVERGENT", "confidence": 0.9},
        {"label": "CONVERGENT", "confidence": 0.9},
        {"label": "EXECUTION_FAILURE", "confidence": 1.0}, # 2/5 = 40% failure
    ]
    res_fail = detector.analyze_regime("task1", "model1", runs_fail)
    print(f"CASE 3 (FAIL): {res_fail['label']} (Ratio: {res_fail['distribution_counts']['EXECUTION_FAILURE']/5})")
    assert res_fail['label'] == "FAILURE_PRONE"

    # CASE 4: INSUFFICIENT_EVIDENCE
    runs_insuf = [
        {"label": "CONVERGENT", "confidence": 0.9},
        {"label": "CONVERGENT", "confidence": 0.9},
    ]
    res_insuf = detector.analyze_regime("task1", "model1", runs_insuf)
    print(f"CASE 4 (INSUF): {res_insuf['label']}")
    assert res_insuf['label'] == "INSUFFICIENT_EVIDENCE"

    # CASE 5: SATURATED_REGIME
    runs_sat = [
        {"label": "SATURATED", "confidence": 0.9},
        {"label": "SATURATED", "confidence": 0.9},
        {"label": "SATURATED", "confidence": 0.9},
        {"label": "SIGNAL_ABSENT", "confidence": 0.2},
    ]
    res_sat = detector.analyze_regime("task1", "model1", runs_sat)
    print(f"CASE 5 (SAT): {res_sat['label']}")
    assert res_sat['label'] == "SATURATED_REGIME"

    print("--- Gradient Logic Verified ---")

if __name__ == "__main__":
    verify_gradient_logic()
