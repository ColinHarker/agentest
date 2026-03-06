---
sidebar_position: 1
title: Recording Traces
---

# Recording Traces

The `Recorder` captures agent interactions into reproducible `AgentTrace` objects.

## Basic Recording

```python
from agentest import Recorder

recorder = Recorder(task="My agent task", metadata={"version": "1.0"})

# Record messages
recorder.record_message("user", "Do something")

# Record LLM responses
recorder.record_llm_response(
    model="claude-sonnet-4-6",
    content="Here's what I'll do...",
    input_tokens=100,
    output_tokens=50,
    latency_ms=350,
)

# Record tool calls
recorder.record_tool_call(
    name="read_file",
    arguments={"path": "test.txt"},
    result="file contents",
    duration_ms=5.2,
)

# Finalize
trace = recorder.finalize(success=True)
```

## Context Manager

```python
with Recorder(task="My task") as rec:
    rec.record_llm_response("claude-sonnet-4-6", "Done.", 50, 10)
# Automatically finalized on exit
```

If an exception occurs inside the `with` block, the trace is finalized with `success=False`.

## Wrapping Tools

Automatically record tool calls by wrapping existing functions:

```python
def read_file(path: str) -> str:
    return open(path).read()

# Wrap the tool — calls are automatically recorded
read_file = recorder.wrap_tool("read_file", read_file)
result = read_file(path="doc.txt")  # recorded automatically
```

## Saving and Loading

```python
# Save as YAML (default)
recorder.save("traces/my_trace.yaml")

# Save as JSON
recorder.save("traces/my_trace.json", format="json")

# Load
trace = Recorder.load("traces/my_trace.yaml")
```
