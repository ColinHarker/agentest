---
sidebar_position: 8
title: Integrations
---

# Integrations API Reference

## Auto-Instrumentation

`agentest.integrations.instrument`

- `instrument(anthropic=True, openai=True)` — Patch clients for auto-recording
- `uninstrument()` — Remove patches
- `get_traces()` — Get all recorded traces
- `clear_traces()` — Clear recorded traces
- `flush_trace(task=None)` — Finalize current trace, optionally start new one
- `get_current_recorder()` — Get the active Recorder

## Claude Agent SDK

### `AgentestTracer`

`agentest.integrations.claude_agent_sdk.AgentestTracer`

- `record(fn, *args)` — Record a synchronous function call
- `record_async(fn, *args)` — Record an async function call
- `recording()` — Context manager for manual recording
- `get_trace()` — Get the recorded trace

## OpenAI Agents SDK

### `AgentestTracer`

`agentest.integrations.openai_agents.AgentestTracer`

- `record(fn, *args)` — Record a synchronous function call
- `record_async(fn, *args)` — Record an async function call

## CrewAI

### `record_crew()`

`agentest.integrations.crewai.record_crew`

Record a CrewAI crew execution. Returns `(result, trace)`.

### `CrewAIAdapter`

`agentest.integrations.crewai.CrewAIAdapter`

Persistent adapter for recording multiple crew runs. Property: `traces`.

## AutoGen

### `record_autogen_chat()`

`agentest.integrations.autogen.record_autogen_chat`

Record an AutoGen multi-agent conversation. Returns `(result, trace)`.

### `AutoGenAdapter`

`agentest.integrations.autogen.AutoGenAdapter`

Persistent adapter for recording multiple chats. Property: `traces`.
