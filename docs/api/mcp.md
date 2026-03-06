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

Tests MCP servers. Methods:

- `test_initialize()` — Test server initialization
- `test_list_tools()` — Test tool listing
- `test_tool_call(tool_name, arguments, expected_result)` — Test a specific tool
- `test_list_resources()` — Test resource listing
- `test_tool_schema_validation()` — Validate tool schemas
- `run_standard_tests()` — Run all standard compliance tests

### `MCPAssertions`

`agentest.mcp_testing.assertions.MCPAssertions`

Fluent assertion helper: `.all_passed()`, `.has_tool(name)`, `.tool_count_at_least(n)`, `.max_latency(ms)`, `.no_errors()`.
