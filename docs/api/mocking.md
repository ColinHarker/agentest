---
sidebar_position: 4
title: Tool Mocking
---

# Tool Mocking

Fluent API for mocking tool calls in agent tests.

### `ToolCallRecord`

`agentest.mocking.tool_mock.ToolCallRecord`

Record of a mock tool invocation (name, arguments, timestamp).

### `ToolMock`

`agentest.mocking.tool_mock.ToolMock`

Individual tool mock with fluent API:

- `.returns(value)` — Set default return value
- `.when(**kwargs).returns(value)` — Conditional return
- `.otherwise().returns(value)` — Fallback return
- `.returns_sequence([...])` — Sequential returns
- `.responds_with(fn)` — Custom handler function
- `.raises(error)` — Simulate errors
- `.assert_called()` / `.assert_called_times(n)` / `.assert_called_with(**kwargs)` — Assertions

### `MockToolkit`

`agentest.mocking.tool_mock.MockToolkit`

Container for multiple `ToolMock` instances:

- `.mock(name)` — Get or create a mock for a tool
- `.execute(name, **kwargs)` — Execute a mock
- `.assert_all_called()` — Assert all mocks were called
