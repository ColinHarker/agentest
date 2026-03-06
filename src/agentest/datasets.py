"""Dataset management — versioned test datasets with A/B testing support."""

from __future__ import annotations

import json
import random
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agentest.benchmark.runner import BenchmarkResult, BenchmarkRunner, BenchmarkTask
from agentest.core import AgentTrace
from agentest.evaluators.base import Evaluator


class TestCase(BaseModel):
    """A single test case in a dataset."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    task: str
    expected_tools: list[str] = Field(default_factory=list)
    expected_output: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class Dataset(BaseModel):
    """A versioned collection of test cases.

    Usage:
        dataset = Dataset(name="core_tasks", version="1.0.0")
        dataset.test_cases.append(TestCase(name="summarize", task="Summarize README.md"))
        dataset.test_cases.append(TestCase(name="search", task="Find all Python files"))
        dataset.save("datasets/core_tasks.yaml")

        # Split for A/B testing
        group_a, group_b = dataset.split(ratio=0.5)
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    version: str = "1.0.0"
    description: str = ""
    test_cases: list[TestCase] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)

    @property
    def size(self) -> int:
        return len(self.test_cases)

    def filter(self, tags: list[str] | None = None) -> Dataset:
        """Return a subset matching any of the given tags."""
        if not tags:
            return self
        tag_set = set(tags)
        filtered = [tc for tc in self.test_cases if tag_set & set(tc.tags)]
        return Dataset(
            name=f"{self.name}[{','.join(tags)}]",
            version=self.version,
            description=f"Filtered subset of {self.name}",
            test_cases=filtered,
            metadata={**self.metadata, "source": self.name, "filter_tags": tags},
        )

    def split(self, ratio: float = 0.5, seed: int = 42) -> tuple[Dataset, Dataset]:
        """Split into two datasets for A/B testing.

        Args:
            ratio: Fraction of test cases in the first dataset.
            seed: Random seed for reproducibility.
        """
        rng = random.Random(seed)
        cases = list(self.test_cases)
        rng.shuffle(cases)
        split_idx = max(1, int(len(cases) * ratio))
        group_a = cases[:split_idx]
        group_b = cases[split_idx:]

        return (
            Dataset(
                name=f"{self.name}_A",
                version=self.version,
                test_cases=group_a,
                metadata={**self.metadata, "split": "A", "ratio": ratio},
            ),
            Dataset(
                name=f"{self.name}_B",
                version=self.version,
                test_cases=group_b,
                metadata={**self.metadata, "split": "B", "ratio": 1 - ratio},
            ),
        )

    def save(self, path: str | Path) -> Path:
        """Save dataset to YAML or JSON based on file extension."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(mode="json")

        if path.suffix == ".json":
            path.write_text(json.dumps(data, indent=2))
        else:
            path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
        return path

    @staticmethod
    def load(path: str | Path) -> Dataset:
        """Load dataset from YAML or JSON."""
        path = Path(path)
        text = path.read_text()

        if path.suffix == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)

        return Dataset.model_validate(data)


class ABTestResult(BaseModel):
    """Result of an A/B test comparing two agent configurations."""

    variant_a: str
    variant_b: str
    results_a: BenchmarkResult
    results_b: BenchmarkResult
    winner: str | None = None
    metrics_comparison: dict[str, dict[str, float]] = Field(default_factory=dict)


class DatasetRunner:
    """Run a dataset against an agent function with evaluators.

    Usage:
        runner = DatasetRunner(evaluators=[TaskCompletionEvaluator(), SafetyEvaluator()])
        result = runner.run(dataset, agent_fn=my_agent)

        # A/B test
        ab_result = runner.ab_test(
            dataset,
            variant_a=("gpt-4o", agent_gpt4),
            variant_b=("claude", agent_claude),
        )
    """

    def __init__(self, evaluators: list[Evaluator] | None = None) -> None:
        self.evaluators = evaluators or []

    def run(
        self,
        dataset: Dataset,
        agent_fn: Callable[[str], AgentTrace],
    ) -> BenchmarkResult:
        """Run all test cases through agent_fn and evaluate."""
        runner = BenchmarkRunner(name=dataset.name, evaluators=self.evaluators)

        for tc in dataset.test_cases:
            runner.add_task(
                BenchmarkTask(
                    name=tc.name,
                    description=tc.task,
                    task_fn=lambda task=tc.task: agent_fn(task),
                    expected_tools=tc.expected_tools,
                    metadata=tc.metadata,
                )
            )

        return runner.run()

    def ab_test(
        self,
        dataset: Dataset,
        variant_a: tuple[str, Callable[[str], AgentTrace]],
        variant_b: tuple[str, Callable[[str], AgentTrace]],
    ) -> ABTestResult:
        """Run A/B test comparing two agent configurations."""
        name_a, fn_a = variant_a
        name_b, fn_b = variant_b

        results_a = self.run(dataset, fn_a)
        results_b = self.run(dataset, fn_b)

        metrics: dict[str, dict[str, float]] = {
            "pass_rate": {
                "a": results_a.pass_rate,
                "b": results_b.pass_rate,
                "delta": results_b.pass_rate - results_a.pass_rate,
            },
            "avg_score": {
                "a": results_a.avg_score,
                "b": results_b.avg_score,
                "delta": results_b.avg_score - results_a.avg_score,
            },
            "total_cost": {
                "a": results_a.total_cost,
                "b": results_b.total_cost,
                "delta": results_b.total_cost - results_a.total_cost,
            },
        }

        # Determine winner: higher pass_rate wins, tiebreak on avg_score, then cost
        winner = None
        if results_a.pass_rate > results_b.pass_rate:
            winner = name_a
        elif results_b.pass_rate > results_a.pass_rate:
            winner = name_b
        elif results_a.avg_score > results_b.avg_score:
            winner = name_a
        elif results_b.avg_score > results_a.avg_score:
            winner = name_b
        elif results_a.total_cost < results_b.total_cost:
            winner = name_a
        elif results_b.total_cost < results_a.total_cost:
            winner = name_b

        return ABTestResult(
            variant_a=name_a,
            variant_b=name_b,
            results_a=results_a,
            results_b=results_b,
            winner=winner,
            metrics_comparison=metrics,
        )
