"""Tests for statistical analysis."""

import tempfile
from pathlib import Path

from agentest.core import AgentTrace, LLMResponse, ToolCall
from agentest.stats import (
    SLO,
    StatsAnalyzer,
    TrendDirection,
)


def _make_trace(task="test task", tokens=100, success=True):
    trace = AgentTrace(
        task=task,
        success=success,
        llm_responses=[
            LLMResponse(
                model="gpt-4o-mini",
                input_tokens=tokens,
                output_tokens=tokens // 2,
                total_tokens=tokens + tokens // 2,
            ),
        ],
        tool_calls=[ToolCall(name="test", arguments={}, result="ok")],
    )
    trace.finalize(success=success)
    return trace


class TestStatsAnalyzer:
    def test_add_trace(self):
        analyzer = StatsAnalyzer()
        trace = _make_trace()
        analyzer.add_trace(trace, score=0.9)
        assert "test task" in analyzer.samples
        assert len(analyzer.samples["test task"]) == 1
        assert analyzer.samples["test task"][0].score == 0.9

    def test_trend_stable(self):
        analyzer = StatsAnalyzer()
        for _ in range(5):
            analyzer.add_trace(_make_trace(tokens=100), score=0.9)
        result = analyzer.trend("test task", metric="score")
        assert result.direction == TrendDirection.STABLE
        assert result.samples == 5

    def test_trend_improving_score(self):
        analyzer = StatsAnalyzer()
        for i in range(10):
            analyzer.add_trace(_make_trace(), score=0.5 + i * 0.05)
        result = analyzer.trend("test task", metric="score")
        assert result.direction == TrendDirection.IMPROVING
        assert result.slope > 0

    def test_trend_degrading_cost(self):
        analyzer = StatsAnalyzer()
        for i in range(10):
            analyzer.add_trace(_make_trace(tokens=100 + i * 50))
        result = analyzer.trend("test task", metric="tokens")
        assert result.direction == TrendDirection.DEGRADING
        assert result.slope > 0

    def test_trend_too_few_samples(self):
        analyzer = StatsAnalyzer()
        analyzer.add_trace(_make_trace(), score=0.9)
        result = analyzer.trend("test task", metric="score")
        assert result.direction == TrendDirection.STABLE
        assert result.samples == 1

    def test_trend_window(self):
        analyzer = StatsAnalyzer()
        for i in range(20):
            analyzer.add_trace(_make_trace(), score=0.5 + i * 0.02)
        result = analyzer.trend("test task", metric="score", window=5)
        assert result.samples == 5

    def test_confidence_interval(self):
        analyzer = StatsAnalyzer()
        for _ in range(10):
            analyzer.add_trace(_make_trace(), score=0.9)
        ci = analyzer.confidence_interval("test task", metric="score")
        assert ci.mean == 0.9
        assert ci.ci_lower <= 0.9
        assert ci.ci_upper >= 0.9
        assert ci.samples == 10

    def test_confidence_interval_single_sample(self):
        analyzer = StatsAnalyzer()
        analyzer.add_trace(_make_trace(), score=0.85)
        ci = analyzer.confidence_interval("test task", metric="score")
        assert ci.mean == 0.85
        assert ci.ci_lower == 0.85
        assert ci.ci_upper == 0.85
        assert ci.samples == 1

    def test_check_slo_pass(self):
        analyzer = StatsAnalyzer()
        for _ in range(5):
            analyzer.add_trace(_make_trace(tokens=100), score=0.95)
        slo = SLO(metric="score", target=0.8, comparison="gte")
        result = analyzer.check_slo("test task", slo)
        assert result.compliant
        assert result.compliance_rate == 1.0

    def test_check_slo_fail(self):
        analyzer = StatsAnalyzer()
        for _ in range(5):
            analyzer.add_trace(_make_trace(), score=0.5)
        slo = SLO(metric="score", target=0.8, comparison="gte")
        result = analyzer.check_slo("test task", slo)
        assert not result.compliant
        assert result.compliance_rate == 0.0

    def test_check_slo_lte(self):
        analyzer = StatsAnalyzer()
        for _ in range(5):
            analyzer.add_trace(_make_trace(tokens=100))
        slo = SLO(metric="tokens", target=200.0, comparison="lte")
        result = analyzer.check_slo("test task", slo)
        assert result.compliant

    def test_check_slos_multiple(self):
        analyzer = StatsAnalyzer()
        for _ in range(5):
            analyzer.add_trace(_make_trace(), score=0.95)
        slos = [
            SLO(metric="score", target=0.8, comparison="gte"),
            SLO(metric="tokens", target=500.0, comparison="lte"),
        ]
        results = analyzer.check_slos(slos)
        assert len(results) == 2
        assert all(r.compliant for r in results)

    def test_check_slo_empty(self):
        analyzer = StatsAnalyzer()
        slo = SLO(metric="score", target=0.8, comparison="gte")
        result = analyzer.check_slo("nonexistent", slo)
        assert not result.compliant
        assert result.samples == 0

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.json"

            analyzer = StatsAnalyzer()
            for i in range(5):
                analyzer.add_trace(_make_trace(), score=0.8 + i * 0.02)
            analyzer.save(path)

            loaded = StatsAnalyzer.load(path)
            assert "test task" in loaded.samples
            assert len(loaded.samples["test task"]) == 5

    def test_load_in_constructor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.json"

            analyzer = StatsAnalyzer()
            analyzer.add_trace(_make_trace(), score=0.9)
            analyzer.save(path)

            analyzer2 = StatsAnalyzer(history_file=path)
            assert len(analyzer2.samples["test task"]) == 1

    def test_add_benchmark_result(self):
        """Test adding benchmark results."""
        from agentest.benchmark.runner import BenchmarkResult, TaskResult

        analyzer = StatsAnalyzer()
        trace = _make_trace()
        task_result = TaskResult(
            task_name="test task",
            trace=trace,
            eval_results=[],
            duration_ms=100,
        )
        bench_result = BenchmarkResult(
            name="bench",
            tasks=[task_result],
            total_time_ms=100,
        )
        analyzer.add_benchmark_result(bench_result)
        assert "test task" in analyzer.samples
