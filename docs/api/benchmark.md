---
sidebar_position: 6
title: Benchmark
---

# Benchmark

Benchmark runner and model comparison utilities.

### `BenchmarkTask`

`agentest.benchmark.runner.BenchmarkTask`

Definition of a benchmark task: `name`, `description`, `task_fn`, `timeout_seconds`.

### `TaskResult`

`agentest.benchmark.runner.TaskResult`

Result of running a single benchmark task.

### `BenchmarkResult`

`agentest.benchmark.runner.BenchmarkResult`

Aggregated results from a benchmark run. Methods: `summary()`.

### `BenchmarkRunner`

`agentest.benchmark.runner.BenchmarkRunner`

Executes benchmark tasks and evaluates results. Methods:

- `add_task(task)` — Add a task
- `run()` — Run all tasks synchronously
- `run_async(max_concurrency)` — Run tasks with async concurrency
- `run_n_times(n)` — Run multiple times for statistical significance

### `ModelScore`

`agentest.benchmark.comparison.ModelScore`

Score data for a single model in a comparison.

### `ModelComparison`

`agentest.benchmark.comparison.ModelComparison`

Compare benchmark results across models. Methods:

- `add_result(model, result)` — Add a model's results
- `best_model(metric)` — Find the best model by metric
- `diff(model_a, model_b)` — Side-by-side comparison
- `to_csv(path)` / `to_markdown(path)` — Export results
