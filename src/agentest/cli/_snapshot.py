"""Snapshot commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from agentest.cli._main import console, main
from agentest.recorder.recorder import Recorder


@main.group()
def snapshot() -> None:
    """Manage trace snapshots for CI regression testing."""
    pass


main.add_command(snapshot)


@snapshot.command("save")
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--snapshot-dir", type=click.Path(), default="snapshots", help="Snapshot directory.")
def snapshot_save(trace_path: str, snapshot_dir: str) -> None:
    """Save a trace as a golden snapshot."""
    from agentest.snapshots import SnapshotManager

    trace = Recorder.load(trace_path)
    manager = SnapshotManager(snapshot_dir=Path(snapshot_dir))
    path = manager.save_snapshot(trace)
    console.print(f"Saved snapshot: [cyan]{path}[/cyan] (task: {trace.task})")


@snapshot.command("check")
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--snapshot-dir", type=click.Path(), default="snapshots", help="Snapshot directory.")
@click.option("--update", is_flag=True, default=False, help="Update snapshot if check fails.")
@click.option("--cost-threshold", type=float, default=10.0, help="Cost threshold (%%).")
@click.option("--latency-threshold", type=float, default=20.0, help="Latency threshold (%%).")
@click.option("--token-threshold", type=float, default=15.0, help="Token threshold (%%).")
def snapshot_check(
    trace_path: str,
    snapshot_dir: str,
    update: bool,
    cost_threshold: float,
    latency_threshold: float,
    token_threshold: float,
) -> None:
    """Check a trace against its saved snapshot."""
    from agentest.snapshots import SnapshotConfig, SnapshotManager

    config = SnapshotConfig(
        cost_threshold_pct=cost_threshold,
        latency_threshold_pct=latency_threshold,
        token_threshold_pct=token_threshold,
    )
    trace = Recorder.load(trace_path)
    manager = SnapshotManager(snapshot_dir=Path(snapshot_dir), config=config)
    result = manager.check(trace)

    if result.passed:
        console.print(f"[green]PASS[/green] {result.task}: {result.message}")
    else:
        console.print(f"[red]FAIL[/red] {result.task}: {result.message}")

        if result.metric_diffs:
            for metric, diff_info in result.metric_diffs.items():
                console.print(
                    f"  {metric}: {diff_info.get('baseline', 0):.4f} -> "
                    f"{diff_info.get('current', 0):.4f} ({diff_info.get('change_pct', 0):+.1f}%)"
                )
        if result.added_tools:
            console.print(f"  Added tools: {', '.join(result.added_tools)}")
        if result.removed_tools:
            console.print(f"  Removed tools: {', '.join(result.removed_tools)}")

        if update:
            manager.update(trace)
            console.print(f"  [yellow]Updated snapshot for: {result.task}[/yellow]")

        sys.exit(1)


@snapshot.command("check-dir")
@click.argument("traces_dir", type=click.Path(exists=True))
@click.option("--snapshot-dir", type=click.Path(), default="snapshots", help="Snapshot directory.")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def snapshot_check_dir(traces_dir: str, snapshot_dir: str, fmt: str) -> None:
    """Check all traces in a directory against saved snapshots."""
    from agentest.snapshots import SnapshotManager

    manager = SnapshotManager(snapshot_dir=Path(snapshot_dir))
    results = manager.check_all(Path(traces_dir))

    if not results:
        console.print("[yellow]No traces found.[/yellow]")
        return

    if fmt == "json":
        console.print(json.dumps([r.model_dump() for r in results], indent=2, default=str))
    else:
        from rich.table import Table
        from rich.text import Text

        table = Table(title="Snapshot Check Results", show_lines=True)
        table.add_column("Task", style="cyan", max_width=40)
        table.add_column("Status", justify="center")
        table.add_column("Structure", justify="center")
        table.add_column("Message")

        for r in results:
            status = Text("PASS", style="green") if r.passed else Text("FAIL", style="red")
            struct = (
                Text("OK", style="green") if r.structural_match else Text("DIFF", style="yellow")
            )
            table.add_row(r.task[:40], status, struct, r.message[:60])

        console.print(table)

        passed = sum(1 for r in results if r.passed)
        console.print(f"\n{passed}/{len(results)} snapshots matched")

    if any(not r.passed for r in results):
        sys.exit(1)
