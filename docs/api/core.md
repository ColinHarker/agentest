---
sidebar_position: 1
title: Core Models
---

# Core Models

Core data models for representing agent traces, tool calls, and LLM responses.

### `Role`

`agentest.core.Role`

Enum for message roles: `"user"`, `"assistant"`, `"system"`, `"tool"`.

### `ToolCall`

`agentest.core.ToolCall`

Represents a single tool invocation with name, arguments, result, duration, and error status.

### `LLMResponse`

`agentest.core.LLMResponse`

Represents an LLM API call with model, content, token counts, latency, and cost.

### `Message`

`agentest.core.Message`

A message in the agent conversation with role, content, and timestamp.

### `AgentTrace`

`agentest.core.AgentTrace`

The core trace object containing messages, tool calls, LLM responses, metadata, timing, and success status. Provides computed properties for total tokens, cost, and duration.

### `TraceSession`

`agentest.core.TraceSession`

A collection of related traces for multi-session workflows.

### `diff_traces()`

`agentest.core.diff_traces`

Compare two `AgentTrace` objects and return structured deltas for tokens, cost, duration, tool calls, and errors.
