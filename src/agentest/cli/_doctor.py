"""Doctor command."""

from __future__ import annotations

import importlib
from pathlib import Path

from agentest.cli._main import console, main


@main.command()
def doctor() -> None:
    """Check Agentest setup and report issues."""
    import agentest

    console.print(f"[bold]agentest {agentest.__version__}[/bold]\n")

    # Check for AI SDKs
    for pkg, desc in [("anthropic", "Anthropic SDK"), ("openai", "OpenAI SDK")]:
        try:
            mod = importlib.import_module(pkg)
            ver = getattr(mod, "__version__", "?")
            msg = f"  [green]\u2713[/green] {desc} {ver}"
            console.print(f"{msg} \u2014 auto-instrumentation available")
        except ImportError:
            console.print(f"  [dim]\u2013[/dim] {desc} not installed")

    # Check for optional extras
    for pkg, extra in [
        ("opentelemetry", "otel"),
        ("flask", "flask"),
        ("fastapi", "web"),
    ]:
        try:
            importlib.import_module(pkg)
            console.print(f"  [green]\u2713[/green] {pkg} available")
        except ImportError:
            console.print(
                f"  [dim]\u2013[/dim] {pkg} not installed"
                f" (pip install agentest[{extra}])"
            )

    # Check traces directory
    traces_dir = Path("traces")
    if traces_dir.is_dir():
        count = len(list(traces_dir.glob("*.yaml")) + list(traces_dir.glob("*.json")))
        console.print(
            f"\n  [green]\u2713[/green] traces/ directory ({count} trace files)"
        )
    else:
        console.print(
            "\n  [yellow]![/yellow] No traces/ directory"
            " \u2014 run [cyan]agentest init[/cyan]"
        )

    # Check pytest plugin
    try:
        import agentest.pytest_plugin  # noqa: F401

        console.print("  [green]\u2713[/green] pytest plugin registered")
    except Exception:
        console.print("  [yellow]![/yellow] pytest plugin not available")

    # Check snapshots
    snap_dir = Path(".agentest/snapshots")
    if snap_dir.is_dir():
        count = len(list(snap_dir.glob("*.yaml")))
        console.print(f"  [green]\u2713[/green] Snapshots ({count} saved)")
    else:
        console.print(
            "  [dim]\u2013[/dim] No snapshots"
            " \u2014 run [cyan]agentest snapshot save[/cyan] after a good run"
        )
