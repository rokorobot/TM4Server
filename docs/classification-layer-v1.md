# TM4 Classification Layer v1 - Technical Specification

This document defines the formal semantic interpretation layer for TM4Server experiments, building on the deterministic artifact foundation of v1.1.

## 🏛️ Architectural Principles

1.  **Decoupling**: Execution (Runner) and Interpretation (Classifier) are strictly decoupled. The Runner emits evidence; the Classifier assigns meaning.
2.  **Immutability**: The `run_summary.json` is an immutable record of evidence. Classification is a versioned interpretation layer that can be replayed or updated without altering the underlying evidence.
3.  **Auditability**: Every classification must include an **Evidence Block** and a **Confidence Score**, making the interpretation transparent and auditable.
4.  **Deterministic Governance**: Classification uses a strict **First-Match Logic** to ensure exclusivity and predictability.

## 🏷️ Scientific Labels (v1)

| Label | Meaning |
| :--- | :--- |
| **`EXECUTION_FAILURE`** | The run crashed, timed out, or produced malformed telemetry. |
| **`SATURATED`** | The run reached the performance ceiling immediately; no optimization headroom. |
| **`UNSTABLE`** | High variance, repeated collapses, or unacceptable violation rates. |
| **`CONVERGENT`** | Meaningful directional improvement with late-stage stabilization. |
| **`SIGNAL_ABSENT`** | The task provided no useful optimization signal (flatline). |
| **`UNCLASSIFIED`** | Insufficient or ambiguous evidence to assign a confident label. |

## 📊 Evaluation Substrate

The Classifier operates on the metrics extracted from `run_summary.json`:
- `net_improvement`: Primary directional signal.
- `improvement_density`: Frequency of new performance highs.
- `late_variance` vs `early_variance`: Stability dynamics.
- `violation_rate`: Constraint fulfillment.
- `fitness_range`: Distribution scale.

## 🧠 Strict First-Match Logic (v1)

Evaluation follows a non-overlapping cascade. The first satisfied rule wins:

1.  **EXECUTION_FAILURE**
    - Trigger: `status != "completed"` OR `generations == 0`.
2.  **SATURATED**
    - Trigger: `gen0_best >= 0.95` (ceiling match).
3.  **UNSTABLE**
    - Trigger: `violation_rate > 0.10` OR `collapse_count > 0` OR `late_variance > stability_threshold`.
4.  **CONVERGENT**
    - Trigger: `net_improvement >= 0.15` AND `improvement_density >= 0.4`.
5.  **SIGNAL_ABSENT**
    - Trigger: `abs(net_improvement) < 0.02` AND `fitness_range < 0.05`.
6.  **UNCLASSIFIED**
    - Trigger: Default fallback.

## 📝 Output Schema

Classification results are stored in `classification.json` within the run directory or embedded in the analysis layer:

```json
{
  "classification": {
    "version": "v1",
    "label": "CONVERGENT",
    "confidence": 0.87,
    "evidence": {
      "net_improvement": 0.18,
      "improvement_density": 0.44,
      "late_variance": 0.02,
      "violation_rate": 0.0
    },
    "reason": "Meaningful directional improvement (0.18) with strong stabilization.",
    "classified_at": "2026-04-10T03:40:00Z"
  }
}
```

## 🛠️ Operational Strategy

1.  **Trigger**: Classification is triggered via **POST-RUN ASYNC** (Worker hook) or **ON-DEMAND** (API).
2.  **Replayability**: Since classification is pure logic, historical runs can be re-labeled by re-running the classifier with a new `version`.
3.  **UI**: The Operator Console displays the **Scientific Label** as a secondary badge alongside the operational state.

---
**Status**: DRAFT (v1.1 Foundation Ready)
