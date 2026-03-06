"""Tests for recorder and replayer."""

import tempfile
from pathlib import Path

import pytest

from agentest.recorder.recorder import Recorder
from agentest.recorder.replayer import Replayer, ReplayMismatchError


def test_recorder_basic():
    rec = Recorder(task="Test task")
    rec.record_message("user", "Hello")
    rec.record_llm_response(
        model="test-model",
        content="Hi there",
        input_tokens=10,
        output_tokens=5,
    )
    rec.record_tool_call(name="search", arguments={"q": "test"}, result=["result1"])
    trace = rec.finalize(success=True)

    assert trace.task == "Test task"
    assert len(trace.messages) == 1
    assert len(trace.llm_responses) == 1
    assert len(trace.tool_calls) == 1
    assert trace.success is True


def test_recorder_wrap_tool():
    rec = Recorder(task="Wrap test")

    def my_tool(x: int, y: int) -> int:
        return x + y

    wrapped = rec.wrap_tool("add", my_tool)
    result = wrapped(x=3, y=4)

    assert result == 7
    assert len(rec.trace.tool_calls) == 1
    assert rec.trace.tool_calls[0].name == "add"
    assert rec.trace.tool_calls[0].result == 7


def test_recorder_wrap_tool_error():
    rec = Recorder(task="Error test")

    def failing_tool() -> None:
        raise ValueError("boom")

    wrapped = rec.wrap_tool("fail", failing_tool)
    with pytest.raises(ValueError, match="boom"):
        wrapped()

    assert len(rec.trace.tool_calls) == 1
    assert rec.trace.tool_calls[0].error == "boom"


def test_recorder_save_load_yaml():
    rec = Recorder(task="Save test")
    rec.record_llm_response(model="test", content="response")
    rec.record_tool_call(name="tool1", arguments={"a": 1}, result="ok")
    rec.finalize(success=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = rec.save(Path(tmpdir) / "trace.yaml")
        loaded = Recorder.load(path)

    assert loaded.task == "Save test"
    assert len(loaded.llm_responses) == 1
    assert len(loaded.tool_calls) == 1


def test_recorder_save_load_json():
    rec = Recorder(task="JSON test")
    rec.record_tool_call(name="tool1", result="ok")
    rec.finalize(success=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = rec.save(Path(tmpdir) / "trace.json", format="json")
        loaded = Recorder.load(path)

    assert loaded.task == "JSON test"


def test_replayer_basic():
    rec = Recorder(task="Replay test")
    rec.record_llm_response(model="claude-sonnet-4-6", content="Hello")
    rec.record_tool_call(name="search", arguments={"q": "test"}, result=["r1"])
    trace = rec.finalize(success=True)

    replayer = Replayer(trace)
    response = replayer.next_llm_response()
    assert response.content == "Hello"

    tool = replayer.next_tool_result("search")
    assert tool.result == ["r1"]

    assert replayer.is_complete


def test_replayer_strict_mismatch():
    rec = Recorder(task="Mismatch test")
    rec.record_llm_response(model="claude-sonnet-4-6", content="Hello")
    trace = rec.finalize()

    replayer = Replayer(trace, strict=True)
    with pytest.raises(ReplayMismatchError):
        replayer.next_llm_response(model="gpt-4o")


def test_replayer_non_strict():
    rec = Recorder(task="Non-strict test")
    rec.record_llm_response(model="claude-sonnet-4-6", content="Hello")
    trace = rec.finalize()

    replayer = Replayer(trace, strict=False)
    response = replayer.next_llm_response(model="gpt-4o")
    assert response.content == "Hello"
    assert len(replayer.mismatches) == 1


def test_replayer_create_tool_mock():
    rec = Recorder(task="Mock test")
    rec.record_tool_call(name="read", arguments={"path": "a.txt"}, result="content A")
    rec.record_tool_call(name="read", arguments={"path": "b.txt"}, result="content B")
    rec.record_tool_call(name="write", arguments={"path": "c.txt"}, result=True)
    trace = rec.finalize()

    replayer = Replayer(trace)
    mocks = replayer.create_tool_mock()

    assert "read" in mocks
    assert "write" in mocks
    assert mocks["read"]() == "content A"
    assert mocks["read"]() == "content B"
    assert mocks["write"]() is True


def test_recorder_context_manager_success():
    with Recorder(task="Context test") as rec:
        rec.record_message("user", "Hello")
        rec.record_llm_response(model="test", content="Hi")

    assert rec.trace.success is True
    assert rec.trace.end_time is not None


def test_recorder_context_manager_error():
    try:
        with Recorder(task="Error context") as rec:
            rec.record_message("user", "Hello")
            raise ValueError("something broke")
    except ValueError:
        pass

    assert rec.trace.success is False
    assert rec.trace.error == "something broke"


def test_replayer_reset():
    rec = Recorder(task="Reset test")
    rec.record_llm_response(model="test", content="Hello")
    trace = rec.finalize()

    replayer = Replayer(trace)
    replayer.next_llm_response()
    assert replayer.is_complete

    replayer.reset()
    assert not replayer.is_complete
    response = replayer.next_llm_response()
    assert response.content == "Hello"
