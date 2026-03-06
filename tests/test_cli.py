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
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "1.0.2" in result.output
