"""Serve and UI commands."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from agentest.cli._main import console, main


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", "-p", default=8000, type=int, help="Port to bind to.")
@click.option("--traces-dir", default="traces", help="Directory containing traces.")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload for development.")
def serve(host: str, port: int, traces_dir: str, reload: bool) -> None:
    """Start the Agentest web UI."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error:[/red] Web UI requires extra dependencies.")
        console.print("Install with: [cyan]pip install agentest[web][/cyan]")
        sys.exit(1)

    from agentest.server.app import create_app

    Path(traces_dir).mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Agentest UI[/bold] starting at [cyan]http://{host}:{port}[/cyan]")
    console.print(f"  Traces directory: [cyan]{traces_dir}[/cyan]")
    console.print()

    # Create app with traces dir
    app = create_app(traces_dir=traces_dir)

    uvicorn.run(app, host=host, port=port, log_level="info")


@main.command()
@click.argument("trace_dir", type=click.Path(exists=True))
@click.option("--port", "-p", default=8000, type=int, help="Port for the UI server.")
def ui(trace_dir: str, port: int) -> None:
    """Open the web UI for a traces directory (alias for serve)."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error:[/red] Web UI requires extra dependencies.")
        console.print("Install with: [cyan]pip install agentest[web][/cyan]")
        sys.exit(1)
    import webbrowser

    from agentest.server.app import create_app

    app = create_app(traces_dir=trace_dir)

    console.print(f"[bold]Opening Agentest UI[/bold] at [cyan]http://127.0.0.1:{port}[/cyan]")
    webbrowser.open(f"http://127.0.0.1:{port}")

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
