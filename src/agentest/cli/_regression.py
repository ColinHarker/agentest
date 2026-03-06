"""Regression command."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from agentest.cli._main import console, main
from agentest.recorder.recorder import Recorder


@main.command()
@click.argument("traces_dir", type=click.Path(exists=True))
@click.option("--baseline", type=click.Path(exists=True), required=True, help="Baseline dir.")
@click.option("--update-baseline", is_flag=True, default=False, help="Update baselines.")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option("--cost-threshold", type=float, default=0.1, help="Cost threshold (0.1=10%).")
@click.option("--token-threshold", type=float, default=0.1, help="Token regression threshold.")
@click.option("--latency-threshold", type=float, default=0.2, help="Latency regression threshold.")
def regression(
    traces_dir: str,
    baseline: str,
    update_baseline: bool,
    fmt: str,
    cost_threshold: float,
    token_threshold: float,
    latency_threshold: float,
) -> None:
    """Detect regressions by comparing traces against baselines."""
    from agentest.regression import RegressionDetector, RegressionThresholds

    thresholds = RegressionThresholds(
        cost_increase=cost_threshold,
        token_increase=token_threshold,
        latency_increase=latency_threshold,
    )
    detector = RegressionDetector(baseline_dir=baseline, thresholds=thresholds)
    results = detector.check_all(traces_dir)

    if not results:
        console.print("[yellow]No traces found.[/yellow]")
        return

    if fmt == "json":
        console.print(json.dumps([r.model_dump() for r in results], indent=2, default=str))
    else:
        from rich.table import Table
        from rich.text import Text

        table = Table(title="Regression Report", show_lines=True)
        table.add_column("Task", style="cyan", max_width=40)
        table.add_column("Status", justify="center")
        table.add_column("Regressions", justify="center")
        table.add_column("Improvements", justify="center")
        table.add_column("Details")

        for r in results:
            status = Text("PASS", style="green") if r.passed else Text("FAIL", style="red")
            details = ""
            if r.regressions:
                details = "; ".join(
                    f"{reg.metric}: {reg.change_pct:+.1%}" for reg in r.regressions
                )
            table.add_row(
                r.task[:40],
                status,
                str(len(r.regressions)),
                str(len(r.improvements)),
                details,
            )

        console.print(table)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        console.print(f"\n{passed}/{total} tasks passed regression checks")

    if update_baseline:
        for r in results:
            trace_path = Path(traces_dir)
            for f in sorted(trace_path.iterdir()):
                if f.suffix in (".yaml", ".yml", ".json"):
                    try:
                        trace = Recorder.load(f)
                        if trace.task == r.task:
                            detector.update_baseline(trace)
                            console.print(f"  Updated baseline: {r.task}")
                            break
                    except Exception:
                        continue

    if any(not r.passed for r in results):
        sys.exit(1)
