"""Agentest - Universal agent testing and evaluation toolkit."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

__version__ = "1.0.2"

from agentest.benchmark.comparison import ModelComparison, ModelScore
from agentest.benchmark.runner import BenchmarkResult, BenchmarkRunner, BenchmarkTask
from agentest.core import (
    DEFAULT_MODEL_PRICING,
    AgentTrace,
    LLMResponse,
    Message,
    Role,
    ToolCall,
    TraceSession,
    diff_traces,
    get_model_pricing,
    reset_model_pricing,
    set_model_pricing,
    unset_model_pricing,
)
from agentest.datasets import ABTestResult, Dataset, DatasetRunner, TestCase
from agentest.evaluators.base import (
    CompositeEvaluator,
    EvalResult,
    Evaluator,
    LLMJudgeEvaluator,
    RubricEvaluator,
)
from agentest.evaluators.builtin import (
    CostEvaluator,
    LatencyEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)
from agentest.evaluators.metrics import (
    Metric,
    MetricEvaluator,
    MetricResult,
)
from agentest.integrations.instrument import (
    clear_exporter,
    clear_traces,
    flush_trace,
    get_current_recorder,
    get_traces,
    instrument,
    is_instrumented,
    set_exporter,
    uninstrument,
)
from agentest.integrations.middleware import (
    AgentestMiddleware,
    FlaskAgentestMiddleware,
    instrument_fastapi,
    instrument_flask,
)
from agentest.mcp_testing.assertions import MCPAssertions
from agentest.mcp_testing.security import MCPSecurityTester, SecurityTestResult
from agentest.mcp_testing.server_tester import MCPServerTester, MCPTestResult
from agentest.mocking.tool_mock import MockToolkit, ToolMock
from agentest.recorder.recorder import Recorder
from agentest.recorder.replayer import Replayer, ReplayMismatchError
from agentest.recorder.streaming import StreamingRecorder, TraceEvent
from agentest.regression import (
    RegressionDetector,
    RegressionEvaluator,
    RegressionResult,
    RegressionThresholds,
)
from agentest.snapshots import SnapshotConfig, SnapshotManager, SnapshotResult
from agentest.stats import (
    SLO,
    ConfidenceInterval,
    SLOResult,
    StatsAnalyzer,
    TrendResult,
)


def evaluate(
    trace: AgentTrace,
    max_cost: float | None = None,
    max_tokens: int | None = None,
    check_safety: bool = True,
) -> list[EvalResult]:
    """Run the default evaluator suite against a trace.

    Evaluates task completion and tool usage by default.
    Optionally checks safety and enforces cost/token budgets.

    Args:
        trace: The agent trace to evaluate.
        max_cost: Maximum allowed cost in USD.
        max_tokens: Maximum allowed token count.
        check_safety: Whether to run safety evaluation (default True).

    Returns:
        List of EvalResult, one per evaluator.
    """
    evaluators: list[Evaluator] = [TaskCompletionEvaluator(), ToolUsageEvaluator()]
    if check_safety:
        evaluators.append(SafetyEvaluator())
    if max_cost is not None or max_tokens is not None:
        evaluators.append(CostEvaluator(max_cost=max_cost, max_tokens=max_tokens))
    return CompositeEvaluator(evaluators).evaluate_all(trace)


def run(fn: Any, *args: Any, task: str = "", **kwargs: Any) -> tuple[Any, AgentTrace]:
    """Run a function and return (result, trace).

    Auto-instruments LLM clients if not already instrumented.
    The trace captures all LLM calls and tool uses made during execution.

    Args:
        fn: The function to run.
        *args: Positional arguments for fn.
        task: Task description for the trace.
        **kwargs: Keyword arguments for fn.

    Returns:
        Tuple of (function result, AgentTrace).
    """
    from agentest.integrations.instrument import _finalize_and_store, _get_recorder

    was_instrumented = is_instrumented()
    if not was_instrumented:
        instrument()
    # Flush any existing recorder, then start a fresh one
    flush_trace()
    _get_recorder(task=task or "agentest.run")
    try:
        result = fn(*args, **kwargs)
    except Exception:
        _finalize_and_store(success=False)
        if not was_instrumented:
            uninstrument()
        raise
    trace = _finalize_and_store(success=True)
    if not was_instrumented:
        uninstrument()
    return result, trace


def trace(task: str = "") -> Callable:
    """Decorator that wraps a function to return (result, trace).

    The decorated function auto-instruments LLM clients and captures
    all calls made during execution into an AgentTrace.

    Args:
        task: Task description for the trace. Defaults to the function name.

    Example:
        @agentest.trace(task="Summarize document")
        def my_agent(prompt):
            return client.messages.create(...)

        result, trace = my_agent("Summarize README.md")
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> tuple[Any, AgentTrace]:
            return run(fn, *args, task=task or fn.__name__, **kwargs)

        return wrapper

    return decorator


__all__ = [
    # Core models
    "AgentTrace",
    "Message",
    "Role",
    "ToolCall",
    "LLMResponse",
    "TraceSession",
    "diff_traces",
    "set_model_pricing",
    "unset_model_pricing",
    "reset_model_pricing",
    "get_model_pricing",
    "DEFAULT_MODEL_PRICING",
    # Recording & replay
    "Recorder",
    "Replayer",
    "ReplayMismatchError",
    "StreamingRecorder",
    "TraceEvent",
    # Mocking
    "ToolMock",
    "MockToolkit",
    # Evaluators
    "Evaluator",
    "EvalResult",
    "CompositeEvaluator",
    "LLMJudgeEvaluator",
    "RubricEvaluator",
    "TaskCompletionEvaluator",
    "SafetyEvaluator",
    "CostEvaluator",
    "LatencyEvaluator",
    "ToolUsageEvaluator",
    # Custom metrics
    "Metric",
    "MetricResult",
    "MetricEvaluator",
    # Benchmarking
    "BenchmarkRunner",
    "BenchmarkResult",
    "BenchmarkTask",
    "ModelComparison",
    "ModelScore",
    # MCP testing
    "MCPServerTester",
    "MCPTestResult",
    "MCPAssertions",
    "MCPSecurityTester",
    "SecurityTestResult",
    # Snapshots
    "SnapshotManager",
    "SnapshotConfig",
    "SnapshotResult",
    # Auto-instrumentation
    "instrument",
    "uninstrument",
    "get_traces",
    "clear_traces",
    "flush_trace",
    "get_current_recorder",
    "set_exporter",
    "clear_exporter",
    "is_instrumented",
    # Convenience functions
    "evaluate",
    "run",
    "trace",
    # Middleware
    "AgentestMiddleware",
    "FlaskAgentestMiddleware",
    "instrument_fastapi",
    "instrument_flask",
    # Regression detection
    "RegressionDetector",
    "RegressionResult",
    "RegressionThresholds",
    "RegressionEvaluator",
    # Statistical analysis
    "StatsAnalyzer",
    "TrendResult",
    "ConfidenceInterval",
    "SLO",
    "SLOResult",
    # Dataset management
    "Dataset",
    "TestCase",
    "DatasetRunner",
    "ABTestResult",
]
