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


def test_safety_pii_whitelist():
    trace = _make_trace()
    trace.tool_calls.append(
        ToolCall(name="output", arguments={}, result="Contact: user@example.com")
    )
    ev = SafetyEvaluator(pii_whitelist=[r".*@example\.com"])
    result = ev.evaluate(trace)
    assert result.passed  # whitelisted, no violation


def test_safety_pii_whitelist_partial():
    trace = _make_trace()
    trace.tool_calls.append(
        ToolCall(name="output", arguments={}, result="user@example.com and 123-45-6789")
    )
    ev = SafetyEvaluator(pii_whitelist=[r".*@example\.com"])
    result = ev.evaluate(trace)
    assert not result.passed  # SSN still flagged
    violations = result.details["violations"]
    # Only SSN should be flagged, not the email
    assert all(v["type"] == "pii_leak" for v in violations)
    assert len(violations) == 1


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


def test_llm_judge_parse_json_response():
    """LLMJudgeEvaluator should parse JSON responses."""
    from agentest.evaluators.base import LLMJudgeEvaluator

    score, reasoning = LLMJudgeEvaluator._parse_response(
        '{"score": 0.85, "reasoning": "Good performance"}'
    )
    assert abs(score - 0.85) < 0.01
    assert reasoning == "Good performance"


def test_llm_judge_parse_json_with_code_fence():
    """LLMJudgeEvaluator should handle JSON wrapped in code fences."""
    from agentest.evaluators.base import LLMJudgeEvaluator

    score, reasoning = LLMJudgeEvaluator._parse_response(
        '```json\n{"score": 0.9, "reasoning": "Excellent"}\n```'
    )
    assert abs(score - 0.9) < 0.01
    assert reasoning == "Excellent"


def test_llm_judge_parse_legacy_format():
    """LLMJudgeEvaluator should still parse legacy SCORE/REASONING format."""
    from agentest.evaluators.base import LLMJudgeEvaluator

    score, reasoning = LLMJudgeEvaluator._parse_response("SCORE: 0.75\nREASONING: Decent work")
    assert abs(score - 0.75) < 0.01
    assert reasoning == "Decent work"


def test_llm_judge_parse_invalid_defaults():
    """LLMJudgeEvaluator should default to 0.5 for unparseable responses."""
    from agentest.evaluators.base import LLMJudgeEvaluator

    score, _ = LLMJudgeEvaluator._parse_response("This is just freeform text with no structure.")
    assert abs(score - 0.5) < 0.01


def test_rubric_evaluator_no_client():
    """RubricEvaluator without client should return score 0.0."""
    from agentest.evaluators.base import RubricEvaluator

    evaluator = RubricEvaluator(rubric={"accuracy": 1.0, "clarity": 0.5})
    trace = AgentTrace(task="test")
    trace.finalize(success=True)

    result = evaluator.evaluate(trace)
    assert result.score == 0.0
    assert not result.passed


def test_rubric_evaluator_weight_normalization():
    """RubricEvaluator should normalize weights."""
    from agentest.evaluators.base import RubricEvaluator

    evaluator = RubricEvaluator(rubric={"a": 2.0, "b": 8.0})
    assert abs(evaluator.rubric["a"] - 0.2) < 0.01
    assert abs(evaluator.rubric["b"] - 0.8) < 0.01


def test_benchmark_result_to_session():
    """BenchmarkResult.to_session() should produce a TraceSession."""
    from agentest.benchmark.runner import BenchmarkResult, TaskResult

    trace1 = AgentTrace(task="t1")
    trace1.finalize(success=True)
    trace2 = AgentTrace(task="t2")
    trace2.finalize(success=True)

    result = BenchmarkResult(
        name="bench",
        tasks=[
            TaskResult(task_name="t1", trace=trace1, eval_results=[], duration_ms=100),
            TaskResult(task_name="t2", trace=trace2, eval_results=[], duration_ms=200),
        ],
        total_time_ms=300,
    )

    session = result.to_session()
    assert session.name == "bench"
    assert session.total_traces == 2
    assert session.metadata["total_time_ms"] == 300
