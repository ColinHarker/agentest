"""Tests for dataset management."""

import tempfile
from pathlib import Path

from agentest.core import AgentTrace, LLMResponse, ToolCall
from agentest.datasets import Dataset, DatasetRunner, TestCase


def _make_test_dataset():
    return Dataset(
        name="test_dataset",
        version="1.0.0",
        test_cases=[
            TestCase(name="task1", task="Do task 1", tags=["core", "fast"]),
            TestCase(name="task2", task="Do task 2", tags=["core"]),
            TestCase(name="task3", task="Do task 3", tags=["slow"]),
            TestCase(name="task4", task="Do task 4", tags=["fast"]),
        ],
    )


def _dummy_agent(task: str) -> AgentTrace:
    trace = AgentTrace(
        task=task,
        success=True,
        llm_responses=[
            LLMResponse(model="test", input_tokens=10, output_tokens=5, total_tokens=15),
        ],
        tool_calls=[ToolCall(name="test_tool", arguments={}, result="ok")],
    )
    trace.finalize(success=True)
    return trace


class TestTestCase:
    def test_creation(self):
        tc = TestCase(name="test", task="Do something")
        assert tc.name == "test"
        assert tc.task == "Do something"
        assert tc.id  # auto-generated

    def test_with_metadata(self):
        tc = TestCase(
            name="test",
            task="Do something",
            expected_tools=["read_file"],
            tags=["core"],
            metadata={"priority": "high"},
        )
        assert tc.expected_tools == ["read_file"]
        assert "core" in tc.tags


class TestDataset:
    def test_creation(self):
        ds = _make_test_dataset()
        assert ds.name == "test_dataset"
        assert ds.size == 4

    def test_filter_by_tags(self):
        ds = _make_test_dataset()
        filtered = ds.filter(tags=["fast"])
        assert filtered.size == 2
        assert all(any(t == "fast" for t in tc.tags) for tc in filtered.test_cases)

    def test_filter_no_tags(self):
        ds = _make_test_dataset()
        filtered = ds.filter(tags=None)
        assert filtered.size == 4  # returns self

    def test_filter_empty_result(self):
        ds = _make_test_dataset()
        filtered = ds.filter(tags=["nonexistent"])
        assert filtered.size == 0

    def test_split(self):
        ds = _make_test_dataset()
        a, b = ds.split(ratio=0.5, seed=42)
        assert a.size + b.size == ds.size
        assert a.size >= 1
        assert b.size >= 1
        assert "A" in a.metadata.get("split", "")
        assert "B" in b.metadata.get("split", "")

    def test_split_deterministic(self):
        ds = _make_test_dataset()
        a1, b1 = ds.split(ratio=0.5, seed=42)
        a2, b2 = ds.split(ratio=0.5, seed=42)
        assert [tc.name for tc in a1.test_cases] == [tc.name for tc in a2.test_cases]

    def test_save_load_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ds = _make_test_dataset()
            path = ds.save(Path(tmpdir) / "dataset.yaml")
            loaded = Dataset.load(path)
            assert loaded.name == ds.name
            assert loaded.size == ds.size
            assert loaded.test_cases[0].name == ds.test_cases[0].name

    def test_save_load_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ds = _make_test_dataset()
            path = ds.save(Path(tmpdir) / "dataset.json")
            loaded = Dataset.load(path)
            assert loaded.name == ds.name
            assert loaded.size == ds.size


class TestDatasetRunner:
    def test_run(self):
        ds = _make_test_dataset()
        runner = DatasetRunner()
        result = runner.run(ds, _dummy_agent)
        assert result.total_tasks == 4
        assert result.pass_rate == 1.0

    def test_run_with_evaluators(self):
        from agentest.evaluators.builtin import TaskCompletionEvaluator

        ds = Dataset(
            name="test",
            test_cases=[TestCase(name="t1", task="task 1")],
        )
        runner = DatasetRunner(evaluators=[TaskCompletionEvaluator()])
        result = runner.run(ds, _dummy_agent)
        assert result.total_tasks == 1
        assert len(result.tasks[0].eval_results) > 0

    def test_ab_test(self):
        ds = Dataset(
            name="test",
            test_cases=[
                TestCase(name="t1", task="task 1"),
                TestCase(name="t2", task="task 2"),
            ],
        )
        runner = DatasetRunner()
        result = runner.ab_test(
            ds,
            variant_a=("model_a", _dummy_agent),
            variant_b=("model_b", _dummy_agent),
        )
        assert result.variant_a == "model_a"
        assert result.variant_b == "model_b"
        assert result.results_a.total_tasks == 2
        assert result.results_b.total_tasks == 2
        assert "pass_rate" in result.metrics_comparison
