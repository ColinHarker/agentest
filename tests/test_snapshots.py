"""Tests for trace snapshot management."""

from __future__ import annotations

import tempfile
from pathlib import Path

from agentest.core import AgentTrace, LLMResponse, ToolCall
from agentest.snapshots import SnapshotConfig, SnapshotManager


def _make_trace(
    task: str = "test task",
    cost_tokens: tuple[int, int] = (1000, 500),
    tools: list[str] | None = None,
    success: bool = True,
) -> AgentTrace:
    trace = AgentTrace(task=task)
    trace.llm_responses.append(
        LLMResponse(
            model="claude-sonnet-4-6",
            input_tokens=cost_tokens[0],
            output_tokens=cost_tokens[1],
            total_tokens=sum(cost_tokens),
        )
    )
    for tool_name in tools or ["read_file"]:
        trace.tool_calls.append(ToolCall(name=tool_name, result="ok"))
    trace.finalize(success=success)
    return trace


def test_snapshot_save_and_check_pass():
    """Saving and checking the same trace should pass."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SnapshotManager(snapshot_dir=Path(tmpdir))
        trace = _make_trace()

        manager.save_snapshot(trace)
        result = manager.check(trace)

        assert result.passed
        assert result.structural_match
        assert result.message == "OK"


def test_snapshot_check_no_snapshot():
    """Checking a trace with no saved snapshot should fail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SnapshotManager(snapshot_dir=Path(tmpdir))
        trace = _make_trace()

        result = manager.check(trace)
        assert not result.passed
        assert "No snapshot found" in result.message


def test_snapshot_check_structural_diff():
    """Tool sequence changes should be detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SnapshotManager(snapshot_dir=Path(tmpdir))

        baseline = _make_trace(tools=["read_file", "search"])
        manager.save_snapshot(baseline)

        current = _make_trace(tools=["read_file", "write_file"])
        result = manager.check(current)

        assert not result.passed
        assert not result.structural_match
        assert "write_file" in result.added_tools or "search" in result.removed_tools


def test_snapshot_check_metric_threshold():
    """Cost/token changes beyond threshold should fail."""
    config = SnapshotConfig(cost_threshold_pct=5.0, token_threshold_pct=5.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SnapshotManager(snapshot_dir=Path(tmpdir), config=config)

        baseline = _make_trace(cost_tokens=(1000, 500))
        manager.save_snapshot(baseline)

        # Double the tokens — way beyond 5% threshold
        current = _make_trace(cost_tokens=(2000, 1000))
        result = manager.check(current)

        assert not result.passed
        assert "cost" in result.message.lower() or "token" in result.message.lower()


def test_snapshot_update():
    """update() should overwrite the saved snapshot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SnapshotManager(snapshot_dir=Path(tmpdir))

        old = _make_trace(cost_tokens=(1000, 500))
        manager.save_snapshot(old)

        new = _make_trace(cost_tokens=(2000, 1000))
        manager.update(new)

        # Now checking against the updated snapshot should pass
        result = manager.check(new)
        assert result.passed


def test_snapshot_list():
    """list_snapshots should return saved task names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SnapshotManager(snapshot_dir=Path(tmpdir))

        manager.save_snapshot(_make_trace(task="task_one"))
        manager.save_snapshot(_make_trace(task="task_two"))

        snapshots = manager.list_snapshots()
        assert len(snapshots) == 2


def test_snapshot_check_all():
    """check_all should check all traces in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snap_dir = Path(tmpdir) / "snapshots"
        traces_dir = Path(tmpdir) / "traces"
        traces_dir.mkdir()

        manager = SnapshotManager(snapshot_dir=snap_dir)

        trace = _make_trace(task="my_task")
        manager.save_snapshot(trace)

        # Save the trace to traces_dir
        from agentest.recorder.recorder import Recorder

        rec = Recorder(task="my_task")
        rec.trace = trace
        rec.save(traces_dir / "trace.yaml")

        results = manager.check_all(traces_dir)
        assert len(results) == 1
        assert results[0].passed
