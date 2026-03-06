"""Agentest - Universal agent testing and evaluation toolkit."""

__version__ = "0.2.0"

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
from agentest.evaluators.base import CompositeEvaluator, EvalResult, Evaluator, LLMJudgeEvaluator
from agentest.evaluators.builtin import (
    CostEvaluator,
    LatencyEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)
from agentest.integrations.instrument import (
    clear_traces,
    flush_trace,
    get_current_recorder,
    get_traces,
    instrument,
    uninstrument,
)
from agentest.mcp_testing.assertions import MCPAssertions
from agentest.mcp_testing.server_tester import MCPServerTester, MCPTestResult
from agentest.mocking.tool_mock import MockToolkit, ToolMock
from agentest.recorder.recorder import Recorder
from agentest.recorder.replayer import Replayer, ReplayMismatchError

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
    # Mocking
    "ToolMock",
    "MockToolkit",
    # Evaluators
    "Evaluator",
    "EvalResult",
    "CompositeEvaluator",
    "LLMJudgeEvaluator",
    "TaskCompletionEvaluator",
    "SafetyEvaluator",
    "CostEvaluator",
    "LatencyEvaluator",
    "ToolUsageEvaluator",
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
    # Auto-instrumentation
    "instrument",
    "uninstrument",
    "get_traces",
    "clear_traces",
    "flush_trace",
    "get_current_recorder",
]
