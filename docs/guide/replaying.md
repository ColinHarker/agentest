---
sidebar_position: 2
title: Replaying Sessions
---

# Replaying Sessions

The `Replayer` provides deterministic playback of recorded traces — no real LLM or tool calls needed.

## Basic Replay

```python
from agentest import Recorder, Replayer

trace = Recorder.load("traces/my_trace.yaml")
replayer = Replayer(trace, strict=True)

# Get recorded responses in order
response = replayer.next_llm_response()
tool_result = replayer.next_tool_result("read_file")

assert replayer.is_complete
```

## Strict vs Non-Strict Mode

- **Strict** (`strict=True`, default): Raises `ReplayMismatchError` if the requested model or tool name doesn't match the recording.
- **Non-strict** (`strict=False`): Logs mismatches but continues. Access them via `replayer.mismatches`.

## Generating Tool Mocks

Create callable mock functions directly from a recorded trace:

```python
mocks = replayer.create_tool_mock()
result = mocks["read_file"](path="test.txt")  # returns recorded result
```

Each mock is stateful — successive calls return successive recorded results for that tool.
