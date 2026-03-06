"""Example: Benchmark and compare models.

Demonstrates running the same set of tasks across different LLM models
and comparing their performance on pass rate, score, cost, and latency.

This example uses simulated agent runs (no real API calls) to show how
BenchmarkRunner and ModelComparison work. Replace ``simulate_agent()`` with
your real agent to benchmark actual models.

Prerequisites:
    pip install agentest

Usage:
    python examples/benchmark_models.py

No API keys required — uses simulated agent responses.
"""

from agentest import (
    BenchmarkRunner,
    BenchmarkResult,
    ModelComparison,
    CostEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)
from agentest.benchmark.runner import BenchmarkTask
from agentest.core import AgentTrace, LLMResponse, ToolCall
from agentest.reporters.console import ConsoleReporter


def simulate_agent(model: str, task: str) -> AgentTrace:
    """Simulate an agent run (replace with real agent calls)."""
    trace = AgentTrace(task=task)

    # Simulate different model characteristics
    if "opus" in model:
        tokens_in, tokens_out = 500, 200
        content = "Comprehensive and detailed analysis of the topic..."
    elif "sonnet" in model:
        tokens_in, tokens_out = 300, 100
        content = "Clear and concise analysis..."
    elif "gpt-4o" in model:
        tokens_in, tokens_out = 400, 150
        content = "Thorough analysis of the topic..."
    else:
        tokens_in, tokens_out = 200, 80
        content = "Quick analysis..."

    trace.llm_responses.append(
        LLMResponse(
            model=model,
            content=content,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            total_tokens=tokens_in + tokens_out,
        )
    )
    trace.tool_calls.append(ToolCall(name="search", arguments={"query": task}, result=["r1"]))
    trace.finalize(success=True)
    return trace


def main():
    models = ["claude-sonnet-4-6", "claude-opus-4-6", "gpt-4o", "gpt-4o-mini"]
    comparison = ModelComparison()
    reporter = ConsoleReporter()

    for model in models:
        runner = BenchmarkRunner(
            name=f"bench_{model}",
            evaluators=[
                TaskCompletionEvaluator(min_messages=0),
                CostEvaluator(max_cost=1.0),
                ToolUsageEvaluator(required_tools=["search"]),
            ],
        )

        for task_name, task_desc in [
            ("summarize", "Summarize a document"),
            ("analyze", "Analyze code quality"),
            ("search", "Find relevant information"),
        ]:
            runner.add_task(BenchmarkTask(
                name=task_name,
                description=task_desc,
                task_fn=lambda m=model, t=task_desc: simulate_agent(m, t),
            ))

        result = runner.run()
        comparison.add_result(model, result)

        reporter.print_benchmark_result(result)
        print()

    # Compare all models
    print("=" * 60)
    reporter.print_comparison(comparison)

    # Detailed diff between two models
    print("\n" + "=" * 60)
    diff = comparison.diff("claude-sonnet-4-6", "gpt-4o")
    print(f"Sonnet vs GPT-4o:")
    print(f"  Better on score: {diff['better_on_score']}")
    print(f"  Better on cost:  {diff['better_on_cost']}")


if __name__ == "__main__":
    main()
