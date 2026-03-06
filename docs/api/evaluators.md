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
