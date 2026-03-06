"""Assertion helpers for MCP server testing."""

from __future__ import annotations

from agentest.mcp_testing.server_tester import MCPTestResult


class MCPAssertions:
    """Fluent assertion helpers for MCP test results.

    Usage:
        results = tester.run_standard_tests()
        assertions = MCPAssertions(results)

        assertions.all_passed()
        assertions.has_tool("read_file")
        assertions.tool_count_at_least(3)
    """

    def __init__(self, results: list[MCPTestResult]) -> None:
        self.results = results

    def all_passed(self) -> MCPAssertions:
        """Assert all tests passed."""
        failed = [r for r in self.results if not r.passed]
        if failed:
            failures = "\n".join(f"  - {r.test_name}: {r.error}" for r in failed)
            raise AssertionError(f"MCP tests failed:\n{failures}")
        return self

    def test_passed(self, test_name: str) -> MCPAssertions:
        """Assert a specific test passed."""
        matching = [r for r in self.results if r.test_name == test_name]
        if not matching:
            raise AssertionError(f"No test found with name {test_name!r}")
        if not matching[0].passed:
            raise AssertionError(f"Test {test_name!r} failed: {matching[0].error}")
        return self

    def has_tool(self, tool_name: str) -> MCPAssertions:
        """Assert the server exposes a tool with the given name."""
        list_results = [r for r in self.results if r.test_name == "list_tools"]
        if not list_results:
            raise AssertionError("No list_tools test result found")

        response = list_results[0].response or {}
        tools = response.get("result", {}).get("tools", [])
        tool_names = [t.get("name") for t in tools]

        if tool_name not in tool_names:
            raise AssertionError(f"Tool {tool_name!r} not found. Available: {tool_names}")
        return self

    def tool_count_at_least(self, n: int) -> MCPAssertions:
        """Assert at least N tools are exposed."""
        list_results = [r for r in self.results if r.test_name == "list_tools"]
        if not list_results:
            raise AssertionError("No list_tools test result found")

        response = list_results[0].response or {}
        tools = response.get("result", {}).get("tools", [])

        if len(tools) < n:
            raise AssertionError(f"Expected at least {n} tools, found {len(tools)}")
        return self

    def max_latency(self, max_ms: float) -> MCPAssertions:
        """Assert all tests completed within the given latency."""
        slow = [r for r in self.results if r.duration_ms > max_ms]
        if slow:
            details = "\n".join(f"  - {r.test_name}: {r.duration_ms:.0f}ms" for r in slow)
            raise AssertionError(f"Tests exceeded {max_ms:.0f}ms latency:\n{details}")
        return self

    def no_errors(self) -> MCPAssertions:
        """Assert no tests had errors (excluding 'not supported' errors)."""
        errors = [r for r in self.results if r.error and "Not supported" not in r.error]
        if errors:
            details = "\n".join(f"  - {r.test_name}: {r.error}" for r in errors)
            raise AssertionError(f"Tests had errors:\n{details}")
        return self
