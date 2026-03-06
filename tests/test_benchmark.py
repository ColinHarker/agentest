"""Tests for benchmarking and model comparison."""

import tempfile
from pathlib import Path

from agentest.benchmark.comparison import ModelComparison
from agentest.benchmark.runner import BenchmarkResult, BenchmarkRunner, BenchmarkTask, TaskResult
from agentest.core import AgentTrace, LLMResponse, ToolCall
from agentest.evaluators.builtin import TaskCompletionEvaluator


def _make_successful_trace(model: str = "test") -> AgentTrace:
    trace = AgentTrace(task="test task")
    trace.llm_responses.append(
        LLMResponse(
            model=model,
            content="done",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )
    )
    trace.tool_calls.append(ToolCall(name="tool1", result="ok"))
    trace.finalize(success=True)
    return trace


def test_benchmark_runner():
    runner = BenchmarkRunner(
        name="test_bench",
        evaluators=[TaskCompletionEvaluator(min_messages=0)],
    )

    runner.add_task(
        BenchmarkTask(
            name="task1",
            description="Test task 1",
            task_fn=lambda: _make_successful_trace(),
        )
    )

    result = runner.run()
    assert result.total_tasks == 1
    assert result.passed_tasks == 1
    assert result.pass_rate == 1.0


def test_benchmark_runner_failure():
    def failing_task() -> AgentTrace:
        trace = AgentTrace(task="fail")
        trace.finalize(success=False, error="boom")
        return trace

    runner = BenchmarkRunner(
        name="fail_bench",
        evaluators=[TaskCompletionEvaluator(min_messages=0)],
    )
    runner.add_task(BenchmarkTask(name="fail_task", description="Fails", task_fn=failing_task))

    result = runner.run()
    assert result.passed_tasks == 0


def test_benchmark_runner_exception():
    def exploding_task() -> AgentTrace:
        raise RuntimeError("kaboom")

    runner = BenchmarkRunner(name="explode_bench")
    runner.add_task(BenchmarkTask(name="explode", description="Explodes", task_fn=exploding_task))

    result = runner.run()
    assert result.tasks[0].error == "kaboom"


def test_benchmark_run_n_times():
    runner = BenchmarkRunner(name="repeat_bench")
    runner.add_task(
        BenchmarkTask(
            name="task",
            description="Repeatable",
            task_fn=lambda: _make_successful_trace(),
        )
    )

    results = runner.run_n_times(n=3)
    assert len(results) == 3


def test_model_comparison():
    comparison = ModelComparison()

    # Create results for two models
    sonnet_result = BenchmarkResult(
        name="bench",
        tasks=[
            TaskResult(
                task_name="task1",
                trace=_make_successful_trace("claude-sonnet-4-6"),
                eval_results=[],
                duration_ms=100,
            )
        ],
        total_time_ms=100,
    )

    gpt_result = BenchmarkResult(
        name="bench",
        tasks=[
            TaskResult(
                task_name="task1",
                trace=_make_successful_trace("gpt-4o"),
                eval_results=[],
                duration_ms=200,
            )
        ],
        total_time_ms=200,
    )

    comparison.add_result("claude-sonnet-4-6", sonnet_result)
    comparison.add_result("gpt-4o", gpt_result)

    table = comparison.comparison_table()
    assert len(table) == 2

    best_latency = comparison.best_model("latency")
    assert best_latency == "claude-sonnet-4-6"  # 100ms vs 200ms


def test_model_comparison_diff():
    comparison = ModelComparison()

    r1 = BenchmarkResult(name="b", tasks=[], total_time_ms=0)
    r2 = BenchmarkResult(name="b", tasks=[], total_time_ms=0)

    comparison.add_result("model_a", r1)
    comparison.add_result("model_b", r2)

    diff = comparison.diff("model_a", "model_b")
    assert "models" in diff
    assert "better_on_score" in diff


def _make_comparison_with_data() -> ModelComparison:
    comparison = ModelComparison()

    sonnet_result = BenchmarkResult(
        name="bench",
        tasks=[
            TaskResult(
                task_name="task1",
                trace=_make_successful_trace("claude-sonnet-4-6"),
                eval_results=[],
                duration_ms=100,
            )
        ],
        total_time_ms=100,
    )

    gpt_result = BenchmarkResult(
        name="bench",
        tasks=[
            TaskResult(
                task_name="task1",
                trace=_make_successful_trace("gpt-4o"),
                eval_results=[],
                duration_ms=200,
            )
        ],
        total_time_ms=200,
    )

    comparison.add_result("claude-sonnet-4-6", sonnet_result)
    comparison.add_result("gpt-4o", gpt_result)
    return comparison


def test_comparison_to_csv():
    comparison = _make_comparison_with_data()
    csv_str = comparison.to_csv()

    assert "model" in csv_str
    assert "claude-sonnet-4-6" in csv_str
    assert "gpt-4o" in csv_str

    # Test saving to file
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "comparison.csv"
        comparison.to_csv(path)
        assert path.exists()
        content = path.read_text()
        assert "model" in content


def test_comparison_to_markdown():
    comparison = _make_comparison_with_data()
    md = comparison.to_markdown()

    assert "| Model" in md
    assert "claude-sonnet-4-6" in md
    assert "gpt-4o" in md
    assert "---" in md  # separator row

    # Test saving to file
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "comparison.md"
        comparison.to_markdown(path)
        assert path.exists()


def test_comparison_empty_csv():
    comparison = ModelComparison()
    assert comparison.to_csv() == ""


def test_comparison_empty_markdown():
    comparison = ModelComparison()
    assert comparison.to_markdown() == ""


async def test_benchmark_runner_async():
    runner = BenchmarkRunner(
        name="async_bench",
        evaluators=[],
    )

    runner.add_task(
        BenchmarkTask(
            name="task1",
            description="Task 1",
            task_fn=lambda: _make_successful_trace(),
        )
    )
    runner.add_task(
        BenchmarkTask(
            name="task2",
            description="Task 2",
            task_fn=lambda: _make_successful_trace(),
        )
    )

    result = await runner.run_async(max_concurrency=2)
    assert result.total_tasks == 2
    assert len(result.tasks) == 2


async def test_benchmark_runner_async_with_coroutine():
    async def async_task() -> AgentTrace:
        return _make_successful_trace()

    runner = BenchmarkRunner(name="async_coro_bench")
    runner.add_task(
        BenchmarkTask(
            name="async_task",
            description="Async task",
            task_fn=async_task,
        )
    )

    result = await runner.run_async()
    assert result.total_tasks == 1
    assert result.tasks[0].error is None
