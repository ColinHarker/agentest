"""Agentest - Universal agent testing and evaluation toolkit."""

__version__ = "0.2.0"

from agentest.core import (
    AgentTrace,
    Message,
    Role,
    ToolCall,
    LLMResponse,
    TraceSession,
    diff_traces,
    set_model_pricing,
    get_model_pricing,
    DEFAULT_MODEL_PRICING,
)
from agentest.recorder.recorder import Recorder
from agentest.recorder.replayer import Replayer, ReplayMismatchError
from agentest.mocking.tool_mock import ToolMock, MockToolkit
from agentest.evaluators.base import Evaluator, EvalResult, CompositeEvaluator, LLMJudgeEvaluator
from agentest.evaluators.builtin import (
    TaskCompletionEvaluator,
    SafetyEvaluator,
    CostEvaluator,
    LatencyEvaluator,
    ToolUsageEvaluator,
)
from agentest.benchmark.runner import BenchmarkRunner, BenchmarkResult, BenchmarkTask
from agentest.benchmark.comparison import ModelComparison, ModelScore
from agentest.mcp_testing.server_tester import MCPServerTester, MCPTestResult
from agentest.mcp_testing.assertions import MCPAssertions
from agentest.integrations.instrument import (
    instrument,
    uninstrument,
    get_traces,
    clear_traces,
    flush_trace,
    get_current_recorder,
)

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
