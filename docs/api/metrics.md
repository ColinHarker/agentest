---
sidebar_position: 11
title: Metrics
---

# Metrics

Custom metrics framework for user-defined evaluation metrics.

## Base

### `Metric`

`agentest.evaluators.metrics.Metric`

Abstract base class for custom metrics. Metrics compute a single scalar value from a trace. Subclass and set `name` and `description` class attributes, then implement the `compute` method.

**Methods:**

- `compute(trace: AgentTrace) -> float` — Abstract. Compute a scalar metric value from a trace.

**Example:**

```python
from agentest.evaluators.metrics import Metric

class ResponseLengthMetric(Metric):
    name = "response_length"
    description = "Average response length in characters"

    def compute(self, trace):
        if not trace.llm_responses:
            return 0.0
        return sum(len(r.content) for r in trace.llm_responses) / len(trace.llm_responses)
```

### `MetricResult`

`agentest.evaluators.metrics.MetricResult`

Result from computing a metric. Pydantic model with fields: `metric` (str), `value` (float), `threshold` (float or None), `passed` (bool or None), `details` (dict).

### `MetricEvaluator`

`agentest.evaluators.metrics.MetricEvaluator`

Evaluator that runs a set of Metrics with optional thresholds. Extends `Evaluator`.

**Constructor:**

- `MetricEvaluator(metrics: list[tuple[Metric, float | None]])` — List of `(metric, threshold)` tuples. If threshold is `None`, the metric is computed but does not affect pass/fail.

**Methods:**

- `evaluate(trace: AgentTrace) -> EvalResult` — Run all metrics and return an aggregated result. Score is the fraction of thresholded metrics that pass.
- `compute_all(trace: AgentTrace) -> list[MetricResult]` — Compute all metrics and return individual results.

**Example:**

```python
from agentest.evaluators.metrics import MetricEvaluator, TokenEfficiencyMetric, ErrorRateMetric

evaluator = MetricEvaluator(metrics=[
    (TokenEfficiencyMetric(), 500.0),   # max 500 tokens per tool call
    (ErrorRateMetric(), 0.1),            # max 10% error rate
])
result = evaluator.evaluate(trace)
```

## Built-in Metrics

### `TokenEfficiencyMetric`

`agentest.evaluators.metrics.TokenEfficiencyMetric`

Tokens per tool call -- lower is more efficient. Computes `total_tokens / max(total_tool_calls, 1)`.

### `ErrorRateMetric`

`agentest.evaluators.metrics.ErrorRateMetric`

Fraction of tool calls that failed. Computes `len(failed_tool_calls) / total_tool_calls`.

### `CostPerTokenMetric`

`agentest.evaluators.metrics.CostPerTokenMetric`

Cost per 1K tokens. Computes `(total_cost / total_tokens) * 1000`.

### `ToolCallCountMetric`

`agentest.evaluators.metrics.ToolCallCountMetric`

Total number of tool calls made. Returns `total_tool_calls` as a float.

### `LLMCallCountMetric`

`agentest.evaluators.metrics.LLMCallCountMetric`

Total number of LLM API calls. Returns `len(llm_responses)` as a float.
