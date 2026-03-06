"""Example: Testing a realistic coding assistant agent with Agentest.

A coding agent that reads files, searches code, runs tests, and writes
fixes — with real file I/O and real Anthropic API calls. Shows how to
integrate Agentest into an actual agent application.

Usage:
    # Set your API key first
    export ANTHROPIC_API_KEY=sk-ant-...

    # Run the example
    python examples/coding_agent.py

    # Or run with a custom model
    python examples/coding_agent.py --model claude-haiku-4-5
"""

import os
import sys
import tempfile
import time
from pathlib import Path

import anthropic

from agentest import (
    BenchmarkRunner,
    CostEvaluator,
    MockToolkit,
    Recorder,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
    diff_traces,
)
from agentest.benchmark.runner import BenchmarkTask
from agentest.evaluators.base import CompositeEvaluator
from agentest.reporters.console import ConsoleReporter


# ---------------------------------------------------------------------------
# 1. Real tools that the agent can call
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    """Read a file from disk."""
    return Path(path).read_text()


def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    Path(path).write_text(content)
    return f"Wrote {len(content)} bytes to {path}"


def search_code(directory: str, pattern: str) -> list[dict]:
    """Search for a pattern in Python files under a directory."""
    results = []
    base = Path(directory)
    for py_file in base.rglob("*.py"):
        try:
            lines = py_file.read_text().splitlines()
            for i, line in enumerate(lines, 1):
                if pattern in line:
                    results.append({
                        "file": str(py_file.relative_to(base)),
                        "line": i,
                        "content": line.strip(),
                    })
        except (OSError, UnicodeDecodeError):
            continue
    return results


def run_tests(directory: str) -> dict:
    """Run tests in a directory (simplified — checks for test functions)."""
    base = Path(directory)
    test_files = list(base.rglob("test_*.py"))
    passed, failed = 0, 0
    failures = []
    for tf in test_files:
        content = tf.read_text()
        tests = [line for line in content.splitlines() if line.strip().startswith("def test_")]
        for test in tests:
            test_name = test.strip().split("(")[0].replace("def ", "")
            if "fail" in test_name.lower() or "broken" in test_name.lower():
                failed += 1
                failures.append(f"{tf.name}::{test_name}")
            else:
                passed += 1
    return {"passed": passed, "failed": failed, "failures": failures}


# ---------------------------------------------------------------------------
# 2. The agent loop — real LLM calls + real tool execution
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read a file from disk.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute file path"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "content": {"type": "string", "description": "File content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "search_code",
        "description": "Search for a text pattern in Python files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory to search in"},
                "pattern": {"type": "string", "description": "Text pattern to search for"},
            },
            "required": ["directory", "pattern"],
        },
    },
    {
        "name": "run_tests",
        "description": "Run the test suite in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"directory": {"type": "string", "description": "Project directory"}},
            "required": ["directory"],
        },
    },
]

TOOL_DISPATCH = {
    "read_file": read_file,
    "write_file": write_file,
    "search_code": search_code,
    "run_tests": run_tests,
}


def run_coding_agent(
    client: anthropic.Anthropic,
    project_dir: str,
    task: str,
    model: str = "claude-sonnet-4-6",
    max_turns: int = 10,
) -> Recorder:
    """Run a coding agent that uses real LLM calls and real tool execution.

    The agent is given tools and a task, and autonomously decides which tools
    to call. Every interaction is recorded by Agentest for later evaluation.
    """
    with Recorder(task=task, metadata={"project": project_dir, "model": model}) as recorder:
        recorder.record_message("user", task)

        system_prompt = (
            f"You are a coding assistant. Fix bugs in the project at {project_dir}. "
            "Use the provided tools to read files, search code, run tests, and write fixes. "
            "When you're done, summarize what you changed."
        )

        messages = [{"role": "user", "content": task}]

        for turn in range(max_turns):
            start_ms = time.time()
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
            latency_ms = (time.time() - start_ms) * 1000

            # Record the LLM response
            text_parts = [b.text for b in response.content if b.type == "text"]
            recorder.record_llm_response(
                model=model,
                content="\n".join(text_parts),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=latency_ms,
            )

            # Process tool use blocks
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # Model is done — record final assistant message
                if text_parts:
                    recorder.record_message("assistant", "\n".join(text_parts))
                break

            # Build the assistant message and tool results for the next turn
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_block in tool_use_blocks:
                tool_fn = TOOL_DISPATCH.get(tool_block.name)
                tool_start = time.time()
                try:
                    result = tool_fn(**tool_block.input) if tool_fn else f"Unknown tool: {tool_block.name}"
                    result_str = str(result) if not isinstance(result, str) else result
                    duration_ms = (time.time() - tool_start) * 1000

                    recorder.record_tool_call(
                        name=tool_block.name,
                        arguments=tool_block.input,
                        result=result_str,
                        duration_ms=duration_ms,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": result_str,
                    })
                except Exception as e:
                    duration_ms = (time.time() - tool_start) * 1000
                    recorder.record_tool_call(
                        name=tool_block.name,
                        arguments=tool_block.input,
                        error=str(e),
                        duration_ms=duration_ms,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": f"Error: {e}",
                        "is_error": True,
                    })

            messages.append({"role": "user", "content": tool_results})

    return recorder


# ---------------------------------------------------------------------------
# 3. Sample project with a known bug
# ---------------------------------------------------------------------------

def create_sample_project(base_dir: str) -> str:
    """Create a small Python project with a zero-division bug."""
    project = Path(base_dir) / "myproject"
    project.mkdir(parents=True, exist_ok=True)

    (project / "calculator.py").write_text(
        '"""A simple calculator module."""\n\n\n'
        "def add(a, b):\n    return a + b\n\n\n"
        "def subtract(a, b):\n    return a - b\n\n\n"
        "def multiply(a, b):\n    return a * b\n\n\n"
        "def divide(a, b):\n    return a / b\n"
    )

    (project / "test_calculator.py").write_text(
        "from calculator import add, subtract, multiply, divide\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
        "def test_subtract():\n    assert subtract(5, 3) == 2\n\n\n"
        "def test_multiply():\n    assert multiply(4, 5) == 20\n\n\n"
        "def test_divide():\n    assert divide(10, 2) == 5\n\n\n"
        "def test_divide_broken_by_zero():\n"
        "    # This test will fail with ZeroDivisionError\n"
        "    divide(1, 0)\n"
    )

    return str(project)


# ---------------------------------------------------------------------------
# 4. Main — run the agent, evaluate, compare
# ---------------------------------------------------------------------------

def main():
    # Parse args
    model = "claude-sonnet-4-6"
    for i, arg in enumerate(sys.argv):
        if arg == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: Set ANTHROPIC_API_KEY environment variable first.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    reporter = ConsoleReporter()

    with tempfile.TemporaryDirectory() as tmpdir:
        # ---- Run 1: Fix the bug ----
        print("=" * 60)
        print(f"Running coding agent (model: {model})")
        print("=" * 60)

        project_dir = create_sample_project(tmpdir)
        recorder = run_coding_agent(
            client=client,
            project_dir=project_dir,
            task=f"Fix the ZeroDivisionError bug in {project_dir}/calculator.py. "
                 "Read the code, run the tests, apply a fix, then verify the tests pass.",
            model=model,
        )
        trace = recorder.trace

        print(f"\nTrace: {trace.id[:12]}...")
        print(f"  Tool calls: {trace.total_tool_calls}")
        print(f"  Tokens:     {trace.total_tokens:,}")
        print(f"  Cost:       ${trace.total_cost:.4f}")
        print(f"  Duration:   {trace.duration_ms:.0f}ms")
        print(f"  Success:    {trace.success}")

        # Save trace
        trace_path = Path(tmpdir) / "traces" / "run1.yaml"
        recorder.save(trace_path)
        print(f"  Saved to:   {trace_path}")

        # ---- Evaluate ----
        print("\n" + "=" * 60)
        print("Evaluating agent trace")
        print("=" * 60)

        evaluators = CompositeEvaluator([
            TaskCompletionEvaluator(min_messages=2),
            SafetyEvaluator(blocked_tools=["exec", "eval"]),
            CostEvaluator(max_cost=0.50, max_tokens=50000),
            ToolUsageEvaluator(
                required_tools=["read_file"],
                forbidden_tools=["exec"],
                max_retries_per_tool=3,
            ),
        ])

        results = evaluators.evaluate_all(trace)
        reporter.print_eval_results(results, title="Bug-Fix Agent Evaluation")

        # ---- Run 2: Same task again to compare consistency ----
        print("\n" + "=" * 60)
        print(f"Running agent again for comparison")
        print("=" * 60)

        project_dir2 = create_sample_project(tmpdir + "/run2")
        recorder2 = run_coding_agent(
            client=client,
            project_dir=project_dir2,
            task=f"Fix the ZeroDivisionError bug in {project_dir2}/calculator.py. "
                 "Read the code, run the tests, apply a fix, then verify the tests pass.",
            model=model,
        )
        trace2 = recorder2.trace

        print(f"\nTrace: {trace2.id[:12]}...")
        print(f"  Tokens: {trace2.total_tokens:,}  Cost: ${trace2.total_cost:.4f}")

        # ---- Diff the two runs ----
        print("\n" + "=" * 60)
        print("Comparing Run 1 vs Run 2")
        print("=" * 60)

        diff = diff_traces(trace, trace2)
        s = diff["summary"]

        print(f"\n  Cost:    ${s['total_cost']['a']:.4f} -> ${s['total_cost']['b']:.4f}"
              f"  (delta: ${s['total_cost']['delta']:+.4f})")
        print(f"  Tokens:  {s['total_tokens']['a']:,} -> {s['total_tokens']['b']:,}"
              f"  (delta: {s['total_tokens']['delta']:+,})")
        print(f"  Tools:   same sequence = {diff['tool_calls']['same_sequence']}")
        if diff["tool_calls"]["added"]:
            print(f"           added: {diff['tool_calls']['added']}")
        if diff["tool_calls"]["removed"]:
            print(f"           removed: {diff['tool_calls']['removed']}")

        # ---- Mock-based testing (no API calls) ----
        print("\n" + "=" * 60)
        print("Testing agent tool patterns with mocks (no API calls)")
        print("=" * 60)

        toolkit = MockToolkit()
        toolkit.mock("read_file").when(path="/project/calculator.py").returns(
            "def divide(a, b):\n    return a / b\n"
        )
        toolkit.mock("search_code").returns([
            {"file": "calculator.py", "line": 1, "content": "def divide(a, b):"},
        ])
        toolkit.mock("run_tests").returns_sequence([
            {"passed": 4, "failed": 1, "failures": ["test_divide_by_zero"]},
            {"passed": 5, "failed": 0, "failures": []},
        ])
        toolkit.mock("write_file").returns("Wrote 80 bytes")

        # Simulate expected tool-call pattern
        src = toolkit.execute("read_file", path="/project/calculator.py")
        toolkit.execute("run_tests", directory="/project")
        toolkit.execute("write_file", path="/project/calculator.py", content="fixed")
        r2 = toolkit.execute("run_tests", directory="/project")

        toolkit.mock("read_file").assert_called_times(1)
        toolkit.mock("write_file").assert_called_with(path="/project/calculator.py")
        toolkit.mock("run_tests").assert_called_times(2)
        toolkit.assert_all_called()

        print(f"  All mock assertions passed ({len(toolkit.all_calls)} calls)")
        print(f"  Tests after fix: {r2}")


if __name__ == "__main__":
    main()
