"""Tests for the CLI interface."""

import json
from pathlib import Path

from click.testing import CliRunner

from agentest.cli import main
from agentest.recorder.recorder import Recorder

# ---- Helpers ----


def _create_trace_file(directory: Path, name: str = "trace.yaml", success: bool = True) -> Path:
    """Create a minimal trace YAML file and return its path."""
    recorder = Recorder(task="Test task")
    recorder.record_message("user", "Hello")
    recorder.record_llm_response(
        model="claude-sonnet-4-6",
        content="Hi there",
        input_tokens=50,
        output_tokens=10,
    )
    recorder.record_tool_call(
        name="read_file",
        arguments={"path": "test.txt"},
        result="file contents",
    )
    recorder.finalize(success=success)
    path = directory / name
    recorder.save(path)
    return path


# ---- evaluate command ----


def test_evaluate_passing_trace(tmp_path):
    trace_path = _create_trace_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["evaluate", str(trace_path)])
    assert result.exit_code == 0
    assert "task_completion" in result.output or "Evaluation" in result.output


def test_evaluate_with_json_output(tmp_path):
    trace_path = _create_trace_file(tmp_path)
    output_path = tmp_path / "report.json"
    runner = CliRunner()
    result = runner.invoke(main, ["evaluate", str(trace_path), "-o", str(output_path)])
    assert result.exit_code == 0
    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert isinstance(data, list)
    assert len(data) > 0


def test_evaluate_failing_trace(tmp_path):
    """A trace with success=False should cause exit code 1 from safety/task evaluators."""
    trace_path = _create_trace_file(tmp_path, success=False)
    runner = CliRunner()
    result = runner.invoke(main, ["evaluate", str(trace_path)])
    # Task completion evaluator should fail for unsuccessful trace
    assert result.exit_code == 1


def test_evaluate_with_cost_budget(tmp_path):
    trace_path = _create_trace_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["evaluate", str(trace_path), "--max-cost", "10.0"])
    assert result.exit_code == 0


# ---- replay command ----


def test_replay_successful_trace(tmp_path):
    trace_path = _create_trace_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["replay", str(trace_path)])
    assert result.exit_code == 0
    assert "Replaying trace" in result.output
    assert "read_file" in result.output


def test_replay_failed_trace(tmp_path):
    trace_path = _create_trace_file(tmp_path, success=False)
    runner = CliRunner()
    result = runner.invoke(main, ["replay", str(trace_path)])
    assert result.exit_code == 1
    assert "error" in result.output.lower() or "FAIL" in result.output


# ---- summary command ----


def test_summary_table(tmp_path):
    _create_trace_file(tmp_path, name="trace1.yaml")
    _create_trace_file(tmp_path, name="trace2.yaml", success=False)
    runner = CliRunner()
    result = runner.invoke(main, ["summary", str(tmp_path)])
    assert result.exit_code == 0
    assert "Total" in result.output or "Test task" in result.output


def test_summary_json(tmp_path):
    _create_trace_file(tmp_path, name="trace1.yaml")
    runner = CliRunner()
    result = runner.invoke(main, ["summary", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["task"] == "Test task"


def test_summary_empty_dir(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["summary", str(tmp_path)])
    assert result.exit_code == 0
    assert "No traces found" in result.output


# ---- init command ----


def test_init_creates_directories(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert Path("traces").is_dir()
        assert Path("tests/agent_tests").is_dir()
        assert Path("tests/agent_tests/test_agent_example.py").exists()
        assert Path("tests/agent_tests/conftest.py").exists()


def test_init_idempotent(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0


# ---- diff command ----


def test_diff_table(tmp_path):
    path_a = _create_trace_file(tmp_path, name="a.yaml")
    path_b = _create_trace_file(tmp_path, name="b.yaml")
    runner = CliRunner()
    result = runner.invoke(main, ["diff", str(path_a), str(path_b)])
    assert result.exit_code == 0
    assert "Trace Diff" in result.output or "Total Tokens" in result.output


def test_diff_json(tmp_path):
    path_a = _create_trace_file(tmp_path, name="a.yaml")
    path_b = _create_trace_file(tmp_path, name="b.yaml")
    runner = CliRunner()
    result = runner.invoke(main, ["diff", str(path_a), str(path_b), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "summary" in data
    assert "tool_calls" in data


# ---- version ----


def test_version():
    import agentest

    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert agentest.__version__ in result.output


# ---- doctor command ----


def test_doctor():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "agentest" in result.output
    assert "pytest plugin" in result.output


# ---- regression command ----


def test_regression_detects_no_regression(tmp_path):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    current_dir = tmp_path / "current"
    current_dir.mkdir()

    _create_trace_file(baseline_dir, name="trace.yaml")
    _create_trace_file(current_dir, name="trace.yaml")

    runner = CliRunner()
    result = runner.invoke(
        main, ["regression", str(current_dir), "--baseline", str(baseline_dir)]
    )
    assert result.exit_code == 0


def test_regression_json_format(tmp_path):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    current_dir = tmp_path / "current"
    current_dir.mkdir()

    _create_trace_file(baseline_dir, name="trace.yaml")
    _create_trace_file(current_dir, name="trace.yaml")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["regression", str(current_dir), "--baseline", str(baseline_dir), "--format", "json"],
    )
    assert result.exit_code == 0


# ---- stats command ----


def test_stats_empty_history(tmp_path):
    history_file = tmp_path / "history.json"
    history_file.write_text("{}")

    runner = CliRunner()
    result = runner.invoke(main, ["stats", str(history_file)])
    assert result.exit_code == 0
    assert "No history data" in result.output


def test_stats_with_data(tmp_path):
    from agentest.stats import StatsAnalyzer

    trace_path = _create_trace_file(tmp_path, name="trace.yaml")
    trace = Recorder.load(trace_path)

    analyzer = StatsAnalyzer()
    analyzer.add_trace(trace, score=0.95)
    analyzer.add_trace(trace, score=0.90)
    history_file = tmp_path / "history.json"
    analyzer.save(history_file)

    runner = CliRunner()
    result = runner.invoke(main, ["stats", str(history_file), "--trend", "--ci"])
    assert result.exit_code == 0
    assert "Test task" in result.output


# ---- dataset commands ----


def test_dataset_create(tmp_path):
    runner = CliRunner()
    output_path = tmp_path / "test_ds.yaml"
    result = runner.invoke(
        main, ["dataset", "create", "test_ds", "-o", str(output_path), "-d", "A test dataset"]
    )
    assert result.exit_code == 0
    assert output_path.exists()
    assert "Created dataset" in result.output


def test_dataset_list(tmp_path):
    from agentest.datasets import Dataset, TestCase

    ds = Dataset(
        name="my_ds",
        description="Test dataset",
        test_cases=[TestCase(name="tc1", task="Do something")],
    )
    ds_path = tmp_path / "my_ds.yaml"
    ds.save(ds_path)

    runner = CliRunner()
    result = runner.invoke(main, ["dataset", "list", str(ds_path)])
    assert result.exit_code == 0
    assert "my_ds" in result.output
    assert "tc1" in result.output


def test_dataset_split(tmp_path):
    from agentest.datasets import Dataset, TestCase

    ds = Dataset(
        name="split_ds",
        test_cases=[
            TestCase(name=f"tc{i}", task=f"Task {i}") for i in range(6)
        ],
    )
    ds_path = tmp_path / "split_ds.yaml"
    ds.save(ds_path)

    runner = CliRunner()
    result = runner.invoke(main, ["dataset", "split", str(ds_path), "-o", str(tmp_path)])
    assert result.exit_code == 0
    assert "Split" in result.output
    assert (tmp_path / "split_ds_A.yaml").exists()
    assert (tmp_path / "split_ds_B.yaml").exists()


# ---- snapshot commands ----


def test_snapshot_save(tmp_path):
    trace_path = _create_trace_file(tmp_path, name="trace.yaml")
    snap_dir = tmp_path / "snapshots"

    runner = CliRunner()
    result = runner.invoke(
        main, ["snapshot", "save", str(trace_path), "--snapshot-dir", str(snap_dir)]
    )
    assert result.exit_code == 0
    assert "Saved snapshot" in result.output
    assert snap_dir.exists()


def test_snapshot_check(tmp_path):
    trace_path = _create_trace_file(tmp_path, name="trace.yaml")
    snap_dir = tmp_path / "snapshots"

    runner = CliRunner()
    # Save first
    runner.invoke(main, ["snapshot", "save", str(trace_path), "--snapshot-dir", str(snap_dir)])
    # Check against itself
    result = runner.invoke(
        main, ["snapshot", "check", str(trace_path), "--snapshot-dir", str(snap_dir)]
    )
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_snapshot_check_dir(tmp_path):
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    snap_dir = tmp_path / "snapshots"

    trace_path = _create_trace_file(traces_dir, name="trace.yaml")

    runner = CliRunner()
    # Save snapshot first
    runner.invoke(main, ["snapshot", "save", str(trace_path), "--snapshot-dir", str(snap_dir)])
    # Check all traces in dir
    result = runner.invoke(
        main, ["snapshot", "check-dir", str(traces_dir), "--snapshot-dir", str(snap_dir)]
    )
    assert result.exit_code == 0


# ---- watch command ----


def test_watch_help():
    """Watch command should show help without hanging."""
    runner = CliRunner()
    result = runner.invoke(main, ["watch", "--help"])
    assert result.exit_code == 0
    assert "Watch a traces directory" in result.output
