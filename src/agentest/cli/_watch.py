"""Watch command."""

from __future__ import annotations

from pathlib import Path

import click

from agentest.cli._main import console, main
from agentest.evaluators.base import CompositeEvaluator
from agentest.evaluators.builtin import (
    CostEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)
from agentest.recorder.recorder import Recorder


@main.command()
@click.argument("trace_dir", type=click.Path(exists=True))
@click.option("--interval", "-i", default=2.0, type=float, help="Polling interval in seconds.")
@click.option("--max-cost", type=float, default=None, help="Max cost budget in USD.")
@click.option("--check-safety/--no-check-safety", default=True, help="Run safety checks.")
def watch(trace_dir: str, interval: float, max_cost: float | None, check_safety: bool) -> None:
    """Watch a traces directory and re-evaluate on changes."""
    import time as time_mod

    trace_path = Path(trace_dir)
    last_mtimes: dict[str, float] = {}

    console.print(f"[bold]Watching[/bold] {trace_dir} (every {interval}s, Ctrl+C to stop)")

    evaluators = [TaskCompletionEvaluator(), ToolUsageEvaluator()]
    if check_safety:
        evaluators.append(SafetyEvaluator())
    if max_cost is not None:
        evaluators.append(CostEvaluator(max_cost=max_cost))

    composite = CompositeEvaluator(evaluators)

    try:
        while True:
            changed = False
            for f in sorted(trace_path.iterdir()):
                if f.suffix not in (".yaml", ".yml", ".json"):
                    continue

                mtime = f.stat().st_mtime
                if f.name not in last_mtimes or last_mtimes[f.name] != mtime:
                    last_mtimes[f.name] = mtime
                    changed = True

                    try:
                        trace = Recorder.load(f)
                        results = composite.evaluate_all(trace)
                        all_ok = all(r.passed for r in results)

                        status = "[green]PASS[/green]" if all_ok else "[red]FAIL[/red]"
                        failed = [r for r in results if not r.passed]
                        detail = ""
                        if failed:
                            detail = " - " + "; ".join(r.message for r in failed)

                        console.print(
                            f"  [{time_mod.strftime('%H:%M:%S')}] {f.name}: {status}{detail}"
                        )
                    except Exception as e:
                        console.print(f"  [yellow]{f.name}: error loading - {e}[/yellow]")

            if not changed and not last_mtimes:
                console.print("  [dim]No trace files found yet...[/dim]")

            time_mod.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")
