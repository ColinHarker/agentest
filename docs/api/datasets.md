---
sidebar_position: 10
title: Datasets
---

# Datasets

Versioned test datasets with A/B testing support.

## `TestCase`

`agentest.datasets.TestCase`

A single test case in a dataset. Pydantic model with fields: `id` (auto-generated UUID), `name`, `task`, `expected_tools` (list of str), `expected_output` (optional str), `metadata` (dict), `tags` (list of str).

## `Dataset`

`agentest.datasets.Dataset`

A versioned collection of test cases. Pydantic model with fields: `id`, `name`, `version` (default `"1.0.0"`), `description`, `test_cases` (list of TestCase), `metadata` (dict), `created_at`.

**Properties:**

- `size -> int` — Number of test cases.

**Methods:**

- `filter(tags: list[str] | None = None) -> Dataset` — Return a subset matching any of the given tags.
- `split(ratio: float = 0.5, seed: int = 42) -> tuple[Dataset, Dataset]` — Split into two datasets for A/B testing. `ratio` controls the fraction in the first dataset.
- `save(path: str | Path) -> Path` — Save dataset to YAML or JSON based on file extension.
- `load(path: str | Path) -> Dataset` — Static method. Load dataset from YAML or JSON.

**Example:**

```python
from agentest.datasets import Dataset, TestCase

dataset = Dataset(name="core_tasks", version="1.0.0")
dataset.test_cases.append(TestCase(name="summarize", task="Summarize README.md"))
dataset.test_cases.append(TestCase(name="search", task="Find all Python files"))
dataset.save("datasets/core_tasks.yaml")

# Split for A/B testing
group_a, group_b = dataset.split(ratio=0.5)
```

## `ABTestResult`

`agentest.datasets.ABTestResult`

Result of an A/B test comparing two agent configurations. Pydantic model with fields: `variant_a` (str), `variant_b` (str), `results_a` (BenchmarkResult), `results_b` (BenchmarkResult), `winner` (str or None), `metrics_comparison` (dict of metric diffs including `pass_rate`, `avg_score`, `total_cost`).

## `DatasetRunner`

`agentest.datasets.DatasetRunner`

Run a dataset against an agent function with evaluators.

**Constructor:**

- `DatasetRunner(evaluators: list[Evaluator] | None = None)`

**Methods:**

- `run(dataset: Dataset, agent_fn: Callable[[str], AgentTrace]) -> BenchmarkResult` — Run all test cases through `agent_fn` and evaluate.
- `ab_test(dataset: Dataset, variant_a: tuple[str, Callable], variant_b: tuple[str, Callable]) -> ABTestResult` — Run an A/B test comparing two agent configurations. Each variant is a `(name, agent_fn)` tuple. Winner is determined by pass rate, then average score, then cost.

**Example:**

```python
from agentest.datasets import DatasetRunner

runner = DatasetRunner(evaluators=[TaskCompletionEvaluator(), SafetyEvaluator()])
result = runner.run(dataset, agent_fn=my_agent)

# A/B test
ab_result = runner.ab_test(
    dataset,
    variant_a=("gpt-4o", agent_gpt4),
    variant_b=("claude", agent_claude),
)
print(ab_result.winner)
```
