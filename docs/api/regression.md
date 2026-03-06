---
sidebar_position: 12
title: Regression
---

# Regression

Regression detection -- compare traces across runs and flag regressions.

## `RegressionThresholds`

`agentest.regression.RegressionThresholds`

Thresholds for regression detection. Pydantic model with fields (all floats representing relative change, except `error_rate_increase` which is absolute):

- `cost_increase` (default `0.1`) — 10% cost increase triggers regression.
- `token_increase` (default `0.1`) — 10% token increase.
- `latency_increase` (default `0.2`) — 20% latency increase.
- `error_rate_increase` (default `0.05`) — 5 percentage point increase (absolute).
- `tool_call_increase` (default `0.25`) — 25% tool call increase.

## `Regression`

`agentest.regression.Regression`

A detected regression or improvement. Pydantic model with fields: `metric` (str), `baseline_value` (float), `current_value` (float), `change_pct` (float), `threshold_pct` (float), `severity` (`"warning"`, `"critical"`, or `"improvement"`).

## `RegressionResult`

`agentest.regression.RegressionResult`

Result of regression detection for a single trace. Pydantic model with fields: `task` (str), `regressions` (list of Regression), `improvements` (list of Regression), `passed` (bool).

**Properties:**

- `has_regressions -> bool` — Whether any regressions were detected.

## `RegressionDetector`

`agentest.regression.RegressionDetector`

Detect regressions by comparing current traces against saved baselines.

**Constructor:**

- `RegressionDetector(baseline_dir: str | Path, thresholds: RegressionThresholds | None = None)`

**Methods:**

- `check(trace: AgentTrace) -> RegressionResult` — Compare a trace against its baseline and detect regressions. Checks cost, tokens, tool calls, latency, error rate, and success status. Severity is `"critical"` when the change exceeds 2x the threshold.
- `check_all(traces_dir: str | Path) -> list[RegressionResult]` — Check all traces in a directory against baselines.
- `update_baseline(trace: AgentTrace) -> Path` — Save a trace as the new baseline for its task.

**Example:**

```python
from agentest.regression import RegressionDetector

detector = RegressionDetector(baseline_dir="baselines/")
result = detector.check(current_trace)
if not result.passed:
    for r in result.regressions:
        print(f"Regression: {r.metric} changed {r.change_pct:.1%}")
```

## `RegressionEvaluator`

`agentest.regression.RegressionEvaluator`

Evaluator wrapper for regression detection. Extends `Evaluator`.

**Constructor:**

- `RegressionEvaluator(baseline_dir: str | Path, thresholds: RegressionThresholds | None = None)`

**Methods:**

- `evaluate(trace: AgentTrace) -> EvalResult` — Run regression detection and return an EvalResult. Scoring: -0.3 per critical regression, -0.15 per warning.
