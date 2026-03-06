"""Init command."""

from __future__ import annotations

from pathlib import Path

from agentest.cli._main import console, main
from agentest.cli._templates import (
    SAMPLE_TEST_ANTHROPIC,
    SAMPLE_TEST_GENERIC,
    SAMPLE_TEST_LANGCHAIN,
)


def _detect_framework() -> str:
    """Detect which AI framework is installed."""
    for pkg, name in [
        ("langchain_core", "langchain"),
        ("crewai", "crewai"),
        ("anthropic", "anthropic"),
        ("openai", "openai"),
    ]:
        try:
            __import__(pkg)
            return name
        except ImportError:
            continue
    return "generic"


@main.command()
def init() -> None:
    """Initialize Agentest in the current project."""
    # Create directories
    dirs = ["traces", "tests/agent_tests"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        console.print(f"  Created {d}/")

    # Detect framework and generate tailored sample test
    framework = _detect_framework()
    if framework in ("anthropic", "openai"):
        sample_content = SAMPLE_TEST_ANTHROPIC
    elif framework == "langchain":
        sample_content = SAMPLE_TEST_LANGCHAIN
    else:
        sample_content = SAMPLE_TEST_GENERIC

    sample_test = Path("tests/agent_tests/test_agent_example.py")
    if not sample_test.exists():
        sample_test.write_text(sample_content)
        console.print(f"  Created {sample_test}")
        if framework != "generic":
            console.print(f"  Detected [cyan]{framework}[/cyan] — generated tailored examples")

    # Create sample conftest
    conftest = Path("tests/agent_tests/conftest.py")
    if not conftest.exists():
        conftest.write_text('''"""Agentest pytest configuration.

The agentest pytest plugin auto-registers fixtures:
  - agent_recorder: Fresh Recorder for each test
  - agent_toolkit: Fresh MockToolkit for each test
  - agent_eval_suite: Standard evaluation suite
"""
''')
        console.print(f"  Created {conftest}")

    console.print("\n[bold green]Agentest initialized![/bold green]")
    console.print("Run tests with: [cyan]pytest tests/agent_tests/[/cyan]")
