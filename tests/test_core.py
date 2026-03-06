"""Tests for core data models."""

from agentest.core import (
    AgentTrace,
    LLMResponse,
    Message,
    Role,
    ToolCall,
    TraceSession,
    diff_traces,
)


def test_tool_call_success():
    tc = ToolCall(name="read_file", arguments={"path": "test.txt"}, result="contents")
    assert tc.succeeded
    assert tc.name == "read_file"


def test_tool_call_failure():
    tc = ToolCall(name="read_file", arguments={"path": "missing.txt"}, error="File not found")
    assert not tc.succeeded


def test_llm_response_cost_estimate():
    resp = LLMResponse(
        model="claude-sonnet-4-6",
        content="Hello",
        input_tokens=1000,
        output_tokens=500,
    )
    cost = resp.cost_estimate
    assert cost > 0
    # 1000 * 3.0/1M + 500 * 15.0/1M = 0.003 + 0.0075 = 0.0105
    assert abs(cost - 0.0105) < 0.001


def test_llm_response_unknown_model():
    resp = LLMResponse(model="unknown-model", input_tokens=1000, output_tokens=500)
    assert resp.cost_estimate == 0.0


def test_cost_estimate_exact_match_over_prefix():
    """Exact model name should match before prefix fallback."""
    from agentest.core import reset_model_pricing, set_model_pricing

    set_model_pricing("gpt-4o", 5.0, 15.0)
    set_model_pricing("gpt-4o-mini", 0.15, 0.6)

    resp_mini = LLMResponse(model="gpt-4o-mini", input_tokens=1_000_000, output_tokens=0)
    resp_full = LLMResponse(model="gpt-4o", input_tokens=1_000_000, output_tokens=0)

    # gpt-4o-mini should use mini pricing, not gpt-4o pricing
    assert abs(resp_mini.cost_estimate - 0.15) < 0.01
    assert abs(resp_full.cost_estimate - 5.0) < 0.01
    reset_model_pricing()


def test_cost_estimate_uses_startswith_not_contains():
    """Model matching should use startswith, not substring contains."""
    resp = LLMResponse(model="my-custom-gpt-4o", input_tokens=1000, output_tokens=500)
    # "gpt-4o" should NOT match "my-custom-gpt-4o" via substring
    assert resp.cost_estimate == 0.0


def test_diff_traces_duplicate_tool_calls():
    """diff_traces should detect frequency differences in tool calls."""
    trace_a = AgentTrace(task="test")
    trace_a.tool_calls.append(ToolCall(name="read_file", result="ok"))
    trace_a.finalize(success=True)

    trace_b = AgentTrace(task="test")
    trace_b.tool_calls.append(ToolCall(name="read_file", result="ok"))
    trace_b.tool_calls.append(ToolCall(name="read_file", result="ok2"))
    trace_b.tool_calls.append(ToolCall(name="read_file", result="ok3"))
    trace_b.finalize(success=True)

    result = diff_traces(trace_a, trace_b)
    # trace_b has 2 extra read_file calls
    assert result["tool_calls"]["added"].count("read_file") == 2
    assert result["tool_calls"]["removed"] == []


def test_agent_trace_properties():
    trace = AgentTrace(task="test task")
    trace.llm_responses.append(
        LLMResponse(model="test", input_tokens=100, output_tokens=50, total_tokens=150)
    )
    trace.tool_calls.append(ToolCall(name="tool1", result="ok"))
    trace.tool_calls.append(ToolCall(name="tool2", error="failed"))

    assert trace.total_tokens == 150
    assert trace.total_tool_calls == 2
    assert len(trace.failed_tool_calls) == 1


def test_agent_trace_finalize():
    trace = AgentTrace(task="test")
    assert trace.duration_ms is None

    trace.finalize(success=True)
    assert trace.success is True
    assert trace.duration_ms is not None
    assert trace.duration_ms >= 0


def test_trace_session():
    session = TraceSession(name="test session")
    session.traces.append(AgentTrace(task="t1", success=True))
    session.traces.append(AgentTrace(task="t2", success=False))
    session.traces.append(AgentTrace(task="t3", success=True))

    assert session.total_traces == 3
    assert session.successful_traces == 2
    assert abs(session.success_rate - 2 / 3) < 0.01


def test_message():
    msg = Message(role=Role.USER, content="Hello")
    assert msg.role == Role.USER
    assert msg.content == "Hello"


def test_diff_traces_basic():
    trace_a = AgentTrace(task="summarize")
    trace_a.llm_responses.append(
        LLMResponse(model="claude-sonnet-4-6", input_tokens=100, output_tokens=50, total_tokens=150)
    )
    trace_a.tool_calls.append(ToolCall(name="read_file", arguments={"path": "a.txt"}, result="ok"))
    trace_a.finalize(success=True)

    trace_b = AgentTrace(task="summarize")
    trace_b.llm_responses.append(
        LLMResponse(
            model="claude-sonnet-4-6",
            input_tokens=200,
            output_tokens=100,
            total_tokens=300,
        )
    )
    trace_b.tool_calls.append(ToolCall(name="read_file", arguments={"path": "a.txt"}, result="ok"))
    trace_b.tool_calls.append(ToolCall(name="search", arguments={"q": "test"}, result=["r"]))
    trace_b.finalize(success=True)

    result = diff_traces(trace_a, trace_b)

    assert result["summary"]["total_tokens"]["delta"] == 150
    assert result["summary"]["tool_call_count"]["delta"] == 1
    assert "search" in result["tool_calls"]["added"]
    assert result["tool_calls"]["same_sequence"] is False


def test_diff_traces_errors():
    trace_a = AgentTrace(task="test")
    trace_a.tool_calls.append(ToolCall(name="api", error="timeout"))
    trace_a.finalize(success=False, error="failed")

    trace_b = AgentTrace(task="test")
    trace_b.tool_calls.append(ToolCall(name="api", result="ok"))
    trace_b.finalize(success=True)

    result = diff_traces(trace_a, trace_b)

    assert result["summary"]["success"]["a"] is False
    assert result["summary"]["success"]["b"] is True
    assert "timeout" in result["errors"]["resolved_errors"]
