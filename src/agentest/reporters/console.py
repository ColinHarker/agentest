"""Rich console reporter for agent evaluations."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentest.benchmark.comparison import ModelComparison
from agentest.benchmark.runner import BenchmarkResult
from agentest.evaluators.base import EvalResult


class ConsoleReporter:
    """Pretty-print evaluation results to the console using Rich."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the reporter with an optional Rich Console instance."""
        self.console = console or Console()

    def print_eval_results(
        self, results: list[EvalResult], title: str = "Evaluation Results"
    ) -> None:
        """Print evaluation results as a table."""
        table = Table(title=title, show_lines=True)
        table.add_column("Evaluator", style="cyan")
        table.add_column("Score", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Message")

        for r in results:
            score_text = f"{r.score:.2f}"
            status = (
                Text("PASS", style="bold green") if r.passed else Text("FAIL", style="bold red")
            )
            table.add_row(r.evaluator, score_text, status, r.message)

        self.console.print(table)

    def print_benchmark_result(self, result: BenchmarkResult) -> None:
        """Print a full benchmark result."""
        # Summary panel
        summary = result.summary()
        summary_text = "\n".join(f"  {k}: {v}" for k, v in summary.items())
        self.console.print(
            Panel(summary_text, title=f"Benchmark: {result.name}", border_style="blue")
        )

        # Task details table
        table = Table(title="Task Results", show_lines=True)
        table.add_column("Task", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Score", justify="center")
        table.add_column("Time (ms)", justify="right")
        table.add_column("Details")

        for task in result.tasks:
            status = (
                Text("PASS", style="bold green")
                if task.all_passed
                else Text("FAIL", style="bold red")
            )
            score = f"{task.avg_score:.3f}" if task.avg_score is not None else "N/A"
            time_ms = f"{task.duration_ms:.0f}"

            details = ""
            if task.error:
                details = f"Error: {task.error}"
            elif task.eval_results:
                failed = [r for r in task.eval_results if not r.passed]
                if failed:
                    details = "; ".join(r.message for r in failed)

            table.add_row(task.task_name, status, score, time_ms, details)

        self.console.print(table)

    def print_comparison(self, comparison: ModelComparison) -> None:
        """Print model comparison table."""
        table_data = comparison.comparison_table()
        if not table_data:
            self.console.print("[yellow]No comparison data available.[/yellow]")
            return

        table = Table(title="Model Comparison", show_lines=True)
        table.add_column("Model", style="cyan")
        table.add_column("Pass Rate", justify="center")
        table.add_column("Avg Score", justify="center")
        table.add_column("Cost", justify="right")
        table.add_column("Avg Latency", justify="right")
        table.add_column("Tokens", justify="right")

        best_score = comparison.best_model("avg_score")
        best_cost = comparison.best_model("cost")

        for row in table_data:
            model = row["model"]
            style = ""
            if model == best_score:
                style = "bold green"
            table.add_row(
                Text(model, style=style),
                row["pass_rate"],
                row["avg_score"],
                row["total_cost"],
                row["avg_latency_ms"],
                str(row["total_tokens"]),
            )

        self.console.print(table)

        if best_score:
            self.console.print(f"\n  Best score: [bold green]{best_score}[/bold green]")
        if best_cost:
            self.console.print(f"  Best cost:  [bold blue]{best_cost}[/bold blue]")
