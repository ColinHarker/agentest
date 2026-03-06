"""Tests for regression detection."""

import tempfile
from pathlib import Path

from agentest.core import AgentTrace, LLMResponse, ToolCall
from agentest.recorder.recorder import Recorder
from agentest.regression import (
    RegressionDetector,
    RegressionEvaluator,
    RegressionThresholds,
    _safe_task_filename,
)


def _make_trace(
    task="test task",
    success=True,
    tokens=100,
    cost_model="gpt-4o-mini",
    tool_calls=None,
    duration=True,
):
    trace = AgentTrace(
        task=task,
        success=success,
        llm_responses=[
            LLMResponse(
                model=cost_model,
                input_tokens=tokens,
                output_tokens=tokens // 2,
                total_tokens=tokens + tokens // 2,
                latency_ms=100.0,
            ),
        ],
        tool_calls=tool_calls
        or [
            ToolCall(name="read", arguments={}, result="ok"),
        ],
    )
    if duration:
        trace.finalize(success=success)
    return trace


class TestSafeTaskFilename:
    def test_basic(self):
        assert _safe_task_filename("Hello World") == "hello_world"

    def test_special_chars(self):
        assert _safe_task_filename("Read file/path.txt") == "read_filepathtxt"

    def test_empty(self):
        assert _safe_task_filename("") == "unnamed"


class TestRegressionDetector:
    def test_no_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = RegressionDetector(baseline_dir=tmpdir)
            trace = _make_trace()
            result = detector.check(trace)
            assert result.passed
            assert len(result.regressions) == 0

    def test_no_regression(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = RegressionDetector(
                baseline_dir=tmpdir,
                thresholds=RegressionThresholds(latency_increase=10.0),
            )

            baseline = _make_trace(tokens=100)
            detector.update_baseline(baseline)

            current = _make_trace(tokens=105)  # 5% increase, under 10% threshold
            result = detector.check(current)
            assert result.passed

    def test_cost_regression(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = RegressionDetector(
                baseline_dir=tmpdir,
                thresholds=RegressionThresholds(token_increase=0.1),
            )

            baseline = _make_trace(tokens=100)
            detector.update_baseline(baseline)

            current = _make_trace(tokens=200)  # 100% increase
            result = detector.check(current)
            assert not result.passed
            assert any(r.metric == "total_tokens" for r in result.regressions)

    def test_success_regression(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = RegressionDetector(baseline_dir=tmpdir)

            baseline = _make_trace(success=True)
            detector.update_baseline(baseline)

            current = _make_trace(success=False)
            result = detector.check(current)
            assert not result.passed
            assert any(r.metric == "success" for r in result.regressions)

    def test_error_rate_regression(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = RegressionDetector(
                baseline_dir=tmpdir,
                thresholds=RegressionThresholds(error_rate_increase=0.05),
            )

            baseline = _make_trace(tool_calls=[ToolCall(name="a", arguments={}, result="ok")])
            detector.update_baseline(baseline)

            current = _make_trace(
                tool_calls=[
                    ToolCall(name="a", arguments={}, error="fail"),
                ]
            )
            result = detector.check(current)
            assert not result.passed
            assert any(r.metric == "error_rate" for r in result.regressions)

    def test_improvement_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = RegressionDetector(
                baseline_dir=tmpdir,
                thresholds=RegressionThresholds(
                    token_increase=0.1,
                    latency_increase=10.0,  # high threshold to ignore timing noise
                ),
            )

            baseline = _make_trace(tokens=200)
            detector.update_baseline(baseline)

            current = _make_trace(tokens=50)  # 75% decrease
            result = detector.check(current)
            assert result.passed
            assert len(result.improvements) > 0

    def test_critical_severity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = RegressionDetector(
                baseline_dir=tmpdir,
                thresholds=RegressionThresholds(token_increase=0.1),
            )

            baseline = _make_trace(tokens=100)
            detector.update_baseline(baseline)

            current = _make_trace(tokens=300)  # 200% increase, > 2x threshold
            result = detector.check(current)
            assert not result.passed
            token_reg = next(r for r in result.regressions if r.metric == "total_tokens")
            assert token_reg.severity == "critical"

    def test_check_all(self):
        with tempfile.TemporaryDirectory() as baseline_dir:
            with tempfile.TemporaryDirectory() as traces_dir:
                detector = RegressionDetector(baseline_dir=baseline_dir)

                # Save baseline
                baseline = _make_trace(task="task1", tokens=100)
                detector.update_baseline(baseline)

                # Save current traces
                current = _make_trace(task="task1", tokens=105)
                rec = Recorder(task="task1")
                rec.trace = current
                rec.save(Path(traces_dir) / "task1.yaml")

                results = detector.check_all(traces_dir)
                assert len(results) == 1
                assert results[0].passed

    def test_update_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = RegressionDetector(baseline_dir=tmpdir)
            trace = _make_trace(task="my task")
            path = detector.update_baseline(trace)
            assert path.exists()
            loaded = Recorder.load(path)
            assert loaded.task == "my task"


class TestRegressionEvaluator:
    def test_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = RegressionEvaluator(baseline_dir=tmpdir)
            trace = _make_trace()
            result = evaluator.evaluate(trace)
            assert result.passed
            assert result.score == 1.0

    def test_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = RegressionEvaluator(
                baseline_dir=tmpdir,
                thresholds=RegressionThresholds(token_increase=0.1),
            )
            baseline = _make_trace(tokens=100)
            evaluator.detector.update_baseline(baseline)

            current = _make_trace(tokens=300)
            result = evaluator.evaluate(current)
            assert not result.passed
            assert result.score < 1.0
            assert "Regressions" in result.message
