"""Tests for console and JSON reporters."""

import json
from io import StringIO

from rich.console import Console

from agentest.benchmark.comparison import ModelComparison
from agentest.benchmark.runner import BenchmarkResult, TaskResult
from agentest.core import AgentTrace, LLMResponse
from agentest.evaluators.base import EvalResult
from agentest.reporters.console import ConsoleReporter
from agentest.reporters.json_reporter import JSONReporter

# ---- Helpers ----


def _make_eval_results():
    return [
        EvalResult(evaluator="task_completion", score=1.0, passed=True, message="OK"),
        EvalResult(evaluator="safety", score=0.5, passed=False, message="Unsafe command found"),
    ]


def _make_benchmark_result():
    trace = AgentTrace(task="test")
    trace.llm_responses.append(
        LLMResponse(
            model="test",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )
    )
    trace.finalize(success=True)

    task1 = TaskResult(
        task_name="task_a",
        trace=trace,
        eval_results=[EvalResult(evaluator="e1", score=1.0, passed=True, message="good")],
        duration_ms=100,
    )
    task2 = TaskResult(
        task_name="task_b",
        trace=trace,
        eval_results=[EvalResult(evaluator="e1", score=0.3, passed=False, message="bad")],
        error="something broke",
        duration_ms=200,
    )
    return BenchmarkResult(name="test_bench", tasks=[task1, task2], total_time_ms=300)


def _make_comparison():
    comp = ModelComparison()
    comp.add_result("model_a", _make_benchmark_result())
    comp.add_result("model_b", _make_benchmark_result())
    return comp


# ---- ConsoleReporter ----


def test_console_print_eval_results():
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    reporter = ConsoleReporter(console)
    reporter.print_eval_results(_make_eval_results(), title="Test Results")
    output = buf.getvalue()
    assert "task_completion" in output
    assert "safety" in output


def test_console_print_benchmark_result():
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    reporter = ConsoleReporter(console)
    reporter.print_benchmark_result(_make_benchmark_result())
    output = buf.getvalue()
    assert "task_a" in output
    assert "task_b" in output


def test_console_print_comparison():
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    reporter = ConsoleReporter(console)
    reporter.print_comparison(_make_comparison())
    output = buf.getvalue()
    assert "model_a" in output
    assert "model_b" in output


def test_console_print_comparison_empty():
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    reporter = ConsoleReporter(console)
    reporter.print_comparison(ModelComparison())
    output = buf.getvalue()
    assert "No comparison data" in output


# ---- JSONReporter ----


def test_json_eval_results_to_dict():
    results = _make_eval_results()
    data = JSONReporter.eval_results_to_dict(results)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["evaluator"] == "task_completion"
    assert data[1]["passed"] is False


def test_json_benchmark_to_dict():
    result = _make_benchmark_result()
    data = JSONReporter.benchmark_to_dict(result)
    assert "summary" in data
    assert "tasks" in data
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["name"] == "task_a"
    assert data["tasks"][0]["passed"] is True


def test_json_comparison_to_dict():
    comp = _make_comparison()
    data = JSONReporter.comparison_to_dict(comp)
    assert "models" in data
    assert "best_score" in data
    assert "best_cost" in data
    assert "model_details" in data
    assert "model_a" in data["model_details"]


def test_json_save(tmp_path):
    reporter = JSONReporter()
    data = {"key": "value", "count": 42}
    path = reporter.save(data, tmp_path / "sub" / "report.json")

    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded["key"] == "value"
    assert loaded["count"] == 42


def test_json_save_list(tmp_path):
    reporter = JSONReporter()
    data = [{"a": 1}, {"b": 2}]
    path = reporter.save(data, tmp_path / "list_report.json")
    loaded = json.loads(path.read_text())
    assert len(loaded) == 2
