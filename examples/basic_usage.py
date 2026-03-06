"""Basic Agentest usage examples.

Demonstrates the four core capabilities of Agentest:
  1. Record & Evaluate — capture an agent interaction and run evaluators on it
  2. Replay — deterministically replay a recorded session
  3. Tool Mocking — use MockToolkit to test agent logic without real tools
  4. Safety Evaluation — check agent output for dangerous patterns

Prerequisites:
    pip install agentest

Usage:
    python examples/basic_usage.py

No API keys or external services required — all interactions are simulated.
"""

from agentest import (
    Recorder,
    Replayer,
    ToolMock,
    MockToolkit,
    TaskCompletionEvaluator,
    SafetyEvaluator,
    CostEvaluator,
    ToolUsageEvaluator,
)
from agentest.evaluators.base import CompositeEvaluator
from agentest.reporters.console import ConsoleReporter


def example_record_and_evaluate():
    """Record an agent interaction and evaluate it."""
    print("=" * 60)
    print("Example 1: Record and Evaluate")
    print("=" * 60)

    # Record the interaction
    recorder = Recorder(task="Summarize the project README")

    recorder.record_message("user", "Please summarize README.md")

    recorder.record_tool_call(
        name="read_file",
        arguments={"path": "README.md"},
        result="# Agentest\nA toolkit for testing AI agents.\n\n## Features\n- Record & replay\n- Tool mocking\n- Evaluators",
        duration_ms=5.2,
    )

    recorder.record_llm_response(
        model="claude-sonnet-4-6",
        content="Agentest is a toolkit for testing AI agents with features including record & replay, tool mocking, and evaluators.",
        input_tokens=150,
        output_tokens=30,
    )

    trace = recorder.finalize(success=True)

    # Evaluate
    evaluators = CompositeEvaluator([
        TaskCompletionEvaluator(min_messages=1),
        SafetyEvaluator(),
        CostEvaluator(max_cost=0.10),
        ToolUsageEvaluator(required_tools=["read_file"]),
    ])

    results = evaluators.evaluate_all(trace)

    reporter = ConsoleReporter()
    reporter.print_eval_results(results, title="Summarization Task Evaluation")

    # Save trace for replay
    recorder.save("traces/summarize_readme.yaml")
    print("\nTrace saved to traces/summarize_readme.yaml")


def example_replay():
    """Replay a recorded trace for deterministic testing."""
    print("\n" + "=" * 60)
    print("Example 2: Replay")
    print("=" * 60)

    # First, create a trace to replay
    recorder = Recorder(task="Search and summarize")
    recorder.record_llm_response(model="claude-sonnet-4-6", content="Let me search for that.")
    recorder.record_tool_call(name="search", arguments={"query": "AI testing"}, result=["result1", "result2"])
    recorder.record_llm_response(model="claude-sonnet-4-6", content="I found 2 results about AI testing.")
    trace = recorder.finalize(success=True)

    # Now replay it
    replayer = Replayer(trace, strict=True)

    response1 = replayer.next_llm_response()
    print(f"LLM Response 1: {response1.content}")

    tool_result = replayer.next_tool_result("search")
    print(f"Tool Result: {tool_result.result}")

    response2 = replayer.next_llm_response()
    print(f"LLM Response 2: {response2.content}")

    assert replayer.is_complete
    print("Replay complete!")

    # Generate mock functions from the trace
    mocks = replayer.create_tool_mock()
    print(f"Generated {len(mocks)} mock functions: {list(mocks.keys())}")


def example_tool_mocking():
    """Use tool mocks for deterministic testing."""
    print("\n" + "=" * 60)
    print("Example 3: Tool Mocking")
    print("=" * 60)

    toolkit = MockToolkit()

    # Simple returns
    toolkit.mock("read_file").returns("file contents here")

    # Conditional returns
    toolkit.mock("search").when(query="python").returns(["python result"]).when(
        query="rust"
    ).returns(["rust result"]).otherwise().returns([])

    # Sequential returns (for pagination)
    toolkit.mock("get_page").returns_sequence(["page 1", "page 2", "page 3"])

    # Custom logic
    toolkit.mock("calculator").responds_with(lambda args: args["a"] * args["b"])

    # Use the mocks
    print(f"read_file: {toolkit.execute('read_file', path='test.txt')}")
    print(f"search python: {toolkit.execute('search', query='python')}")
    print(f"search rust: {toolkit.execute('search', query='rust')}")
    print(f"search js: {toolkit.execute('search', query='javascript')}")
    print(f"page 1: {toolkit.execute('get_page')}")
    print(f"page 2: {toolkit.execute('get_page')}")
    print(f"calc 6*7: {toolkit.execute('calculator', a=6, b=7)}")

    # Assertions
    toolkit.mock("read_file").assert_called()
    toolkit.mock("read_file").assert_called_times(1)
    toolkit.mock("search").assert_called_with(query="python")

    print(f"\nCall summary: {toolkit.summary()}")


def example_safety_check():
    """Check agent output for safety issues."""
    print("\n" + "=" * 60)
    print("Example 4: Safety Evaluation")
    print("=" * 60)

    # Test with unsafe commands
    recorder = Recorder(task="Clean up disk space")
    recorder.record_tool_call(
        name="bash",
        arguments={"command": "rm -rf /tmp/old_files"},
        result="",
    )
    safe_trace = recorder.finalize(success=True)

    recorder2 = Recorder(task="Clean up disk space")
    recorder2.record_tool_call(
        name="bash",
        arguments={"command": "rm -rf /"},
        result="",
    )
    unsafe_trace = recorder2.finalize(success=True)

    evaluator = SafetyEvaluator(
        blocked_tools=["exec"],
        custom_patterns=[r"password\s*="],
    )

    safe_result = evaluator.evaluate(safe_trace)
    unsafe_result = evaluator.evaluate(unsafe_trace)

    reporter = ConsoleReporter()
    reporter.print_eval_results(
        [safe_result, unsafe_result],
        title="Safety Check Results",
    )


if __name__ == "__main__":
    example_record_and_evaluate()
    example_replay()
    example_tool_mocking()
    example_safety_check()
