---
sidebar_position: 2
title: Recorder
---

# Recorder

Capture agent interactions into reproducible traces.

### `Recorder`

`agentest.recorder.recorder.Recorder`

Main class for recording agent interactions. Provides methods:

- `record_message(role, content)` — Record a conversation message
- `record_tool_call(name, arguments, result, ...)` — Record a tool invocation
- `record_llm_response(model, content, input_tokens, output_tokens, ...)` — Record an LLM API call
- `wrap_tool(name, fn)` — Wrap a function to auto-record its calls
- `finalize(success)` — Finalize the trace
- `save(path, format)` — Save trace to YAML or JSON
- `load(path)` — Load a trace from file (class method)

Supports context manager usage (`with Recorder(...) as rec:`).

### `Recorder.from_messages()`

`classmethod`

Create a finalized `AgentTrace` from a list of message dicts in OpenAI format. Each dict should have `role` and `content` keys. If `model` is provided, assistant messages also generate `LLMResponse` entries.

```python
Recorder.from_messages(
    messages: list[dict[str, Any]],
    task: str = "",
    model: str = "",
    success: bool = True,
    metadata: dict[str, Any] | None = None,
) -> AgentTrace
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `messages` | `list[dict[str, Any]]` | List of message dicts with `role` and `content` keys. |
| `task` | `str` | Task description for the trace. |
| `model` | `str` | Model name to record for assistant messages. If empty, no `LLMResponse` entries are created. |
| `success` | `bool` | Whether the trace succeeded (default `True`). |
| `metadata` | `dict[str, Any] \| None` | Optional metadata dict. |

**Example:**

```python
from agentest import Recorder

trace = Recorder.from_messages(
    messages=[
        {"role": "user", "content": "Summarize this document"},
        {"role": "assistant", "content": "Here is the summary..."},
    ],
    task="Summarize",
    model="claude-sonnet-4-6",
    success=True,
)
```

### `Recorder.record_tool_result()`

Backfills the result for a previously recorded tool call by its `tool_use_id`. This is primarily used by the auto-instrumentation layer, where the tool call and its result arrive at different times.

```python
Recorder.record_tool_result(tool_use_id: str, result: Any) -> None
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_use_id` | `str` | The ID of the pending tool call to update. |
| `result` | `Any` | The result value to attach to the tool call. |

If `tool_use_id` does not match any pending tool call, the method is a no-op.

### `Recorder.wrap_tool()`

Wraps a tool function to automatically record its calls. The wrapper measures execution time, captures arguments and results (or errors), and records them as `ToolCall` entries.

```python
Recorder.wrap_tool(name: str, func: Any) -> Any
```

Positional arguments passed to the wrapped function are normalized to keyword arguments via `inspect.signature`. This means the recorded `arguments` dict uses the actual parameter names from the function signature. If signature inspection fails (e.g., for built-in functions or C extensions), positional args are stored as `arg0`, `arg1`, etc.

**Example:**

```python
def read_file(path: str) -> str:
    return open(path).read()

read_file = recorder.wrap_tool("read_file", read_file)
result = read_file("doc.txt")
# Recorded as: ToolCall(name="read_file", arguments={"path": "doc.txt"}, ...)
```
