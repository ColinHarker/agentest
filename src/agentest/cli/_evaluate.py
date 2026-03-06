"""Evaluate command."""

from __future__ import annotations

import sys

import click

from agentest.cli._main import console, main, reporter
from agentest.evaluators.base import CompositeEvaluator
from agentest.evaluators.builtin import (
    CostEvaluator,
    LatencyEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)
from agentest.recorder.recorder import Recorder
from agentest.reporters.json_reporter import JSONReporter


@main.command()
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--max-cost", type=float, default=None, help="Max cost budget in USD.")
@click.option("--max-tokens", type=int, default=None, help="Max token budget.")
@click.option("--max-time-ms", type=float, default=None, help="Max total time in ms.")
@click.option("--check-safety/--no-check-safety", default=True, help="Run safety checks.")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save JSON report to file.")
def evaluate(
    trace_path: str,
    max_cost: float | None,
    max_tokens: int | None,
    max_time_ms: float | None,
    check_safety: bool,
    output: str | None,
) -> None:
    """Evaluate a recorded agent trace."""
    trace = Recorder.load(trace_path)

    evaluators = [TaskCompletionEvaluator(), ToolUsageEvaluator()]

    if check_safety:
        evaluators.append(SafetyEvaluator())
    if max_cost is not None or max_tokens is not None:
        evaluators.append(CostEvaluator(max_cost=max_cost, max_tokens=max_tokens))
    if max_time_ms is not None:
        evaluators.append(LatencyEvaluator(max_total_ms=max_time_ms))

    composite = CompositeEvaluator(evaluators)
    results = composite.evaluate_all(trace)

    reporter.print_eval_results(results, title=f"Evaluation: {trace_path}")

    all_passed = all(r.passed for r in results)

    if output:
        json_reporter = JSONReporter()
        json_reporter.save(JSONReporter.eval_results_to_dict(results), output)
        console.print(f"\nReport saved to: {output}")

    if not all_passed:
        sys.exit(1)
