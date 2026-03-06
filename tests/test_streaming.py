"""Tests for streaming trace recording."""

import tempfile
from pathlib import Path

from agentest.recorder.streaming import StreamingRecorder, TraceEvent


class TestTraceEvent:
    def test_creation(self):
        event = TraceEvent(type="message", data={"role": "user", "content": "hi"})
        assert event.type == "message"
        assert event.data["role"] == "user"
        assert event.timestamp > 0


class TestStreamingRecorder:
    def test_inherits_recorder(self):
        """StreamingRecorder is a drop-in replacement for Recorder."""
        rec = StreamingRecorder(task="test")
        rec.record_message("user", "hello")
        rec.record_llm_response(model="test", content="hi", input_tokens=10, output_tokens=5)
        rec.record_tool_call(name="search", arguments={"q": "x"}, result="found")
        trace = rec.finalize(success=True)

        assert trace.task == "test"
        assert len(trace.messages) == 1
        assert len(trace.llm_responses) == 1
        assert len(trace.tool_calls) == 1
        assert trace.success is True

    def test_events_emitted(self):
        events: list[TraceEvent] = []
        rec = StreamingRecorder(task="test", on_event=events.append)

        rec.record_message("user", "hello")
        rec.record_llm_response(model="test", content="hi")
        rec.record_tool_call(name="search", arguments={"q": "x"}, result="found")

        assert len(events) == 3
        assert events[0].type == "message"
        assert events[0].data["role"] == "user"
        assert events[1].type == "llm_response"
        assert events[1].data["model"] == "test"
        assert events[2].type == "tool_call"
        assert events[2].data["name"] == "search"

    def test_events_stored(self):
        rec = StreamingRecorder(task="test")
        rec.record_message("user", "hello")
        rec.record_tool_call(name="a", arguments={}, result="ok")
        assert len(rec.events) == 2

    def test_flush_to_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flush_path = Path(tmpdir) / "live.yaml"
            rec = StreamingRecorder(
                task="test",
                flush_path=flush_path,
                flush_interval=2,
            )

            rec.record_message("user", "hello")
            assert not flush_path.exists()  # only 1 event, interval is 2

            rec.record_tool_call(name="a", arguments={}, result="ok")
            assert flush_path.exists()  # 2 events, flush triggered

            # Verify the flushed file is loadable
            from agentest.recorder.recorder import Recorder

            trace = Recorder.load(flush_path)
            assert trace.task == "test"
            assert len(trace.messages) == 1
            assert len(trace.tool_calls) == 1

    def test_flush_interval_respected(self):
        flush_count = 0
        original_flush = StreamingRecorder._flush

        def counting_flush(self):
            nonlocal flush_count
            flush_count += 1
            # Don't actually write to disk
            pass

        StreamingRecorder._flush = counting_flush
        try:
            rec = StreamingRecorder(task="test", flush_path="/tmp/unused.yaml", flush_interval=3)
            for i in range(9):
                rec.record_message("user", f"msg {i}")
            assert flush_count == 3  # flushed at events 3, 6, 9
        finally:
            StreamingRecorder._flush = original_flush

    def test_no_callback(self):
        """Works fine without a callback."""
        rec = StreamingRecorder(task="test")
        rec.record_message("user", "hello")
        rec.record_tool_call(name="a", arguments={}, result="ok")
        assert len(rec.events) == 2

    def test_context_manager(self):
        events: list[TraceEvent] = []
        with StreamingRecorder(task="test", on_event=events.append) as rec:
            rec.record_message("user", "hello")
        assert len(events) == 1
        assert rec.trace.success is True

    def test_tool_call_error_event(self):
        events: list[TraceEvent] = []
        rec = StreamingRecorder(task="test", on_event=events.append)
        rec.record_tool_call(name="fail", arguments={}, error="boom")
        assert events[0].data["error"] == "boom"
