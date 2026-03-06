"""Model comparison utilities for benchmarking agents across different LLMs."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentest.benchmark.runner import BenchmarkResult


@dataclass
class ModelScore:
    """Aggregated scores for a single model."""

    model: str
    pass_rate: float
    avg_score: float
    total_cost: float
    avg_latency_ms: float
    total_tokens: int
    task_scores: dict[str, float] = field(default_factory=dict)


class ModelComparison:
    """Compare benchmark results across different models.

    Usage:
        comparison = ModelComparison()
        comparison.add_result("claude-sonnet-4-6", sonnet_result)
        comparison.add_result("gpt-4o", gpt4o_result)

        table = comparison.comparison_table()
        winner = comparison.best_model(metric="pass_rate")
    """

    def __init__(self) -> None:
        self.results: dict[str, BenchmarkResult] = {}

    def add_result(self, model: str, result: BenchmarkResult) -> None:
        """Add a benchmark result for a model."""
        self.results[model] = result

    def model_scores(self) -> dict[str, ModelScore]:
        """Calculate aggregate scores for each model."""
        scores: dict[str, ModelScore] = {}

        for model, result in self.results.items():
            task_scores = {}
            total_latency = 0.0
            total_tokens = 0

            for task_result in result.tasks:
                if task_result.avg_score is not None:
                    task_scores[task_result.task_name] = task_result.avg_score
                total_latency += task_result.duration_ms
                if task_result.trace:
                    total_tokens += task_result.trace.total_tokens

            avg_latency = total_latency / len(result.tasks) if result.tasks else 0

            scores[model] = ModelScore(
                model=model,
                pass_rate=result.pass_rate,
                avg_score=result.avg_score,
                total_cost=result.total_cost,
                avg_latency_ms=avg_latency,
                total_tokens=total_tokens,
                task_scores=task_scores,
            )

        return scores

    def best_model(self, metric: str = "pass_rate") -> str | None:
        """Find the best model by a given metric.

        Args:
            metric: One of 'pass_rate', 'avg_score', 'cost' (lowest), 'latency' (lowest).
        """
        scores = self.model_scores()
        if not scores:
            return None

        if metric in ("cost", "latency", "avg_latency_ms", "total_cost"):
            attr = "total_cost" if metric == "cost" else "avg_latency_ms"
            return min(scores, key=lambda m: getattr(scores[m], attr))
        else:
            return max(scores, key=lambda m: getattr(scores[m], metric, 0))

    def comparison_table(self) -> list[dict[str, Any]]:
        """Generate a comparison table as a list of dicts."""
        scores = self.model_scores()
        table = []

        for model, score in sorted(scores.items()):
            table.append(
                {
                    "model": model,
                    "pass_rate": f"{score.pass_rate:.1%}",
                    "avg_score": f"{score.avg_score:.3f}",
                    "total_cost": f"${score.total_cost:.4f}",
                    "avg_latency_ms": f"{score.avg_latency_ms:.0f}",
                    "total_tokens": score.total_tokens,
                }
            )

        return table

    def diff(self, model_a: str, model_b: str) -> dict[str, Any]:
        """Compare two models side by side."""
        scores = self.model_scores()

        if model_a not in scores or model_b not in scores:
            raise KeyError(f"Both models must have results. Have: {list(scores.keys())}")

        a, b = scores[model_a], scores[model_b]

        # Find tasks where models differ
        task_diffs = {}
        all_tasks = set(a.task_scores.keys()) | set(b.task_scores.keys())
        for task in all_tasks:
            sa = a.task_scores.get(task, 0)
            sb = b.task_scores.get(task, 0)
            if sa != sb:
                task_diffs[task] = {
                    model_a: f"{sa:.3f}",
                    model_b: f"{sb:.3f}",
                    "delta": f"{sa - sb:+.3f}",
                }

        return {
            "models": [model_a, model_b],
            "pass_rate": {
                model_a: f"{a.pass_rate:.1%}",
                model_b: f"{b.pass_rate:.1%}",
            },
            "avg_score": {
                model_a: f"{a.avg_score:.3f}",
                model_b: f"{b.avg_score:.3f}",
            },
            "cost": {
                model_a: f"${a.total_cost:.4f}",
                model_b: f"${b.total_cost:.4f}",
            },
            "task_diffs": task_diffs,
            "better_on_score": model_a if a.avg_score >= b.avg_score else model_b,
            "better_on_cost": model_a if a.total_cost <= b.total_cost else model_b,
        }

    def to_csv(self, path: str | Path | None = None) -> str:
        """Export comparison table as CSV. Returns CSV string, optionally saves to file."""
        table = self.comparison_table()
        if not table:
            return ""

        output = io.StringIO()
        columns = [
            "model",
            "pass_rate",
            "avg_score",
            "total_cost",
            "avg_latency_ms",
            "total_tokens",
        ]
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for row in table:
            writer.writerow(row)

        csv_str = output.getvalue()

        if path:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(csv_str)

        return csv_str

    def to_markdown(self, path: str | Path | None = None) -> str:
        """Export comparison table as Markdown. Returns string, optionally saves to file."""
        table = self.comparison_table()
        if not table:
            return ""

        columns = ["Model", "Pass Rate", "Avg Score", "Total Cost", "Avg Latency (ms)", "Tokens"]
        keys = ["model", "pass_rate", "avg_score", "total_cost", "avg_latency_ms", "total_tokens"]

        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join("---" for _ in columns) + " |"

        rows = []
        best_score = self.best_model("avg_score")
        for row in table:
            values = [str(row[k]) for k in keys]
            if row["model"] == best_score:
                values[0] = f"**{values[0]}**"
            rows.append("| " + " | ".join(values) + " |")

        md = "\n".join([header, separator] + rows)

        if path:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(md + "\n")

        return md
