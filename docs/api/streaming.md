---
sidebar_position: 15
title: Streaming
---

# Streaming

Streaming trace recording for long-running agents.

## `TraceEvent`

`agentest.recorder.streaming.TraceEvent`

A single event emitted during streaming recording. Pydantic model with fields: `type` (str, e.g. `"message"`, `"llm_response"`, `"tool_call"`), `timestamp` (float, defaults to current time), `data` (dict).

## `StreamingRecorder`

`agentest.recorder.streaming.StreamingRecorder`

Recorder that emits events and optionally flushes to disk incrementally. Extends `Recorder`.

**Constructor:**

- `StreamingRecorder(task: str = "", metadata: dict | None = None, on_event: Callable[[TraceEvent], None] | None = None, flush_path: str | Path | None = None, flush_interval: int = 5)`

| Parameter | Description |
|---|---|
| `task` | Description of the agent's task. |
| `metadata` | Optional metadata for the trace. |
| `on_event` | Callback invoked for each recorded event. |
| `flush_path` | Path to flush trace state to disk periodically. |
| `flush_interval` | Flush after every N events (default 5). |

**Methods:**

- `record_message(role: str | Role, content: str) -> Message` — Record a message and emit a `"message"` event.
- `record_llm_response(model: str, content: str = "", input_tokens: int = 0, output_tokens: int = 0, latency_ms: float = 0, raw: dict | None = None) -> LLMResponse` — Record an LLM response and emit an `"llm_response"` event.
- `record_tool_call(name: str, arguments: dict | None = None, result: Any = None, error: str | None = None, duration_ms: float | None = None) -> ToolCall` — Record a tool call and emit a `"tool_call"` event.

All methods inherited from `Recorder` (e.g. `finalize`, `save`) are also available.

**Example:**

```python
from agentest.recorder.streaming import StreamingRecorder

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
```
