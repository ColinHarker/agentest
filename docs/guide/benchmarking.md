---
sidebar_position: 5
title: Benchmarking
---

# Benchmarking

`BenchmarkRunner` executes tasks and evaluates results. `ModelComparison` compares across models.

## Running Benchmarks

```python
from agentest import BenchmarkRunner, TaskCompletionEvaluator, CostEvaluator
from agentest.benchmark.runner import BenchmarkTask

runner = BenchmarkRunner(
    name="my_benchmark",
    evaluators=[TaskCompletionEvaluator(), CostEvaluator(max_cost=0.50)],
)

runner.add_task(BenchmarkTask(
    name="summarize",
    description="Summarize a document",
    task_fn=lambda: run_your_agent("Summarize README.md"),
    timeout_seconds=300,
))

result = runner.run()
print(result.summary())
```

## Async Execution

```python
result = await runner.run_async(max_concurrency=5)
```

## Multiple Runs

For statistical significance:

```python
results = runner.run_n_times(n=3)
```

## Model Comparison

```python
from agentest import ModelComparison

comparison = ModelComparison()
for model in ["claude-sonnet-4-6", "gpt-4o"]:
    runner = BenchmarkRunner(name=f"bench_{model}", evaluators=[...])
    # ... add tasks ...
    comparison.add_result(model, runner.run())

# Best model
best = comparison.best_model("avg_score")  # or "pass_rate", "cost", "latency"

# Side-by-side diff
diff = comparison.diff("claude-sonnet-4-6", "gpt-4o")

# Export
comparison.to_csv("results.csv")
comparison.to_markdown("results.md")
```
