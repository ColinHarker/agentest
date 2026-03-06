---
sidebar_position: 3
title: Replayer
---

# Replayer

Deterministic playback of recorded agent sessions.

### `ReplayMismatchError`

`agentest.recorder.replayer.ReplayMismatchError`

Raised in strict mode when the requested model/tool doesn't match the recording.

### `Replayer`

`agentest.recorder.replayer.Replayer`

Plays back recorded traces deterministically. Methods:

- `next_llm_response()` — Get the next recorded LLM response
- `next_tool_result(name)` — Get the next recorded result for a tool
- `create_tool_mock()` — Generate callable mock functions from the trace
- `is_complete` — Whether all recorded events have been replayed
- `mismatches` — List of mismatches (non-strict mode)
