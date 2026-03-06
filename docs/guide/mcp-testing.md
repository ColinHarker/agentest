---
sidebar_position: 6
title: MCP Server Testing
---

# MCP Server Testing

Test MCP (Model Context Protocol) servers for protocol compliance and tool schema validation.

## Basic Usage

```python
from agentest.mcp_testing import MCPServerTester, MCPAssertions

tester = MCPServerTester(
    command=["python", "-m", "my_mcp_server"],
    env={"API_KEY": "test"},
    timeout_seconds=30,
)

# Run standard compliance tests
results = tester.run_standard_tests()
MCPAssertions(results).all_passed()
```

## Individual Tests

```python
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

## Schema Validation

```python
results = tester.test_tool_schema_validation()
MCPAssertions(results).all_passed()
```

Checks that each tool has a `name`, `description`, and valid `inputSchema` (JSON Schema object type).

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
