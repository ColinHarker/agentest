"""Main CLI group and shared objects."""

from __future__ import annotations

import click
from rich.console import Console

from agentest import __version__
from agentest.reporters.console import ConsoleReporter

console = Console()
err_console = Console(stderr=True)
reporter = ConsoleReporter(console)


@click.group()
@click.version_option(version=__version__, prog_name="agentest")
def main() -> None:
    """Agentest - Universal agent testing and evaluation toolkit."""
    pass


# Import subcommand modules to register them on the main group.
import agentest.cli._dataset  # noqa: E402, F401
import agentest.cli._diff  # noqa: E402, F401
import agentest.cli._doctor  # noqa: E402, F401
import agentest.cli._evaluate  # noqa: E402, F401
import agentest.cli._init  # noqa: E402, F401
import agentest.cli._regression  # noqa: E402, F401
import agentest.cli._replay  # noqa: E402, F401
import agentest.cli._serve  # noqa: E402, F401
import agentest.cli._snapshot  # noqa: E402, F401
import agentest.cli._stats  # noqa: E402, F401
import agentest.cli._summary  # noqa: E402, F401
import agentest.cli._watch  # noqa: E402, F401
