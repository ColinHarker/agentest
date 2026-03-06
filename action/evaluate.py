"""Agentest GitHub Action evaluation script.

Reads trace files from a directory, runs configured evaluators,
and outputs results for the GitHub Action.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from agentest.core import AgentTrace
from agentest.evaluators.builtin import (
    CostEvaluator,
    LatencyEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)
from agentest.recorder.recorder import Recorder
from agentest.reporters.json_reporter import JSONReporter


def main() -> None:
    traces_dir = os.environ.get("TRACES_DIR", "traces")
    max_cost = os.environ.get("MAX_COST")
    max_tokens = os.environ.get("MAX_TOKENS")
    check_safety = os.environ.get("CHECK_SAFETY", "true").lower() == "true"
    evaluator_names = os.environ.get("EVALUATORS", "task_completion,safety,tool_usage").split(",")
    output_file = os.environ.get("OUTPUT_FILE", "agentest-report.json")
    fail_on_error = os.environ.get("FAIL_ON_ERROR", "true").lower() == "true"

    # Build evaluator list
    evaluator_map = {
        "task_completion": lambda: TaskCompletionEvaluator(),
        "safety": lambda: SafetyEvaluator(),
        "cost": lambda: CostEvaluator(
            max_cost=float(max_cost) if max_cost else None,
            max_tokens=int(max_tokens) if max_tokens else None,
        ),
        "tool_usage": lambda: ToolUsageEvaluator(),
        "latency": lambda: LatencyEvaluator(),
    }

    evaluators = []
    for name in evaluator_names:
        name = name.strip()
        if name in evaluator_map:
            evaluators.append(evaluator_map[name]())

    if check_safety and "safety" not in evaluator_names:
        evaluators.append(SafetyEvaluator())

    # Load traces
    traces_path = Path(traces_dir)
    if not traces_path.exists():
        print(f"::warning::Traces directory not found: {traces_dir}")
        _write_empty_report(output_file)
        return

    traces: list[AgentTrace] = []
    for f in sorted(traces_path.iterdir()):
        if f.suffix in (".yaml", ".yml", ".json"):
            try:
                traces.append(Recorder.load(f))
            except Exception as e:
                print(f"::warning::Failed to load {f}: {e}")

    if not traces:
        print("::notice::No trace files found to evaluate")
        _write_empty_report(output_file)
        return

    # Evaluate
    all_results = []
    total_passed = 0
    total_failed = 0

    for trace in traces:
        trace_results = [e.evaluate(trace) for e in evaluators]
        all_passed = all(r.passed for r in trace_results)
        avg_score = sum(r.score for r in trace_results) / len(trace_results) if trace_results else 0

        if all_passed:
            total_passed += 1
            icon = "✅"
        else:
            total_failed += 1
            icon = "❌"

        print(f"{icon} {trace.task[:60]} - score: {avg_score:.2f}")
        for r in trace_results:
            status = "✓" if r.passed else "✗"
            print(f"  {status} {r.evaluator}: {r.score:.2f} - {r.message}")

        all_results.append({
            "trace_id": trace.id,
            "task": trace.task,
            "all_passed": all_passed,
            "avg_score": avg_score,
            "results": [r.model_dump() for r in trace_results],
        })

    # Summary
    total = len(traces)
    overall_avg = sum(r["avg_score"] for r in all_results) / total if total else 0

    print(f"\n{'='*50}")
    print(f"Total: {total} | Passed: {total_passed} | Failed: {total_failed} | Avg Score: {overall_avg:.2f}")

    # Save report
    report = {
        "total": total,
        "passed": total_passed,
        "failed": total_failed,
        "avg_score": round(overall_avg, 4),
        "traces": all_results,
    }

    Path(output_file).write_text(json.dumps(report, indent=2, default=str))
    print(f"\nReport saved to: {output_file}")

    # Write GitHub outputs
    _write_outputs(total, total_passed, total_failed, overall_avg, output_file)

    # Exit with error if needed
    if fail_on_error and total_failed > 0:
        print(f"\n::error::{total_failed} trace(s) failed evaluation")
        sys.exit(1)


def _write_empty_report(output_file: str) -> None:
    """Write an empty evaluation report and GitHub outputs."""
    report = {"total": 0, "passed": 0, "failed": 0, "avg_score": 0.0, "traces": []}
    Path(output_file).write_text(json.dumps(report, indent=2))
    _write_outputs(0, 0, 0, 0.0, output_file)


def _write_outputs(
    total: int, passed: int, failed: int, avg_score: float, report_path: str
) -> None:
    """Write GitHub Action outputs."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"total={total}\n")
            f.write(f"passed={passed}\n")
            f.write(f"failed={failed}\n")
            f.write(f"avg_score={avg_score:.4f}\n")
            f.write(f"report_path={report_path}\n")


if __name__ == "__main__":
    main()
