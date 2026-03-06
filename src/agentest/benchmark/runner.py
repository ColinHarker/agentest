"""Benchmark runner for evaluating agents across tasks and models."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from agentest.core import AgentTrace, TraceSession
from agentest.evaluators.base import CompositeEvaluator, EvalResult, Evaluator


@dataclass
class BenchmarkTask:
    """A single benchmark task definition."""

    name: str
    description: str
    task_fn: Callable[..., AgentTrace]
    expected_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 300


@dataclass
class BenchmarkResult:
    """Result of running a benchmark suite."""

    name: str
    tasks: list[TaskResult]
    total_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tasks(self) -> int:
        return len(self.tasks)

    @property
    def passed_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.all_passed)

    @property
    def pass_rate(self) -> float:
        return self.passed_tasks / self.total_tasks if self.tasks else 0.0

    @property
    def avg_score(self) -> float:
        scores = [t.avg_score for t in self.tasks if t.avg_score is not None]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def total_cost(self) -> float:
        return sum(t.trace.total_cost for t in self.tasks if t.trace)

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total_tasks": self.total_tasks,
            "passed": self.passed_tasks,
            "pass_rate": f"{self.pass_rate:.1%}",
            "avg_score": f"{self.avg_score:.3f}",
            "total_cost": f"${self.total_cost:.4f}",
            "total_time_ms": f"{self.total_time_ms:.0f}",
        }


@dataclass
class TaskResult:
    """Result of a single benchmark task."""

    task_name: str
    trace: AgentTrace | None
    eval_results: list[EvalResult]
    error: str | None = None
    duration_ms: float = 0

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.eval_results) and self.error is None

    @property
    def avg_score(self) -> float | None:
        if not self.eval_results:
            return None
        return sum(r.score for r in self.eval_results) / len(self.eval_results)


class BenchmarkRunner:
    """Runs benchmark tasks and evaluates results.

    Usage:
        runner = BenchmarkRunner(
            name="my_agent_benchmark",
            evaluators=[
                TaskCompletionEvaluator(),
                SafetyEvaluator(),
                CostEvaluator(max_cost=0.10),
            ],
        )

        runner.add_task(BenchmarkTask(
            name="file_summary",
            description="Summarize a file",
            task_fn=lambda: run_agent("Summarize README.md"),
        ))

        result = runner.run()
        print(result.summary())
    """

    def __init__(
        self,
        name: str = "benchmark",
        evaluators: list[Evaluator] | None = None,
    ) -> None:
        self.name = name
        self.evaluators = evaluators or []
        self.tasks: list[BenchmarkTask] = []

    def add_task(self, task: BenchmarkTask) -> None:
        """Add a task to the benchmark suite."""
        self.tasks.append(task)

    def add_evaluator(self, evaluator: Evaluator) -> None:
        """Add an evaluator to run on each task."""
        self.evaluators.append(evaluator)

    def run(self, **kwargs: Any) -> BenchmarkResult:
        """Run all benchmark tasks and evaluate results."""
        start = time.time()
        task_results: list[TaskResult] = []

        composite = CompositeEvaluator(self.evaluators) if self.evaluators else None

        for task in self.tasks:
            task_result = self._run_task(task, composite, **kwargs)
            task_results.append(task_result)

        total_time = (time.time() - start) * 1000

        return BenchmarkResult(
            name=self.name,
            tasks=task_results,
            total_time_ms=total_time,
        )

    def _run_task(
        self,
        task: BenchmarkTask,
        composite: CompositeEvaluator | None,
        **kwargs: Any,
    ) -> TaskResult:
        """Run a single task and evaluate it."""
        start = time.time()

        try:
            trace = task.task_fn(**kwargs)
            duration = (time.time() - start) * 1000

            eval_results = []
            if composite:
                eval_results = composite.evaluate_all(trace)

            return TaskResult(
                task_name=task.name,
                trace=trace,
                eval_results=eval_results,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TaskResult(
                task_name=task.name,
                trace=None,
                eval_results=[],
                error=str(e),
                duration_ms=duration,
            )

    async def run_async(self, max_concurrency: int = 5, **kwargs: Any) -> BenchmarkResult:
        """Run all benchmark tasks concurrently and evaluate results.

        Args:
            max_concurrency: Maximum number of tasks to run in parallel.
        """
        start = time.time()
        composite = CompositeEvaluator(self.evaluators) if self.evaluators else None
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_with_limit(task: BenchmarkTask) -> TaskResult:
            async with semaphore:
                return await self._run_task_async(task, composite, **kwargs)

        task_results = await asyncio.gather(
            *(run_with_limit(task) for task in self.tasks)
        )

        total_time = (time.time() - start) * 1000

        return BenchmarkResult(
            name=self.name,
            tasks=list(task_results),
            total_time_ms=total_time,
        )

    async def _run_task_async(
        self,
        task: BenchmarkTask,
        composite: CompositeEvaluator | None,
        **kwargs: Any,
    ) -> TaskResult:
        """Run a single task asynchronously and evaluate it."""
        start = time.time()

        try:
            result = task.task_fn(**kwargs)
            # Support both sync and async task functions
            if asyncio.iscoroutine(result):
                trace = await result
            else:
                trace = result
            duration = (time.time() - start) * 1000

            eval_results = []
            if composite:
                eval_results = composite.evaluate_all(trace)

            return TaskResult(
                task_name=task.name,
                trace=trace,
                eval_results=eval_results,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TaskResult(
                task_name=task.name,
                trace=None,
                eval_results=[],
                error=str(e),
                duration_ms=duration,
            )

    def run_n_times(self, n: int = 3, **kwargs: Any) -> list[BenchmarkResult]:
        """Run the benchmark suite N times for statistical significance."""
        return [self.run(**kwargs) for _ in range(n)]
