"""Tests for custom metrics framework."""

from agentest.core import AgentTrace, LLMResponse, ToolCall
from agentest.evaluators.metrics import (
    CostPerTokenMetric,
    ErrorRateMetric,
    LLMCallCountMetric,
    Metric,
    MetricEvaluator,
    MetricResult,
    TokenEfficiencyMetric,
    ToolCallCountMetric,
)


def _make_trace(**kwargs):
    """Create a trace with sensible defaults."""
    defaults = {
        "task": "test task",
        "success": True,
        "llm_responses": [
            LLMResponse(model="test-model", input_tokens=100, output_tokens=50, total_tokens=150),
        ],
        "tool_calls": [
            ToolCall(name="read_file", arguments={"path": "test.txt"}, result="contents"),
            ToolCall(name="write_file", arguments={"path": "out.txt"}, result="ok"),
        ],
    }
    defaults.update(kwargs)
    return AgentTrace(**defaults)


class TestMetric:
    def test_custom_metric(self):
        """Custom metrics can be created by subclassing."""

        class MyMetric(Metric):
            name = "my_metric"

            def compute(self, trace):
                return len(trace.messages) * 2.0

        metric = MyMetric()
        trace = _make_trace()
        assert metric.compute(trace) == 0.0
        assert repr(metric) == "MyMetric(name='my_metric')"


class TestTokenEfficiencyMetric:
    def test_basic(self):
        trace = _make_trace()
        metric = TokenEfficiencyMetric()
        # 150 tokens / 2 tool calls = 75
        assert metric.compute(trace) == 75.0

    def test_no_tool_calls(self):
        trace = _make_trace(tool_calls=[])
        metric = TokenEfficiencyMetric()
        # 150 tokens / max(0, 1) = 150
        assert metric.compute(trace) == 150.0


class TestErrorRateMetric:
    def test_no_errors(self):
        trace = _make_trace()
        metric = ErrorRateMetric()
        assert metric.compute(trace) == 0.0

    def test_with_errors(self):
        trace = _make_trace(
            tool_calls=[
                ToolCall(name="a", arguments={}, result="ok"),
                ToolCall(name="b", arguments={}, error="failed"),
            ]
        )
        metric = ErrorRateMetric()
        assert metric.compute(trace) == 0.5

    def test_no_tool_calls(self):
        trace = _make_trace(tool_calls=[])
        metric = ErrorRateMetric()
        assert metric.compute(trace) == 0.0


class TestCostPerTokenMetric:
    def test_no_tokens(self):
        trace = _make_trace(llm_responses=[])
        metric = CostPerTokenMetric()
        assert metric.compute(trace) == 0.0


class TestToolCallCountMetric:
    def test_basic(self):
        trace = _make_trace()
        metric = ToolCallCountMetric()
        assert metric.compute(trace) == 2.0


class TestLLMCallCountMetric:
    def test_basic(self):
        trace = _make_trace()
        metric = LLMCallCountMetric()
        assert metric.compute(trace) == 1.0


class TestMetricResult:
    def test_repr_with_pass(self):
        r = MetricResult(metric="test", value=0.5, threshold=1.0, passed=True)
        assert "PASS" in repr(r)

    def test_repr_with_fail(self):
        r = MetricResult(metric="test", value=1.5, threshold=1.0, passed=False)
        assert "FAIL" in repr(r)

    def test_repr_no_threshold(self):
        r = MetricResult(metric="test", value=0.5)
        assert "PASS" not in repr(r)
        assert "FAIL" not in repr(r)


class TestMetricEvaluator:
    def test_all_pass(self):
        trace = _make_trace()
        evaluator = MetricEvaluator(
            metrics=[
                (TokenEfficiencyMetric(), 200.0),  # 75 <= 200
                (ErrorRateMetric(), 0.5),  # 0.0 <= 0.5
            ]
        )
        result = evaluator.evaluate(trace)
        assert result.passed
        assert result.score == 1.0

    def test_some_fail(self):
        trace = _make_trace()
        evaluator = MetricEvaluator(
            metrics=[
                (TokenEfficiencyMetric(), 50.0),  # 75 > 50, FAIL
                (ErrorRateMetric(), 0.5),  # 0.0 <= 0.5, PASS
            ]
        )
        result = evaluator.evaluate(trace)
        assert not result.passed
        assert result.score == 0.5

    def test_no_thresholds(self):
        trace = _make_trace()
        evaluator = MetricEvaluator(
            metrics=[
                (TokenEfficiencyMetric(), None),
                (ErrorRateMetric(), None),
            ]
        )
        result = evaluator.evaluate(trace)
        assert result.passed
        assert result.score == 1.0
        assert result.message == "No thresholds set"

    def test_compute_all(self):
        trace = _make_trace()
        evaluator = MetricEvaluator(
            metrics=[
                (TokenEfficiencyMetric(), 200.0),
                (ErrorRateMetric(), None),
            ]
        )
        results = evaluator.compute_all(trace)
        assert len(results) == 2
        assert results[0].metric == "token_efficiency"
        assert results[0].passed is True
        assert results[1].metric == "error_rate"
        assert results[1].passed is None  # no threshold
