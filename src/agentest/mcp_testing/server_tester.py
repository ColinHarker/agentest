"""Test MCP servers in isolation."""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPTestResult:
    """Result of an MCP server test."""

    test_name: str
    passed: bool
    duration_ms: float
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    error: str | None = None

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"MCPTestResult({self.test_name}: {status} {self.duration_ms:.0f}ms)"


class MCPServerTester:
    """Test an MCP server by sending requests and verifying responses.

    Supports MCP servers launched via stdio (subprocess) transport.

    Usage:
        tester = MCPServerTester(
            command=["python", "-m", "my_mcp_server"],
            env={"API_KEY": "test"},
        )

        # Test tool listing
        result = tester.test_list_tools()
        assert result.passed

        # Test a specific tool call
        result = tester.test_tool_call(
            tool_name="read_file",
            arguments={"path": "/tmp/test.txt"},
            expected_result="file contents",
        )
        assert result.passed

        # Run all standard tests
        results = tester.run_standard_tests()
    """

    def __init__(
        self,
        command: list[str],
        env: dict[str, str] | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self.command = command
        self.env = env
        self.timeout_seconds = timeout_seconds
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _make_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a JSON-RPC request."""
        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            request["params"] = params
        return request

    def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send a request to the MCP server via stdio and get the response."""
        input_data = json.dumps(request) + "\n"

        try:
            result = subprocess.run(
                self.command,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=self.env,
            )

            if result.returncode != 0 and not result.stdout.strip():
                return {"error": {"code": -1, "message": result.stderr.strip()}}

            # Parse the first JSON line from stdout
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line:
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue

            return {"error": {"code": -1, "message": "No valid JSON response"}}

        except subprocess.TimeoutExpired:
            return {"error": {"code": -2, "message": f"Timeout after {self.timeout_seconds}s"}}
        except FileNotFoundError:
            return {"error": {"code": -3, "message": f"Command not found: {self.command}"}}

    def test_initialize(self) -> MCPTestResult:
        """Test MCP server initialization."""
        start = time.time()
        request = self._make_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "agentest", "version": "0.1.0"},
        })

        response = self._send_request(request)
        duration = (time.time() - start) * 1000

        error = response.get("error")
        if error:
            return MCPTestResult(
                test_name="initialize",
                passed=False,
                duration_ms=duration,
                request=request,
                response=response,
                error=error.get("message", str(error)),
            )

        result = response.get("result", {})
        has_version = "protocolVersion" in result
        has_capabilities = "capabilities" in result

        return MCPTestResult(
            test_name="initialize",
            passed=has_version and has_capabilities,
            duration_ms=duration,
            request=request,
            response=response,
            error=None if (has_version and has_capabilities)
            else "Missing protocolVersion or capabilities in response",
        )

    def test_list_tools(self) -> MCPTestResult:
        """Test that the server can list its tools."""
        start = time.time()
        request = self._make_request("tools/list")
        response = self._send_request(request)
        duration = (time.time() - start) * 1000

        error = response.get("error")
        if error:
            return MCPTestResult(
                test_name="list_tools",
                passed=False,
                duration_ms=duration,
                request=request,
                response=response,
                error=error.get("message", str(error)),
            )

        result = response.get("result", {})
        tools = result.get("tools", [])

        return MCPTestResult(
            test_name="list_tools",
            passed=isinstance(tools, list),
            duration_ms=duration,
            request=request,
            response=response,
        )

    def test_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        expected_result: Any = None,
        expect_error: bool = False,
    ) -> MCPTestResult:
        """Test a specific tool call."""
        start = time.time()
        request = self._make_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })

        response = self._send_request(request)
        duration = (time.time() - start) * 1000

        error = response.get("error")

        if expect_error:
            return MCPTestResult(
                test_name=f"tool_call:{tool_name}",
                passed=error is not None,
                duration_ms=duration,
                request=request,
                response=response,
                error=None if error else "Expected error but got success",
            )

        if error:
            return MCPTestResult(
                test_name=f"tool_call:{tool_name}",
                passed=False,
                duration_ms=duration,
                request=request,
                response=response,
                error=error.get("message", str(error)),
            )

        result = response.get("result")
        passed = True

        if expected_result is not None:
            # Compare content if it's MCP content format
            if isinstance(result, dict) and "content" in result:
                actual = result["content"]
                if isinstance(actual, list) and actual:
                    actual_text = actual[0].get("text", "")
                    passed = actual_text == expected_result or expected_result in actual_text
                else:
                    passed = actual == expected_result
            else:
                passed = result == expected_result

        return MCPTestResult(
            test_name=f"tool_call:{tool_name}",
            passed=passed,
            duration_ms=duration,
            request=request,
            response=response,
            error=None if passed else f"Result mismatch",
        )

    def test_list_resources(self) -> MCPTestResult:
        """Test resource listing if supported."""
        start = time.time()
        request = self._make_request("resources/list")
        response = self._send_request(request)
        duration = (time.time() - start) * 1000

        error = response.get("error")
        # Method not found is acceptable (optional capability)
        if error and error.get("code") == -32601:
            return MCPTestResult(
                test_name="list_resources",
                passed=True,
                duration_ms=duration,
                request=request,
                response=response,
                error="Not supported (OK)",
            )

        return MCPTestResult(
            test_name="list_resources",
            passed=error is None,
            duration_ms=duration,
            request=request,
            response=response,
            error=error.get("message") if error else None,
        )

    def run_standard_tests(self) -> list[MCPTestResult]:
        """Run all standard MCP compliance tests."""
        results = [
            self.test_initialize(),
            self.test_list_tools(),
            self.test_list_resources(),
        ]
        return results

    def test_tool_schema_validation(self) -> list[MCPTestResult]:
        """Test that all listed tools have valid schemas."""
        results: list[MCPTestResult] = []

        list_result = self.test_list_tools()
        if not list_result.passed or not list_result.response:
            return [list_result]

        tools = list_result.response.get("result", {}).get("tools", [])

        for tool in tools:
            start = time.time()
            name = tool.get("name", "unknown")
            has_name = bool(tool.get("name"))
            has_description = bool(tool.get("description"))
            has_schema = "inputSchema" in tool
            valid_schema = True

            if has_schema:
                schema = tool["inputSchema"]
                valid_schema = (
                    isinstance(schema, dict)
                    and schema.get("type") == "object"
                )

            duration = (time.time() - start) * 1000
            issues = []
            if not has_name:
                issues.append("missing name")
            if not has_description:
                issues.append("missing description")
            if not has_schema:
                issues.append("missing inputSchema")
            if not valid_schema:
                issues.append("invalid inputSchema")

            results.append(MCPTestResult(
                test_name=f"schema:{name}",
                passed=has_name and has_description and valid_schema,
                duration_ms=duration,
                error="; ".join(issues) if issues else None,
            ))

        return results
