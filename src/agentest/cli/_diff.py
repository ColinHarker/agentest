"""Diff command."""

from __future__ import annotations

import json
from pathlib import Path

import click

from agentest.cli._main import console, main
from agentest.recorder.recorder import Recorder


@main.command()
@click.argument("trace_a", type=click.Path(exists=True))
@click.argument("trace_b", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def diff(trace_a: str, trace_b: str, fmt: str) -> None:
    """Compare two traces side by side."""
    from agentest.core import diff_traces

    a = Recorder.load(trace_a)
    b = Recorder.load(trace_b)
    result = diff_traces(a, b)

    if fmt == "json":
        console.print(json.dumps(result, indent=2, default=str))
        return

    from rich.table import Table
    from rich.text import Text

    # Summary table
    title = f"Trace Diff: {Path(trace_a).name} vs {Path(trace_b).name}"
    table = Table(title=title, show_lines=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Trace A", justify="right")
    table.add_column("Trace B", justify="right")
    table.add_column("Delta", justify="right")

    summary = result["summary"]
    for key in ["total_tokens", "total_cost", "tool_call_count", "llm_call_count"]:
        if key in summary:
            val_a = summary[key]["a"]
            val_b = summary[key]["b"]
            delta = summary[key]["delta"]

            if key == "total_cost":
                a_str = f"${val_a:.4f}"
                b_str = f"${val_b:.4f}"
                d_str = f"${delta:+.4f}"
            else:
                a_str = str(val_a)
                b_str = str(val_b)
                d_str = f"{delta:+d}" if isinstance(delta, int) else f"{delta:+.0f}"

            if delta > 0 and key in ("total_cost", "total_tokens"):
                delta_style = "red"
            elif delta < 0:
                delta_style = "green"
            else:
                delta_style = ""
            table.add_row(
                key.replace("_", " ").title(),
                a_str,
                b_str,
                Text(d_str, style=delta_style),
            )

    if "duration_ms" in summary:
        d = summary["duration_ms"]
        table.add_row(
            "Duration (ms)",
            f"{d['a']:.0f}",
            f"{d['b']:.0f}",
            Text(f"{d['delta']:+.0f}", style="red" if d["delta"] > 0 else "green"),
        )

    console.print(table)

    # Success comparison
    s = summary["success"]
    if s["a"] != s["b"]:
        a_txt = "[green]OK[/green]" if s["a"] else "[red]FAIL[/red]"
        b_txt = "[green]OK[/green]" if s["b"] else "[red]FAIL[/red]"
        console.print(f"\n  Status changed: {a_txt} -> {b_txt}")

    # Tool call sequence
    tc = result["tool_calls"]
    if not tc["same_sequence"]:
        console.print("\n  [yellow]Tool call sequence differs[/yellow]")
        if tc["added"]:
            console.print(f"    Added: {', '.join(tc['added'])}")
        if tc["removed"]:
            console.print(f"    Removed: {', '.join(tc['removed'])}")

    # Errors
    errs = result["errors"]
    if errs["new_errors"]:
        console.print(f"\n  [red]New errors:[/red] {errs['new_errors']}")
    if errs["resolved_errors"]:
        console.print(f"\n  [green]Resolved errors:[/green] {errs['resolved_errors']}")
