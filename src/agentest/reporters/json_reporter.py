"""JSON reporter for machine-readable evaluation output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentest.benchmark.runner import BenchmarkResult
from agentest.benchmark.comparison import ModelComparison
from agentest.evaluators.base import EvalResult


class JSONReporter:
    """Generate JSON reports for evaluation results."""

    @staticmethod
    def eval_results_to_dict(results: list[EvalResult]) -> list[dict[str, Any]]:
        """Convert a list of EvalResults to serializable dicts."""
        return [r.model_dump() for r in results]

    @staticmethod
    def benchmark_to_dict(result: BenchmarkResult) -> dict[str, Any]:
        """Convert a BenchmarkResult to a serializable dict with summary and tasks."""
        return {
            "summary": result.summary(),
            "tasks": [
                {
                    "name": t.task_name,
                    "passed": t.all_passed,
                    "score": t.avg_score,
                    "duration_ms": t.duration_ms,
                    "error": t.error,
                    "eval_results": [r.model_dump() for r in t.eval_results],
                }
                for t in result.tasks
            ],
        }

    @staticmethod
    def comparison_to_dict(comparison: ModelComparison) -> dict[str, Any]:
        """Convert a ModelComparison to a serializable dict with per-model details."""
        scores = comparison.model_scores()
        return {
            "models": comparison.comparison_table(),
            "best_score": comparison.best_model("avg_score"),
            "best_cost": comparison.best_model("cost"),
            "model_details": {
                model: {
                    "pass_rate": s.pass_rate,
                    "avg_score": s.avg_score,
                    "total_cost": s.total_cost,
                    "avg_latency_ms": s.avg_latency_ms,
                    "total_tokens": s.total_tokens,
                    "task_scores": s.task_scores,
                }
                for model, s in scores.items()
            },
        }

    def save(self, data: dict[str, Any] | list[Any], path: str | Path) -> Path:
        """Save report data to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))
        return path
