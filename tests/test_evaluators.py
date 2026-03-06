"""Tests for the evaluation system."""

from agentest.core import AgentTrace, LLMResponse, ToolCall
from agentest.evaluators.base import CompositeEvaluator
from agentest.evaluators.builtin import (
    CostEvaluator,
    LatencyEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)


def _make_trace(**kwargs) -> AgentTrace:
    trace = AgentTrace(task="test task", **kwargs)
    trace.finalize(success=kwargs.get("success", True))
    return trace


def test_task_completion_success():
    trace = _make_trace()
    trace.messages = []  # finalize doesn't add messages
    ev = TaskCompletionEvaluator(min_messages=0)
    result = ev.evaluate(trace)
    assert result.passed


def test_task_completion_failure():
    trace = AgentTrace(task="test")
    trace.finalize(success=False, error="Something went wrong")
    ev = TaskCompletionEvaluator(min_messages=0)
    result = ev.evaluate(trace)
    assert not result.passed


def test_task_completion_requires_tool_calls():
    trace = _make_trace()
    ev = TaskCompletionEvaluator(require_tool_calls=True, min_messages=0)
    result = ev.evaluate(trace)
    assert not result.passed

    trace.tool_calls.append(ToolCall(name="tool1", result="ok"))
    result = ev.evaluate(trace)
    assert result.passed


def test_safety_clean():
    trace = _make_trace()
    ev = SafetyEvaluator()
    result = ev.evaluate(trace)
    assert result.passed


def test_safety_unsafe_command():
    trace = _make_trace()
    trace.tool_calls.append(ToolCall(name="bash", arguments={"command": "rm -rf /"}, result=""))
    ev = SafetyEvaluator()
    result = ev.evaluate(trace)
    assert not result.passed
    assert result.details["violations"]


def test_safety_pii_detection():
    trace = _make_trace()
    trace.tool_calls.append(ToolCall(name="output", arguments={}, result="SSN: 123-45-6789"))
    ev = SafetyEvaluator(check_pii=True)
    result = ev.evaluate(trace)
    assert not result.passed


def test_safety_blocked_tools():
    trace = _make_trace()
    trace.tool_calls.append(ToolCall(name="exec_code", arguments={}, result="ok"))
    ev = SafetyEvaluator(blocked_tools=["exec_code"])
    result = ev.evaluate(trace)
    assert not result.passed


def test_safety_custom_patterns():
    trace = _make_trace()
    trace.llm_responses.append(LLMResponse(model="test", content="Use API key: sk-abc123xyz"))
    ev = SafetyEvaluator(custom_patterns=[r"sk-[a-z0-9]+"])
    result = ev.evaluate(trace)
    assert not result.passed


def test_cost_within_budget():
    trace = _make_trace()
    trace.llm_responses.append(
        LLMResponse(model="claude-sonnet-4-6", input_tokens=100, output_tokens=50, total_tokens=150)
    )
    ev = CostEvaluator(max_cost=1.0)
    result = ev.evaluate(trace)
    assert result.passed


def test_cost_over_budget():
    trace = _make_trace()
    trace.llm_responses.append(
        LLMResponse(
            model="claude-opus-4-6",
            input_tokens=1_000_000,
            output_tokens=500_000,
            total_tokens=1_500_000,
        )
    )
    ev = CostEvaluator(max_cost=1.0)
    result = ev.evaluate(trace)
    assert not result.passed


def test_cost_token_limit():
    trace = _make_trace()
    trace.llm_responses.append(
        LLMResponse(model="test", input_tokens=5000, output_tokens=5000, total_tokens=10000)
    )
    ev = CostEvaluator(max_tokens=5000)
    result = ev.evaluate(trace)
    assert not result.passed


def test_latency_within_limit():
    trace = AgentTrace(task="test")
    trace.finalize(success=True)
    ev = LatencyEvaluator(max_total_ms=60000)
    result = ev.evaluate(trace)
    assert result.passed


def test_tool_usage_required():
    trace = _make_trace()
    trace.tool_calls.append(ToolCall(name="search", result="ok"))
    ev = ToolUsageEvaluator(required_tools=["search", "read_file"])
    result = ev.evaluate(trace)
    assert not result.passed  # Missing read_file


def test_tool_usage_forbidden():
    trace = _make_trace()
    trace.tool_calls.append(ToolCall(name="exec_code", result="ok"))
    ev = ToolUsageEvaluator(forbidden_tools=["exec_code"])
    result = ev.evaluate(trace)
    assert not result.passed


def test_tool_usage_excessive_retries():
    trace = _make_trace()
    for _ in range(5):
        trace.tool_calls.append(
            ToolCall(name="flaky_api", arguments={"id": "123"}, error="timeout")
        )
    ev = ToolUsageEvaluator(max_retries_per_tool=3)
    result = ev.evaluate(trace)
    assert not result.passed


def test_composite_evaluator():
    trace = _make_trace()
    trace.tool_calls.append(ToolCall(name="safe_tool", result="ok"))

    composite = CompositeEvaluator(
        [
            TaskCompletionEvaluator(min_messages=0),
            SafetyEvaluator(),
        ]
    )

    result = composite.evaluate(trace)
    assert result.passed

    results = composite.evaluate_all(trace)
    assert len(results) == 2
    assert all(r.passed for r in results)
