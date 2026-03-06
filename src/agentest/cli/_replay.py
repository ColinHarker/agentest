"""Replay command."""

from __future__ import annotations

import sys

import click

from agentest.cli._main import console, main
from agentest.recorder.recorder import Recorder
from agentest.recorder.replayer import Replayer


@main.command()
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--strict/--no-strict", default=True, help="Fail on mismatches.")
def replay(trace_path: str, strict: bool) -> None:
    """Replay a recorded agent trace and verify consistency."""
    trace = Recorder.load(trace_path)
    replayer = Replayer(trace, strict=strict)

    console.print(f"[bold]Replaying trace:[/bold] {trace_path}")
    console.print(f"  Task: {trace.task}")
    console.print(f"  LLM responses: {len(trace.llm_responses)}")
    console.print(f"  Tool calls: {len(trace.tool_calls)}")
    console.print()

    # Replay all interactions
    for i, response in enumerate(trace.llm_responses):
        console.print(f"  [{i + 1}] LLM: {response.model} - {response.content[:80]}...")

    for i, tc in enumerate(trace.tool_calls):
        status = "[green]OK[/green]" if tc.succeeded else f"[red]ERR: {tc.error}[/red]"
        console.print(f"  [{i + 1}] Tool: {tc.name}({tc.arguments}) -> {status}")

    # Generate mock functions
    mocks = replayer.create_tool_mock()
    console.print(f"\n  Generated {len(mocks)} tool mocks for replay testing")

    if trace.success:
        console.print("\n[bold green]Trace replayed successfully.[/bold green]")
    else:
        console.print(f"\n[bold red]Trace ended with error: {trace.error}[/bold red]")
        sys.exit(1)
