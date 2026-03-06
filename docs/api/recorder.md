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
