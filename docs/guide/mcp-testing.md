---
sidebar_position: 6
title: MCP Server Testing
---

# MCP Server Testing

Test MCP (Model Context Protocol) servers for protocol compliance and tool schema validation.

## Basic Usage

`MCPServerTester` maintains a persistent connection to the MCP server process via stdin/stdout pipes. Use it as a context manager for automatic cleanup:

```python
from agentest.mcp_testing import MCPServerTester, MCPAssertions

# Context manager (recommended) — starts process on enter, stops on exit
with MCPServerTester(
    command=["python", "-m", "my_mcp_server"],
    env={"API_KEY": "test"},
    timeout_seconds=30,
) as tester:
    results = tester.run_standard_tests()
    MCPAssertions(results).all_passed()
```

Without a context manager, the process starts lazily on the first request. Call `close()` when done:

```python
tester = MCPServerTester(command=["python", "-m", "my_mcp_server"])
results = tester.run_standard_tests()
tester.close()
```

## Individual Tests

```python
with MCPServerTester(command=["python", "-m", "my_mcp_server"]) as tester:
    # Test initialization
    result = tester.test_initialize()
    assert result.passed

    # Test tool listing
    result = tester.test_list_tools()
    assert result.passed

    # Test a specific tool
    result = tester.test_tool_call(
        tool_name="read_file",
        arguments={"path": "/tmp/test.txt"},
        expected_result="file contents",
    )
    assert result.passed

    # Test resource listing (optional capability)
    result = tester.test_list_resources()
```

## Test All Tools

Smoke-test every tool the server exposes with auto-generated minimal arguments:

```python
with MCPServerTester(command=["python", "-m", "my_mcp_server"]) as tester:
    tester.test_initialize()

    # Calls each listed tool with minimal valid arguments
    results = tester.test_all_tools()
    MCPAssertions(results).all_passed()

    # Override arguments for specific tools
    results = tester.test_all_tools(tool_arguments={
        "read_file": {"path": "/tmp/test.txt"},
        "search": {"query": "hello"},
    })
```

Tools not in `tool_arguments` are called with defaults generated from their `inputSchema` (required fields only, using type-appropriate values like `""` for strings, `0` for integers, etc.).

## Schema Validation

```python
with MCPServerTester(command=["python", "-m", "my_mcp_server"]) as tester:
    tester.test_initialize()
    results = tester.test_tool_schema_validation()
    MCPAssertions(results).all_passed()
```

Validates each tool has:
- A `name` and `description`
- A valid `inputSchema` with `type: "object"`
- Valid property types (`string`, `number`, `integer`, `boolean`, `array`, `object`, `null`)
- `required` fields that exist in `properties`

## Fluent Assertions

```python
MCPAssertions(results) \
    .all_passed() \
    .has_tool("read_file") \
    .tool_count_at_least(3) \
    .max_latency(5000) \
    .no_errors()
```

All assertion methods return `self` for chaining.
