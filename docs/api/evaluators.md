---
sidebar_position: 5
title: Evaluators
---

# Evaluators

Base evaluator interface and built-in evaluators.

## Base

### `EvalResult`

`agentest.evaluators.base.EvalResult`

Result of an evaluation: `evaluator`, `score` (0.0-1.0), `passed`, `message`, `details`.

### `Evaluator`

`agentest.evaluators.base.Evaluator`

Abstract base class. Subclass and implement `evaluate(trace) -> EvalResult`.

### `CompositeEvaluator`

`agentest.evaluators.base.CompositeEvaluator`

Combine multiple evaluators with AND/OR logic. Methods: `evaluate()`, `evaluate_all()`.

### `LLMJudgeEvaluator`

`agentest.evaluators.base.LLMJudgeEvaluator`

Uses an LLM (Anthropic or OpenAI) to grade agent output against custom criteria.

### `RubricEvaluator`

`agentest.evaluators.base.RubricEvaluator`

Scores an agent trace against a weighted rubric. Each criterion in the rubric is scored independently by an LLM, then a weighted average produces the final score. Pass threshold is 0.7.

**Constructor:**

```python
RubricEvaluator(
    rubric: dict[str, float],
    model: str = "claude-sonnet-4-6",
    client: Any = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `rubric` | `dict[str, float]` | Mapping of criterion descriptions to their weights. Weights are normalized so they sum to 1.0. |
| `model` | `str` | Model identifier for the LLM (default `"claude-sonnet-4-6"`). |
| `client` | `Any` | Anthropic or OpenAI client instance. If `None`, `evaluate()` returns score 0.0. |

**Methods:**

- `evaluate(trace: AgentTrace) -> EvalResult` -- Scores the trace against every criterion and returns a weighted result. The `details` dict contains `criterion_scores`, a list of per-criterion dicts with `criterion`, `weight`, `score`, and `reasoning` fields.

**Example:**

```python
from agentest import RubricEvaluator
import anthropic

evaluator = RubricEvaluator(
    rubric={
        "Answered the user's question accurately": 3.0,
        "Used tools efficiently without unnecessary calls": 2.0,
        "Response was concise and well-structured": 1.0,
    },
    client=anthropic.Anthropic(),
)

result = evaluator.evaluate(trace)
# result.details["criterion_scores"] contains per-criterion breakdowns
```

## Built-in

### `TaskCompletionEvaluator`

`agentest.evaluators.builtin.TaskCompletionEvaluator`

Checks success status, errors, message count, and failed tools. Scoring: -0.25 per issue.

### `SafetyEvaluator`

`agentest.evaluators.builtin.SafetyEvaluator`

Scans for unsafe commands, PII, blocked tools, and custom patterns. Supports `pii_whitelist` to suppress false positives from known-safe PII (e.g., test email addresses). Scoring: -0.2 per violation.

### `CostEvaluator`

`agentest.evaluators.builtin.CostEvaluator`

Enforces cost, token, and LLM call budgets. Binary scoring.

### `LatencyEvaluator`

`agentest.evaluators.builtin.LatencyEvaluator`

Checks total and per-call latency limits.

### `ToolUsageEvaluator`

`agentest.evaluators.builtin.ToolUsageEvaluator`

Validates required/forbidden tools, call limits, and retry limits. Scoring: -0.2 per issue.
