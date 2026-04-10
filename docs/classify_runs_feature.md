# TM4Server Feature Documentation — `classify_runs.py`

## Overview

`tm4server/analysis/classify_runs.py` adds a deterministic semantic classification layer on top of the TM4Server experiment ledger.

Before this feature, the system could reliably answer:

- what ran
- when it ran
- whether it completed
- what artifacts and summary metrics were produced

After this feature, the system can also answer:

- what the run means
- whether the run failed operationally
- whether the benchmark was saturated
- whether the run lacked a usable optimization gradient
- whether the run converged meaningfully
- whether the run was unstable

This is the first analysis-layer module that converts raw experiment telemetry into machine-readable scientific interpretation.

---

## Why this feature exists

TM4Server had already closed the loop between:

**execution → evidence → memory → publication**

That made the system deterministic, auditable, self-indexing, and reproducible.

The next bottleneck was no longer infrastructure.
It was interpretation.

`classify_runs.py` exists to solve that problem.

It establishes a formal layer that maps experiment outputs into explicit outcome classes, allowing downstream reporting, analytics, and gradient detection to operate on structured semantics instead of manual interpretation.

---

## Primary goals

The module is designed to:

1. classify each run into a small set of meaningful experiment states
2. preserve honesty when evidence is incomplete
3. remain deterministic and pipeline-safe
4. support both historical ledgers and richer future run artifacts
5. create a stable substrate for derived metrics and cross-run gradient detection

---

## Classification labels

The v1 classifier uses the following labels:

- `FAILED_EXECUTION`
- `SATURATED`
- `NO_GRADIENT`
- `CONVERGENT`
- `UNSTABLE`
- `UNCLASSIFIED`

### `FAILED_EXECUTION`
The run did not complete successfully at the operational level.

Typical triggers:
- `status != success`
- malformed or missing required execution fields
- zero generations when generations were expected

### `SATURATED`
The run reached or started near the performance ceiling with little or no remaining optimization headroom.

Typical triggers:
- near-ceiling Gen 0 fitness
- immediate TTC success
- flat fitness after early ceiling hit

### `NO_GRADIENT`
The run completed, but the task or evaluator did not provide a meaningful optimization signal.

Typical triggers:
- minimal net improvement
- low fitness range
- low improvement density
- no approach toward success threshold

### `CONVERGENT`
The run exhibited meaningful directional improvement and sufficient late-stage stabilization.

Typical triggers:
- material net fitness improvement
- acceptable or zero violations
- stabilization evidence in later generations
- success or strong directional progress

### `UNSTABLE`
The run showed signal, but not in a reliable or stable way.

Typical triggers:
- repeated collapses
- elevated violation rate
- late-stage variance expansion
- gains that do not hold

### `UNCLASSIFIED`
The classifier could not distinguish the run confidently due to missing or ambiguous evidence.

This is an intentional safety class and should not be treated as failure.

---

## Rule precedence

The classifier applies rules in the following order:

1. `FAILED_EXECUTION`
2. `SATURATED`
3. `UNSTABLE`
4. `CONVERGENT`
5. `NO_GRADIENT`
6. `UNCLASSIFIED`

This order is important.

For example:
- a failed run should never be interpreted as scientifically meaningful
- a trivially ceiling-hitting run should not be mis-labeled as meaningful convergence
- an unstable run should override optimistic convergence interpretation when reliability breaks down

---

## Supported inputs

The module supports three input modes.

### 1. Aggregate JSON ledger
Primary input:
- `docs/experiments/results.json`

Supported top-level forms:
- list of runs
- object with `runs`
- object with `rows`

### 2. Aggregate CSV ledger
Fallback input:
- `docs/experiments/results.csv`

This supports classification from flat fields when JSON is unavailable.

### 3. Single run directory
Direct run mode:
- `/var/lib/tm4/runs/<EXP-ID>/run_summary.json`

This allows classification of a single run without reprocessing the full ledger.

---

## Output artifacts

The classifier can produce:

- `docs/experiments/results_classified.json`
- `docs/experiments/results_classified.csv`
- `docs/experiments/classification_summary.json`

It can also enrich an existing JSON ledger in place.

### `results_classified.json`
Contains each run with an attached `classification_analysis` block.

### `results_classified.csv`
Provides flat export for spreadsheet, Pandas, SQL, or reporting workflows.

### `classification_summary.json`
Provides total run counts by label for quick pipeline visibility and dashboards.

---

## Added schema block

Each classified run receives a new top-level block:

```json
"classification_analysis": {
  "classification": "CONVERGENT",
  "confidence": 0.89,
  "reason": "Best fitness improved from 35 to 88 over 10 generations with late-stage stabilization and zero violations.",
  "rules_version": "v1",
  "triggered_rules": [
    "convergent.meaningful_improvement",
    "convergent.stabilized"
  ],
  "metrics": {
    "gen0_best": 35,
    "final_best": 88,
    "net_improvement": 53,
    "fitness_range": 53,
    "generation_count": 10,
    "ttc": null,
    "violations": 0,
    "violation_rate": 0.0,
    "early_variance": 12.1,
    "late_variance": 2.8,
    "improvement_density": 0.44,
    "monotonicity_ratio": 0.78,
    "collapse_count": 0,
    "data_completeness": 0.92
  },
  "thresholds": {
    "success_threshold": 100.0,
    "saturation_threshold": 95.0,
    "min_meaningful_improvement": 10.0
  },
  "classified_at": "2026-04-08T14:20:11+00:00"
}
```

---

## Derived metrics in v1

The classifier derives metrics when enough source data is available.

Core derived metrics include:

- `gen0_best`
- `final_best`
- `net_improvement`
- `fitness_range`
- `generation_count`
- `ttc`
- `violations`
- `violation_rate`
- `early_variance`
- `late_variance`
- `late_stability_ratio`
- `improvement_density`
- `monotonicity_ratio`
- `collapse_count`
- `reached_success`
- `near_ceiling_start`
- `flatness_flag`
- `instability_flag`
- `data_completeness`

These metrics form the basis of both classification and future gradient analysis.

---

## Time-series support

The most important technical addition in this feature is support for extracting a per-generation fitness series.

The module currently attempts to read:

- `best_fitness_by_gen`
- `generation_summaries[*].best_fitness`

When these are available, the classifier can compute:

- early vs late variance
- monotonicity
- improvement density
- repeated collapse count

Without time-series data, the classifier still runs, but with reduced evidence quality.

---

## Confidence scoring

Each classification emits a confidence score.

This is not intended as a probabilistic scientific truth claim.
It is an internal operational signal reflecting:

- data completeness
- rule strength
- ambiguity level

### Confidence behavior

Typical pattern:
- hard operational failures score near `1.0`
- strong saturation matches score high
- fully evidenced convergence scores high
- ambiguous runs score low
- `UNCLASSIFIED` runs remain intentionally low confidence

This allows downstream systems to distinguish between:
- strong semantic classifications
- weak or incomplete classifications

---

## Backward compatibility behavior

Historical ledgers may not contain:

- full generation series
- `gen0_best`
- `final_best`
- derived variance fields
- collapse counts

The classifier is intentionally tolerant.

Compatibility features include:

- Windows-safe `utf-8-sig` reading
- support for JSON `rows` and `runs`
- fallback to legacy `generations` field
- derived calculations when partial fields exist

When evidence remains insufficient, the classifier returns:

- `UNCLASSIFIED`
- low confidence
- explicit explanation

This is the correct behavior.
The system should never convert missing evidence into fake certainty.

---

## CLI contract

Recommended invocation:

```bash
python -m tm4server.analysis.classify_runs \
  --input-json docs/experiments/results.json \
  --output-json docs/experiments/results_classified.json \
  --output-csv docs/experiments/results_classified.csv \
  --summary-json docs/experiments/classification_summary.json \
  --pretty
```

### Supported input flags

- `--input-json`
- `--input-csv`
- `--run-dir`
- `--input-format {auto,json,csv,run-dir}`

### Supported output flags

- `--output-json`
- `--output-csv`
- `--summary-json`
- `--in-place`

### Threshold overrides

- `--success-threshold`
- `--saturation-threshold`
- `--min-meaningful-improvement`
- `--max-flat-range`
- `--max-flat-net-improvement`
- `--unstable-violation-rate`
- `--unstable-late-variance`
- `--collapse-delta`

### Behavior flags

- `--rules-version`
- `--fail-on-missing-fields`
- `--allow-unclassified`
- `--pretty`
- `--verbose`
- `--dry-run`

### Filtering flags

- `--exp-id`
- `--status`
- `--execution-mode`

---

## Exit codes

The module is pipeline-safe and returns standard exit codes.

- `0` = success
- `1` = fatal I/O error
- `2` = schema or validation error
- `3` = completed with one or more `UNCLASSIFIED` runs
- `4` = no valid runs found

This allows CI, scheduled jobs, and orchestration scripts to distinguish between:

- hard failure
- soft semantic incompleteness
- empty result sets

---

## Current observed behavior on historical runs

When executed against older aggregate ledgers that do not contain fitness time-series artifacts, the classifier currently marks those runs as:

- `UNCLASSIFIED`
- low confidence

This is expected and correct.

Those historical records are missing the temporal evidence required to distinguish among:

- no gradient
- true convergence
- unstable dynamics
- trivial saturation

The classifier is therefore behaving conservatively and honestly.

---

## Strategic significance

This feature changes TM4Server from:

**run recorder**

into:

**run interpreter**

That matters because it introduces a formal semantic layer between raw telemetry and higher-order analysis.

With this feature in place, the system now has the foundation for:

- derived metrics dashboards
- benchmark family comparisons
- convergence-rate reporting
- instability monitoring
- saturation detection
- cross-run gradient analysis
- research narrative generation

---

## What this feature does not do

`classify_runs.py` is intentionally scoped to **per-run classification**.

It does not yet perform:

- cross-run gradient detection
- longitudinal trend analysis
- benchmark-family induction
- automated markdown reporting per experiment

Those belong in the next analysis layer.

Recommended next module:

- `tm4server/analysis/detect_gradients.py`

---

## Recommended next steps

To improve classification quality on future runs, extend `run_summary.json` and the aggregation layer to include:

- `best_fitness_by_gen`
- `gen0_best`
- `final_best`
- `early_variance`
- `late_variance`
- `improvement_density`
- `monotonicity_ratio`
- `collapse_count`

Once these fields are consistently present, the classifier will move from mostly conservative fallback behavior to strong semantic separation.

---

## Summary

`classify_runs.py` is the first analysis-layer feature in TM4Server that turns experiment outputs into explicit semantic outcomes.

It provides:

- deterministic run classification
- confidence scoring
- backward-tolerant ingestion
- machine-readable interpretation blocks
- pipeline-safe exit semantics

Most importantly, it establishes the substrate required for the next phase of the system:

**derived metrics and governed gradient detection across runs**
