"""Summary command."""

from __future__ import annotations

import json
from pathlib import Path

import click

from agentest.cli._main import console, err_console, main
from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder


@main.command()
@click.argument("trace_dir", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def summary(trace_dir: str, fmt: str) -> None:
    """Summarize all traces in a directory."""
    trace_path = Path(trace_dir)
    traces: list[AgentTrace] = []

    for f in sorted(trace_path.iterdir()):
        if f.suffix in (".yaml", ".yml", ".json"):
            try:
                traces.append(Recorder.load(f))
            except Exception as e:
                err_console.print(f"[yellow]Warning: Could not load {f}: {e}[/yellow]")

    if not traces:
        console.print("[yellow]No traces found.[/yellow]")
        return

    if fmt == "json":
        data = []
        for t in traces:
            data.append(
                {
                    "id": t.id,
                    "task": t.task,
                    "success": t.success,
                    "duration_ms": t.duration_ms,
                    "total_cost": t.total_cost,
                    "total_tokens": t.total_tokens,
                    "tool_calls": t.total_tool_calls,
                }
            )
        console.print(json.dumps(data, indent=2))
    else:
        from rich.table import Table

        table = Table(title=f"Traces in {trace_dir}", show_lines=True)
        table.add_column("Task", style="cyan", max_width=40)
        table.add_column("Status", justify="center")
        table.add_column("Cost", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Tools", justify="right")
        table.add_column("Time (ms)", justify="right")

        for t in traces:
            from rich.text import Text

            status = Text("OK", style="green") if t.success else Text("FAIL", style="red")
            table.add_row(
                t.task[:40],
                status,
                f"${t.total_cost:.4f}",
                str(t.total_tokens),
                str(t.total_tool_calls),
                f"{t.duration_ms:.0f}" if t.duration_ms else "N/A",
            )

        console.print(table)
        console.print(
            f"\nTotal: {len(traces)} traces, "
            f"{sum(1 for t in traces if t.success):d} passed, "
            f"${sum(t.total_cost for t in traces):.4f} total cost"
        )
