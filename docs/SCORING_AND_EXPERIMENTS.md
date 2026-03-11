# Scoring And Experiments

This document explains the score fields shown in the UI and artifacts, how experiment planning works, when experiments are executed, and how outcomes are evaluated.

## Paper Scoring

Paper ranking lives in [`tools/ranker.py`](/d:/Projects/Research%20Forge/tools/ranker.py).

### `relevance_score`

Calculated as lexical overlap between topic tokens and tokens from `title + abstract`.

Formula:

```text
relevance_score = overlap(topic_tokens, doc_tokens) / len(topic_tokens)
```

### `recency_score`

Calculated with exponential decay on paper age:

```text
recency_score = exp(-days_old / 365)
```

Newer papers score closer to `1.0`. Older papers decay toward `0.0`.

### `rank_score`

Calculated as a weighted sum:

```text
rank_score = 0.7 * relevance_score + 0.3 * recency_score
```

Those weights come from the default `PaperRanker` configuration.

## Extraction Confidence

### `confidence_score`

This comes from the extraction schema in [`schemas/extraction.py`](/d:/Projects/Research%20Forge/schemas/extraction.py).

- If the LLM returns a structured extraction, the confidence is whatever the model produced after normalization and validation.
- If heuristic fallback is used, the current fallback confidence is `0.45`.

This score is not statistically calibrated. It is an internal confidence hint used for reflection and diagnostics.

## Hypothesis Scores

Hypothesis fields live in [`schemas/hypothesis.py`](/d:/Projects/Research%20Forge/schemas/hypothesis.py).

### `novelty`

Estimated score in `[0, 1]` for how non-obvious or gap-exploiting the hypothesis is.

### `feasibility`

Estimated score in `[0, 1]` for how realistically the hypothesis can be tested with available evidence and likely execution routes.

### `information_gain`

Estimated score in `[0, 1]` for how much the result would teach you if tested.

### `compute_cost`

Estimated score in `[0, 1]` for expected cost. Lower is better.

For LLM-generated hypotheses, these are model-generated rubric scores normalized to `[0, 1]` by [`tools/llm_client.py`](/d:/Projects/Research%20Forge/tools/llm_client.py). If a model returns `1-10` style values, they are divided by `10`.

### `priority_score`

Calculated in [`agent/nodes/prioritize_hypotheses.py`](/d:/Projects/Research%20Forge/agent/nodes/prioritize_hypotheses.py) as:

```text
priority_score =
    0.30 * novelty
  + 0.25 * feasibility
  + 0.30 * information_gain
  + 0.15 * (1 - compute_cost)
```

Higher priority means a better tradeoff between novelty, practicality, expected learning value, and cost.

## Prediction Score Used For Reflection

The agent creates a prediction for top hypotheses:

```text
expected_support_probability = 0.6 * feasibility + 0.4 * (1 - compute_cost)
```

This is later compared against actual outcomes during reflection.

## Experiment Budget

### `experiment_budget`

This is the user constraint from [`schemas/run_report.py`](/d:/Projects/Research%20Forge/schemas/run_report.py).

It controls how many top hypotheses are directly considered for planning.

Current behavior:

- planning candidates are sliced to at most `experiment_budget`
- prioritization still keeps a small buffer of top hypotheses (`budget + 2`) for ranking and reporting

## Experiment Plan Fields

Experiment plans live in [`schemas/experiment.py`](/d:/Projects/Research%20Forge/schemas/experiment.py).

### `complexity`

Shown in UI as `estimated_complexity`.

This is a categorical estimate such as:

- `low`
- `medium`
- `high`

For heuristic proxy experiments, lightweight plans are generally marked `low`. Heavy theoretical plans are usually marked `high`.

### `executable`

Shown in UI as `executable_locally`.

This means:

- the system believes the experiment can run inside the local sandbox
- a runnable Python snippet is available or was auto-generated

### `theoretical_only`

This means the plan is useful as a research design, but the system will not run it locally.

Typical reasons:

- experiments were disabled by the user
- the topic is too heavy for safe lightweight execution
- the LLM provided only a conceptual plan with no safe runnable snippet

### `success_condition`

This is the explicit pass criterion for the experiment plan.

Examples:

- improve `primary_score` by at least `0.03` without runtime cost increase above `0.10`
- improve F1 by at least `0.02` within a bounded runtime cost

It can be LLM-generated or filled by heuristic proxy-plan templates.

## Proxy Experiments

Experiment planning lives in [`agent/nodes/plan_experiment.py`](/d:/Projects/Research%20Forge/agent/nodes/plan_experiment.py).

### Why proxy experiments exist

Many scientific hypotheses cannot honestly be executed locally with no network, no large datasets, and no heavy dependencies. Instead of pretending those are executable, the planner:

- keeps heavy plans theoretical-only
- auto-generates lightweight proxy experiments for lightweight topics

### Topic families with auto-generated proxies

- `llm_eval`
- `anomaly`
- `time_series`
- `graph`
- `generic`

### What proxy experiments actually do

They run real Python code in the sandbox, but on small synthetic or proxy tasks. They are meant to provide a fast signal, not full scientific validation.

Examples:

- pairwise preference simulation for `LLM evaluation`
- synthetic anomaly mixture with thresholded baseline vs robust variant
- autoregressive toy forecast evaluation for `time series`
- synthetic node-feature classification for `graph`

## Sandboxed Execution

Execution is handled by [`tools/python_runner.py`](/d:/Projects/Research%20Forge/tools/python_runner.py).

### Safety restrictions

The runner blocks imports such as:

- `os`
- `sys`
- `subprocess`
- `socket`
- `requests`
- `httpx`
- `urllib`
- `pathlib`
- `ctypes`
- `multiprocessing`

It also blocks calls such as:

- `eval`
- `exec`
- `compile`
- `__import__`
- `open`
- `input`

### Execution environment

- isolated temp directory
- `python -I`
- timeout-limited subprocess
- stdout and stderr captured

## When Experiments Are Skipped

The skip logic is in [`agent/nodes/run_experiment.py`](/d:/Projects/Research%20Forge/agent/nodes/run_experiment.py).

An experiment is marked `not_tested` when:

- `experiments_enabled` is false
- `theoretical_only` is true
- `executable_locally` is false
- `python_snippet` is missing

That is why some plans appear in the UI but are not executed.

## Result Fields

Result fields live in [`schemas/result.py`](/d:/Projects/Research%20Forge/schemas/result.py).

### `status`

- `executed`
- `skipped`
- `failed`

### `hypothesis_outcome`

- `supported`
- `unsupported`
- `inconclusive`
- `not_tested`

### `metric_deltas`

Dictionary of numeric outcome values returned by the experiment snippet.

Common entries:

- `primary_score`
- `runtime_cost`
- family-specific metrics such as `mae_variant`, `f1_variant`, or `accuracy_variant`

### `evidence_quality`

A normalized confidence-like score for how strong the observed evidence is. This is currently assigned by heuristic evaluation logic, not by statistical inference.

### `reproducibility_confidence`

Heuristic estimate for how likely the result is to reproduce under similar conditions.

### `confounders`

Known caveats or failure modes revealed by the experiment or proxy setup.

## Outcome Evaluation Logic

The evaluation logic lives in [`agent/nodes/evaluate_results.py`](/d:/Projects/Research%20Forge/agent/nodes/evaluate_results.py).

Current thresholds:

- if `primary_score >= 0.03` and `runtime_cost <= 0.10`, outcome is `supported`
- if `primary_score < 0`, outcome is `unsupported`
- otherwise, outcome is `inconclusive`

This is intentionally simple MVP logic. It is transparent and easy to replace later with stronger domain-aware evaluation.

## Artifacts

Artifacts are written by [`tools/report_writer.py`](/d:/Projects/Research%20Forge/tools/report_writer.py).

Each run writes:

- `research_report.md`
- `research_report.json`

The JSON artifact is the most complete structured record. The Markdown file is a readable summary.

## How These Fields Show Up In The UI

The Streamlit UI displays:

- `rank_score` under Retrieved Papers
- `priority`, `novelty`, `feasibility`, `info_gain`, `compute_cost` under Generated Hypotheses
- `complexity`, `executable`, `theoretical_only`, `success_condition` under Experiment Plans
- `status`, `outcome`, `metric_deltas`, `evidence_quality`, and `next_step` under Results

That means the UI is directly reflecting the internal run artifact rather than inventing separate display-only scores.
