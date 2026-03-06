"""Tests for the pytest plugin fixtures and configuration."""

from agentest.evaluators.base import CompositeEvaluator
from agentest.mocking.tool_mock import MockToolkit
from agentest.pytest_plugin import (
    AgentTraceTestError,
    pytest_addoption,
    pytest_configure,
)
from agentest.recorder.recorder import Recorder

# ---- Fixtures used as test parameters (the correct way) ----


def test_agent_recorder_fixture(agent_recorder):
    """The agent_recorder fixture should provide a Recorder."""
    assert isinstance(agent_recorder, Recorder)
    assert agent_recorder.trace.task == "test"


def test_agent_recorder_records(agent_recorder):
    """The Recorder from the fixture should be fully functional."""
    agent_recorder.record_message("user", "Hello")
    agent_recorder.record_llm_response(
        model="test-model",
        content="Hi",
        input_tokens=10,
        output_tokens=5,
    )
    agent_recorder.record_tool_call(name="read_file", arguments={"path": "a.txt"}, result="data")
    trace = agent_recorder.finalize(success=True)
    assert len(trace.messages) == 1
    assert len(trace.llm_responses) == 1
    assert len(trace.tool_calls) == 1


def test_agent_toolkit_fixture(agent_toolkit):
    """The agent_toolkit fixture should provide a MockToolkit."""
    assert isinstance(agent_toolkit, MockToolkit)
    agent_toolkit.mock("my_tool").returns("result")
    assert agent_toolkit.execute("my_tool") == "result"


def test_agent_eval_suite_fixture(agent_eval_suite):
    """The agent_eval_suite fixture should provide a CompositeEvaluator."""
    assert isinstance(agent_eval_suite, CompositeEvaluator)
    assert len(agent_eval_suite.evaluators) >= 2


def test_eval_suite_evaluates_trace(agent_eval_suite):
    """The eval suite should be able to evaluate a trace."""
    from agentest.core import AgentTrace

    trace = AgentTrace(task="test task")
    trace.finalize(success=True)
    results = agent_eval_suite.evaluate_all(trace)
    assert len(results) >= 2
    assert all(hasattr(r, "passed") for r in results)


# ---- pytest_configure ----


def test_pytest_configure_registers_markers():
    """pytest_configure should register custom markers."""

    class FakeConfig:
        def __init__(self):
            self._ini_values = []

        def addinivalue_line(self, name, value):
            self._ini_values.append((name, value))

    config = FakeConfig()
    pytest_configure(config)
    marker_lines = [v for k, v in config._ini_values if k == "markers"]
    assert len(marker_lines) == 3
    assert any("agent_eval" in m for m in marker_lines)
    assert any("agent_safety" in m for m in marker_lines)
    assert any("agent_benchmark" in m for m in marker_lines)


# ---- pytest_addoption ----


def test_pytest_addoption_registers_options():
    """pytest_addoption should add CLI options."""

    class FakeGroup:
        def __init__(self):
            self.options = []

        def addoption(self, *args, **kwargs):
            self.options.append(args[0])

    class FakeParser:
        def __init__(self):
            self._groups = {}

        def getgroup(self, name, desc=""):
            if name not in self._groups:
                self._groups[name] = FakeGroup()
            return self._groups[name]

    parser = FakeParser()
    pytest_addoption(parser)
    group = parser._groups["agentest"]
    assert "--agentest-traces" in group.options
    assert "--agentest-max-cost" in group.options
    assert "--agentest-max-tokens" in group.options


# ---- AgentTraceTestError ----


def test_agent_trace_test_failure():
    """AgentTraceTestError should be a proper exception."""
    err = AgentTraceTestError("something failed")
    assert "something failed" in str(err)
