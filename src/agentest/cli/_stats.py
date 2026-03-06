"""Stats command."""

from __future__ import annotations

import json

import click

from agentest.cli._main import console, err_console, main


@main.command()
@click.argument("history_file", type=click.Path())
@click.option("--task", type=str, default=None, help="Filter to a specific task.")
@click.option("--trend", "show_trend", is_flag=True, help="Show trend analysis.")
@click.option("--ci", "show_ci", is_flag=True, help="Show confidence intervals.")
@click.option(
    "--slo",
    "slo_defs",
    multiple=True,
    help="SLO definition: metric:target:comparison (e.g. cost:0.5:lte).",
)
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def stats(
    history_file: str,
    task: str | None,
    show_trend: bool,
    show_ci: bool,
    slo_defs: tuple[str, ...],
    fmt: str,
) -> None:
    """Analyze performance statistics from run history."""
    from agentest.stats import SLO, StatsAnalyzer

    analyzer = StatsAnalyzer.load(history_file)

    if not analyzer.samples:
        console.print("[yellow]No history data found.[/yellow]")
        return

    tasks = [task] if task else list(analyzer.samples.keys())
    output: dict = {"tasks": {}}

    for t in tasks:
        task_data: dict = {}

        if show_trend:
            for metric in ["score", "cost", "tokens", "latency_ms"]:
                trend_result = analyzer.trend(t, metric=metric)
                task_data.setdefault("trends", {})[metric] = {
                    "direction": trend_result.direction.value,
                    "slope": trend_result.slope,
                    "r_squared": trend_result.r_squared,
                    "samples": trend_result.samples,
                }

        if show_ci:
            for metric in ["score", "cost", "tokens"]:
                ci = analyzer.confidence_interval(t, metric=metric)
                task_data.setdefault("confidence_intervals", {})[metric] = {
                    "mean": ci.mean,
                    "ci_lower": ci.ci_lower,
                    "ci_upper": ci.ci_upper,
                    "std": ci.std,
                    "samples": ci.samples,
                }

        if slo_defs:
            slo_results = []
            for slo_def in slo_defs:
                parts = slo_def.split(":")
                if len(parts) != 3:
                    msg = f"Invalid SLO: {slo_def} (expected metric:target:comparison)"
                    err_console.print(f"[yellow]{msg}[/yellow]")
                    continue
                slo = SLO(metric=parts[0], target=float(parts[1]), comparison=parts[2])
                slo_result = analyzer.check_slo(t, slo)
                slo_results.append(
                    {
                        "metric": slo.metric,
                        "target": slo.target,
                        "comparison": slo.comparison,
                        "compliant": slo_result.compliant,
                        "compliance_rate": slo_result.compliance_rate,
                        "current_value": slo_result.current_value,
                    }
                )
            task_data["slos"] = slo_results

        output["tasks"][t] = task_data

    if fmt == "json":
        console.print(json.dumps(output, indent=2, default=str))
    else:
        for t in tasks:
            console.print(
                f"\n[bold cyan]{t}[/bold cyan] ({len(analyzer.samples.get(t, []))} samples)"
            )

            task_data = output["tasks"].get(t, {})

            if "trends" in task_data:
                console.print("  [bold]Trends:[/bold]")
                for metric, info in task_data["trends"].items():
                    direction = info["direction"]
                    if direction == "improving":
                        style = "green"
                    elif direction == "degrading":
                        style = "red"
                    else:
                        style = ""
                    direction_text = (
                        f"[{style}]{direction}[/{style}]" if style else direction
                    )
                    console.print(
                        f"    {metric}: {direction_text} "
                        f"(slope={info['slope']:.4f}, R\u00b2={info['r_squared']:.2f})"
                    )

            if "confidence_intervals" in task_data:
                console.print("  [bold]95% Confidence Intervals:[/bold]")
                for metric, info in task_data["confidence_intervals"].items():
                    console.print(
                        f"    {metric}: {info['mean']:.4f} "
                        f"[{info['ci_lower']:.4f}, {info['ci_upper']:.4f}]"
                    )

            if "slos" in task_data:
                console.print("  [bold]SLO Compliance:[/bold]")
                for slo_info in task_data["slos"]:
                    status = "[green]OK[/green]" if slo_info["compliant"] else "[red]BREACH[/red]"
                    console.print(
                        f"    {slo_info['metric']} {slo_info['comparison']} {slo_info['target']}: "
                        f"{status} (rate={slo_info['compliance_rate']:.1%})"
                    )
