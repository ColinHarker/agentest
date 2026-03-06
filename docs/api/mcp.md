---
sidebar_position: 7
title: MCP Testing
---

# MCP Testing

Test MCP servers for protocol compliance and tool schema validation.

### `MCPTestResult`

`agentest.mcp_testing.server_tester.MCPTestResult`

Result of a single MCP test: `name`, `passed`, `message`, `latency_ms`.

### `MCPServerTester`

`agentest.mcp_testing.server_tester.MCPServerTester`

Tests MCP servers via persistent stdio connection. Supports context manager protocol for automatic lifecycle management.

**Constructor:** `MCPServerTester(command, env=None, timeout_seconds=30)`

**Lifecycle methods:**

- `start()` — Start the server process (called automatically on first request or `__enter__`)
- `close()` — Stop the server process (called automatically on `__exit__`)

**Test methods:**

- `test_initialize()` — Test server initialization
- `test_list_tools()` — Test tool listing
- `test_tool_call(tool_name, arguments, expected_result, expect_error)` — Test a specific tool
- `test_list_resources()` — Test resource listing
- `test_tool_schema_validation()` — Validate tool schemas (name, description, inputSchema structure, property types, required fields)
- `test_all_tools(tool_arguments=None)` — Smoke-test every listed tool with auto-generated minimal arguments
- `run_standard_tests()` — Run all standard compliance tests

### `MCPAssertions`

`agentest.mcp_testing.assertions.MCPAssertions`

Fluent assertion helper: `.all_passed()`, `.has_tool(name)`, `.tool_count_at_least(n)`, `.max_latency(ms)`, `.no_errors()`.
