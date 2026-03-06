"""Streaming trace recording for long-running agents."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentest.core import LLMResponse, Message, Role, ToolCall
from agentest.recorder.recorder import Recorder


class TraceEvent(BaseModel):
    """A single event emitted during streaming recording."""

    type: str
    timestamp: float = Field(default_factory=time.time)
    data: dict[str, Any] = Field(default_factory=dict)


class StreamingRecorder(Recorder):
    """Recorder that emits events and optionally flushes to disk incrementally.

    Usage:
        def on_event(event):
            print(f"[{event.type}] {event.data}")

        recorder = StreamingRecorder(
            task="Long running agent",
            on_event=on_event,
            flush_path="traces/live.yaml",
            flush_interval=3,
        )

        recorder.record_message("user", "Do something complex")
        recorder.record_tool_call(name="search", arguments={"q": "test"}, result="found")
        # After 3 events, trace is auto-flushed to disk
    """

    def __init__(
        self,
        task: str = "",
        metadata: dict[str, Any] | None = None,
        on_event: Callable[[TraceEvent], None] | None = None,
        flush_path: str | Path | None = None,
        flush_interval: int = 5,
    ) -> None:
        """Initialize the streaming recorder.

        Args:
            task: Description of the agent's task.
            metadata: Optional metadata for the trace.
            on_event: Callback invoked for each recorded event.
            flush_path: Path to flush trace state to disk periodically.
            flush_interval: Flush after every N events.
        """
        super().__init__(task=task, metadata=metadata)
        self.on_event = on_event
        self.flush_path = Path(flush_path) if flush_path else None
        self.flush_interval = flush_interval
        self.events: list[TraceEvent] = []

    def record_message(self, role: str | Role, content: str) -> Message:
        """Record a message and emit an event."""
        msg = super().record_message(role, content)
        self._emit(
            TraceEvent(
                type="message",
                data={
                    "role": str(role.value if isinstance(role, Role) else role),
                    "content": content,
                },
            )
        )
        return msg

    def record_llm_response(
        self,
        model: str,
        content: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0,
        raw: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Record an LLM response and emit an event."""
        response = super().record_llm_response(
            model=model,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            raw=raw,
        )
        self._emit(
            TraceEvent(
                type="llm_response",
                data={
                    "model": model,
                    "content": content[:200],
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                },
            )
        )
        return response

    def record_tool_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        result: Any = None,
        error: str | None = None,
        duration_ms: float | None = None,
    ) -> ToolCall:
        """Record a tool call and emit an event."""
        tc = super().record_tool_call(
            name=name,
            arguments=arguments,
            result=result,
            error=error,
            duration_ms=duration_ms,
        )
        self._emit(
            TraceEvent(
                type="tool_call",
                data={
                    "name": name,
                    "arguments": arguments or {},
                    "error": error,
                    "duration_ms": duration_ms,
                },
            )
        )
        return tc

    def _emit(self, event: TraceEvent) -> None:
        """Emit an event to the callback and optionally flush to disk."""
        self.events.append(event)
        if self.on_event:
            self.on_event(event)
        if self.flush_path and len(self.events) % self.flush_interval == 0:
            self._flush()

    def _flush(self) -> None:
        """Write current trace state to flush_path."""
        if self.flush_path:
            self.save(self.flush_path)
