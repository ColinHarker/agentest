"""Custom metrics framework for user-defined evaluation metrics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from agentest.core import AgentTrace
from agentest.evaluators.base import EvalResult, Evaluator


class Metric(ABC):
    """Base class for custom metrics.

    Metrics compute a single scalar value from a trace. They can be used
    standalone or combined with thresholds via MetricEvaluator.

    Example:
        class ResponseLengthMetric(Metric):
            name = "response_length"
            description = "Average response length in characters"

            def compute(self, trace: AgentTrace) -> float:
                if not trace.llm_responses:
                    return 0.0
                return sum(len(r.content) for r in trace.llm_responses) / len(trace.llm_responses)
    """

    name: str = "base_metric"
    description: str = ""

    @abstractmethod
    def compute(self, trace: AgentTrace) -> float:
        """Compute a scalar metric value from a trace."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


class MetricResult(BaseModel):
    """Result from computing a metric."""

    metric: str
    value: float
    threshold: float | None = None
    passed: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    def __repr__(self) -> str:
        status = ""
        if self.passed is not None:
            status = " PASS" if self.passed else " FAIL"
        return f"MetricResult({self.metric}: {self.value:.4f}{status})"


class MetricEvaluator(Evaluator):
    """Evaluator that runs a set of Metrics with optional thresholds.

    Usage:
        evaluator = MetricEvaluator(metrics=[
            (TokenEfficiencyMetric(), 500.0),   # max 500 tokens per tool call
            (ErrorRateMetric(), 0.1),            # max 10% error rate
            (CostPerTokenMetric(), None),        # track but don't threshold
        ])
        result = evaluator.evaluate(trace)
    """

    name = "metrics"
    description = "Custom metrics evaluator"

    def __init__(self, metrics: list[tuple[Metric, float | None]]) -> None:
        """Initialize with metrics and optional thresholds.

        Args:
            metrics: List of (metric, threshold) tuples. If threshold is None,
                the metric is computed but does not affect pass/fail.
        """
        self.metrics = metrics

    def evaluate(self, trace: AgentTrace) -> EvalResult:
        """Run all metrics and return an aggregated result."""
        results = self.compute_all(trace)

        thresholded = [r for r in results if r.passed is not None]
        if thresholded:
            passed = all(r.passed for r in thresholded)
            score = sum(1.0 for r in thresholded if r.passed) / len(thresholded)
        else:
            passed = True
            score = 1.0

        return EvalResult(
            evaluator=self.name,
            score=score,
            passed=passed,
            details={"metrics": [r.model_dump() for r in results]},
            message=f"{sum(1 for r in thresholded if r.passed)}/{len(thresholded)} metrics passed"
            if thresholded
            else "No thresholds set",
        )

    def compute_all(self, trace: AgentTrace) -> list[MetricResult]:
        """Compute all metrics and return individual results."""
        results: list[MetricResult] = []
        for metric, threshold in self.metrics:
            value = metric.compute(trace)
            passed = None
            if threshold is not None:
                passed = value <= threshold
            results.append(
                MetricResult(
                    metric=metric.name,
                    value=value,
                    threshold=threshold,
                    passed=passed,
                )
            )
        return results


# Built-in metrics


class TokenEfficiencyMetric(Metric):
    """Tokens per tool call — lower is more efficient."""

    name = "token_efficiency"
    description = "Average tokens consumed per tool call"

    def compute(self, trace: AgentTrace) -> float:
        return trace.total_tokens / max(trace.total_tool_calls, 1)


class ErrorRateMetric(Metric):
    """Fraction of tool calls that failed."""

    name = "error_rate"
    description = "Ratio of failed tool calls to total tool calls"

    def compute(self, trace: AgentTrace) -> float:
        if trace.total_tool_calls == 0:
            return 0.0
        return len(trace.failed_tool_calls) / trace.total_tool_calls


class CostPerTokenMetric(Metric):
    """Cost per 1K tokens."""

    name = "cost_per_token"
    description = "Cost in USD per 1,000 tokens"

    def compute(self, trace: AgentTrace) -> float:
        if trace.total_tokens == 0:
            return 0.0
        return (trace.total_cost / trace.total_tokens) * 1000


class ToolCallCountMetric(Metric):
    """Total number of tool calls."""

    name = "tool_call_count"
    description = "Total number of tool calls made"

    def compute(self, trace: AgentTrace) -> float:
        return float(trace.total_tool_calls)


class LLMCallCountMetric(Metric):
    """Total number of LLM calls."""

    name = "llm_call_count"
    description = "Total number of LLM API calls"

    def compute(self, trace: AgentTrace) -> float:
        return float(len(trace.llm_responses))
