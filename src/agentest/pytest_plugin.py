"""Pytest plugin for Agentest - test AI agents in CI/CD pipelines.

Usage in conftest.py:
    # No configuration needed - the plugin auto-registers via entry points.

Usage in tests:
    def test_agent_completes_task(agent_recorder, agent_toolkit):
        # Record an agent interaction
        agent_recorder.record_message("user", "Summarize this document")
        agent_recorder.record_llm_response(
            model="claude-sonnet-4-6",
            content="Here is the summary...",
            input_tokens=100,
            output_tokens=50,
        )
        agent_recorder.record_tool_call(
            name="read_file",
            arguments={"path": "doc.txt"},
            result="Document contents...",
        )
        trace = agent_recorder.finalize(success=True)

        # Evaluate
        results = agent_eval_suite.evaluate(trace)
        assert all(r.passed for r in results)

    def test_with_mocked_tools(agent_toolkit):
        agent_toolkit.mock("read_file").returns("file contents")
        agent_toolkit.mock("search").when(query="python").returns(["result"])

        result = agent_toolkit.execute("read_file", path="test.txt")
        assert result == "file contents"

    def test_replay(agent_trace_file):
        # Use a recorded trace as test fixture
        replayer = Replayer(agent_trace_file)
        response = replayer.next_llm_response()
        assert "summary" in response.content.lower()
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from agentest.core import AgentTrace
from agentest.evaluators.base import CompositeEvaluator
from agentest.evaluators.builtin import (
    CostEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)
from agentest.mocking.tool_mock import MockToolkit
from agentest.recorder.recorder import Recorder


def pytest_addoption(parser: Any) -> None:
    """Add Agentest CLI options to pytest."""
    group = parser.getgroup("agentest", "Agentest agent testing")
    group.addoption(
        "--agentest-traces",
        action="store",
        default=None,
        help="Directory containing recorded agent traces for replay tests.",
    )
    group.addoption(
        "--agentest-max-cost",
        action="store",
        type=float,
        default=None,
        help="Maximum cost budget for agent tests (in USD).",
    )
    group.addoption(
        "--agentest-max-tokens",
        action="store",
        type=int,
        default=None,
        help="Maximum token budget for agent tests.",
    )


def pytest_configure(config: Any) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "agent_eval: mark test as an agent evaluation test")
    config.addinivalue_line("markers", "agent_safety: mark test as an agent safety test")
    config.addinivalue_line("markers", "agent_benchmark: mark test as an agent benchmark test")


@pytest.fixture
def agent_recorder() -> Generator[Recorder, None, None]:
    """Fixture that provides a fresh Recorder for each test."""
    recorder = Recorder(task="test")
    yield recorder


@pytest.fixture
def agent_toolkit() -> Generator[MockToolkit, None, None]:
    """Fixture that provides a fresh MockToolkit for each test."""
    toolkit = MockToolkit()
    yield toolkit


@pytest.fixture
def agent_eval_suite(request: Any) -> CompositeEvaluator:
    """Fixture that provides a standard evaluation suite.

    Respects --agentest-max-cost and --agentest-max-tokens options.
    """
    max_cost = request.config.getoption("--agentest-max-cost", default=None)
    max_tokens = request.config.getoption("--agentest-max-tokens", default=None)

    evaluators = [
        TaskCompletionEvaluator(),
        SafetyEvaluator(),
        ToolUsageEvaluator(),
    ]

    if max_cost is not None or max_tokens is not None:
        evaluators.append(CostEvaluator(max_cost=max_cost, max_tokens=max_tokens))

    return CompositeEvaluator(evaluators)


@pytest.fixture
def agent_trace_dir(request: Any) -> Path | None:
    """Fixture that returns the trace directory path."""
    traces_dir = request.config.getoption("--agentest-traces", default=None)
    if traces_dir:
        return Path(traces_dir)
    return None


def pytest_collect_file(parent: Any, file_path: Path) -> Any:
    """Collect .agent.yaml and .agent.json files as test items."""
    if file_path.suffix in (".yaml", ".yml") and ".agent" in file_path.stem:
        return AgentTraceFile.from_parent(parent, path=file_path)
    if file_path.suffix == ".json" and ".agent" in file_path.stem:
        return AgentTraceFile.from_parent(parent, path=file_path)
    return None


class AgentTraceFile(pytest.File):
    """Collector for agent trace files."""

    def collect(self) -> Generator[AgentTraceItem, None, None]:
        trace = Recorder.load(self.path)
        yield AgentTraceItem.from_parent(self, name=f"replay:{self.path.stem}", trace=trace)


class AgentTraceItem(pytest.Item):
    """Test item that replays and evaluates an agent trace."""

    def __init__(self, name: str, parent: Any, trace: AgentTrace) -> None:
        super().__init__(name, parent)
        self.trace = trace

    def runtest(self) -> None:
        # Run standard evaluations
        evaluators = [
            TaskCompletionEvaluator(),
            SafetyEvaluator(),
            ToolUsageEvaluator(),
        ]

        results = [e.evaluate(self.trace) for e in evaluators]
        failed = [r for r in results if not r.passed]

        if failed:
            failures = "\n".join(f"  {r.evaluator}: {r.message}" for r in failed)
            raise AgentTraceTestError(f"Agent trace evaluation failed:\n{failures}")

    def repr_failure(self, excinfo: Any, **kwargs: Any) -> str:
        return str(excinfo.value)

    def reportinfo(self) -> tuple[Path, None, str]:
        return self.path, None, f"agent trace: {self.name}"


class AgentTraceTestError(Exception):
    """Raised when an agent trace fails evaluation."""
