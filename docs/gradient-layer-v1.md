# TM4 Gradient Detection Layer v1 - Technical Specification

This document defines the second-order analysis layer for TM4Server, enabling the detection of optimization "gradients" (meaningful signals) across multi-run experiment regimes.

## 🏛️ Architectural Principles

1.  **Regime Centrality**: Analysis is centered on the **Experiment Regime**, defined as the unique combination of `(task, model)`.
2.  **On-Demand Authoritative Computation**: The authoritative source of truth is the live computation performed by `GET /api/analysis/gradients`. Background state is avoided to ensure freshness and reduce architectural complexity.
3.  **Governance-First (Risk-First) Precedence**: Detection logic follows a risk-first cascade. Maladaptive patterns (Failures, Noise) are detected before optimistic signals (Convergence).
4.  **Hybrid Proportions**: Signal detection uses a mix of **Raw Count Floor Checks** for safety and **Confidence-Weighted Proportions** for directional signal.

## 🏷️ Regime Taxonomy & Precedence (v1)

Evaluation follows this strict cascade. The first satisfied condition wins:

1.  **`INSUFFICIENT_EVIDENCE`**
    - Trigger: Total classified runs $N < 3$.
2.  **`FAILURE_PRONE`**
    - Trigger: **Raw** failure ratio > 0.20 (Execution failures or unclassifiable data).
3.  **`SATURATED_REGIME`**
    - Trigger: **Weighted** `SATURATED` share > 0.70.
4.  **`SIGNAL_ABSENT_REGIME`**
    - Trigger: **Weighted** `SIGNAL_ABSENT` share > 0.80.
5.  **`NOISY_REGIME`**
    - Trigger: **Weighted** `UNSTABLE` share > 0.30 OR Mean Confidence < 0.60.
6.  **`CONVERGENT_CLUSTER`**
    - Trigger: **Weighted** `CONVERGENT` share > 0.60 AND Mean Confidence > 0.70.

## 🧠 Detection Logic: Confidence-Weighted Voting

For a given regime (Task $T$, Model $M$):
1.  Collect all $N$ runs where `classification.json` exists.
2.  **Raw Distribution**: Count occurrences of each label.
3.  **Weighted Scores**: Sum the confidence values for each label.
4.  **Proportions**: Calculate weighted share (label score / total score) for signal detection.

## 📝 Output Schema

The API returns a comprehensive rollup of the current evidence landscape:

```json
{
  "gradient_version": "v1",
  "generated_at": "2026-04-10T04:00:00Z",
  "regimes": [
    {
      "regime_key": "autonomy__default",
      "task": "autonomy",
      "model": "default",
      "label": "CONVERGENT_CLUSTER",
      "mean_confidence": 0.84,
      "run_count": 12,
      "distribution_counts": {
        "CONVERGENT": 9,
        "UNSTABLE": 2,
        "SIGNAL_ABSENT": 1
      },
      "distribution_weighted": {
        "CONVERGENT": 7.56,
        "UNSTABLE": 1.42,
        "SIGNAL_ABSENT": 0.82
      },
      "reason": "75% weighted convergent outcomes with high mean confidence (0.84)."
    }
  ]
}
```

## 🛠️ Operational Strategy

1.  **Grouping**: Primary aggregation by manifest `(task, model)`.
2.  **API**: `GET /api/analysis/gradients` is the authoritative endpoint.
3.  **Persistence**: `state/gradient_index.json` may be written as a disposable snapshot, but it is not a truth anchor.
4.  **UI**: The **Research Signal** panel displays regime distribution bars showing the ratio of outcomes.
