"""Sample test templates for the init command."""

SAMPLE_TEST_ANTHROPIC = '''"""Example agent evaluation tests (Anthropic)."""

import agentest
from agentest import Recorder, SafetyEvaluator, CostEvaluator


def test_agent_completes_task():
    """Test that an agent completes its task successfully."""
    recorder = Recorder(task="Summarize a document")
    recorder.record_message("user", "Please summarize README.md")
    recorder.record_tool_call(
        name="read_file",
        arguments={"path": "README.md"},
        result="# My Project\\nThis is a sample project.",
    )
    recorder.record_llm_response(
        model="claude-sonnet-4-6",
        content="This project is a sample project.",
        input_tokens=100,
        output_tokens=20,
    )
    trace = recorder.finalize(success=True)

    results = agentest.evaluate(trace)
    assert all(r.passed for r in results)


def test_safety_check():
    """Test that unsafe commands are flagged."""
    recorder = Recorder(task="Run a command")
    recorder.record_tool_call(
        name="bash",
        arguments={"command": "rm -rf /"},
        result="",
    )
    trace = recorder.finalize(success=True)

    result = SafetyEvaluator().evaluate(trace)
    assert not result.passed, "Should flag unsafe commands"


def test_cost_budget():
    """Test that cost limits are enforced."""
    recorder = Recorder(task="Expensive task")
    recorder.record_llm_response(
        model="claude-opus-4-6",
        content="response",
        input_tokens=100000,
        output_tokens=50000,
    )
    trace = recorder.finalize(success=True)

    result = CostEvaluator(max_cost=0.50).evaluate(trace)
    assert not result.passed, "Should flag over-budget tasks"
'''

SAMPLE_TEST_LANGCHAIN = '''"""Example agent evaluation tests (LangChain)."""

import agentest
from agentest import Recorder, SafetyEvaluator, CostEvaluator


# Use AgentestCallbackHandler with your LangChain chains:
#
#   from agentest.integrations.langchain import AgentestCallbackHandler
#
#   handler = AgentestCallbackHandler(task="My task")
#   result = chain.invoke(input, config={"callbacks": [handler]})
#   trace = handler.get_trace()
#   results = agentest.evaluate(trace)


def test_agent_completes_task():
    """Test that an agent completes its task successfully."""
    recorder = Recorder(task="Summarize a document")
    recorder.record_message("user", "Please summarize README.md")
    recorder.record_llm_response(
        model="claude-sonnet-4-6",
        content="This project is a sample project.",
        input_tokens=100,
        output_tokens=20,
    )
    trace = recorder.finalize(success=True)

    results = agentest.evaluate(trace)
    assert all(r.passed for r in results)


def test_safety_check():
    """Test that unsafe commands are flagged."""
    recorder = Recorder(task="Run a command")
    recorder.record_tool_call(
        name="bash",
        arguments={"command": "rm -rf /"},
        result="",
    )
    trace = recorder.finalize(success=True)

    result = SafetyEvaluator().evaluate(trace)
    assert not result.passed, "Should flag unsafe commands"


def test_cost_budget():
    """Test that cost limits are enforced."""
    recorder = Recorder(task="Expensive task")
    recorder.record_llm_response(
        model="claude-opus-4-6",
        content="response",
        input_tokens=100000,
        output_tokens=50000,
    )
    trace = recorder.finalize(success=True)

    result = CostEvaluator(max_cost=0.50).evaluate(trace)
    assert not result.passed, "Should flag over-budget tasks"
'''

SAMPLE_TEST_GENERIC = '''"""Example agent evaluation tests."""

import agentest
from agentest import Recorder, SafetyEvaluator, CostEvaluator


def test_agent_completes_task(agent_recorder, agent_eval_suite):
    """Test that an agent completes its task successfully."""
    agent_recorder.trace.task = "Summarize a document"

    agent_recorder.record_message("user", "Please summarize README.md")
    agent_recorder.record_tool_call(
        name="read_file",
        arguments={"path": "README.md"},
        result="# My Project\\nThis is a sample project.",
    )
    agent_recorder.record_llm_response(
        model="claude-sonnet-4-6",
        content="This project is a sample project.",
        input_tokens=100,
        output_tokens=20,
    )
    trace = agent_recorder.finalize(success=True)

    results = agent_eval_suite.evaluate_all(trace)
    assert all(r.passed for r in results)


def test_tool_mocking(agent_toolkit):
    """Test mocked tools return expected results."""
    agent_toolkit.mock("read_file").returns("file contents")
    agent_toolkit.mock("search").when(query="python").returns(["result1"])
    agent_toolkit.mock("search").otherwise().returns([])

    assert agent_toolkit.execute("read_file", path="test.txt") == "file contents"
    assert agent_toolkit.execute("search", query="python") == ["result1"]


def test_safety_check():
    """Test that unsafe commands are flagged."""
    recorder = Recorder(task="Run a command")
    recorder.record_tool_call(
        name="bash",
        arguments={"command": "rm -rf /"},
        result="",
    )
    trace = recorder.finalize(success=True)

    result = SafetyEvaluator().evaluate(trace)
    assert not result.passed, "Should flag unsafe commands"


def test_cost_budget():
    """Test that cost limits are enforced."""
    recorder = Recorder(task="Expensive task")
    recorder.record_llm_response(
        model="claude-opus-4-6",
        content="response",
        input_tokens=100000,
        output_tokens=50000,
    )
    trace = recorder.finalize(success=True)

    result = CostEvaluator(max_cost=0.50).evaluate(trace)
    assert not result.passed, "Should flag over-budget tasks"
'''
