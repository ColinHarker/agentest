"""Test MCP servers in isolation."""

from __future__ import annotations

import json
import selectors
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import agentest


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
    Maintains a persistent connection to the server process for session
    continuity and stateful testing.

    Usage:
        # As context manager (recommended)
        with MCPServerTester(command=["python", "-m", "my_mcp_server"]) as tester:
            result = tester.test_initialize()
            assert result.passed

            result = tester.test_tool_call("read_file", {"path": "/tmp/test.txt"})
            assert result.passed

        # Without context manager (lazy start, cleanup on garbage collection)
        tester = MCPServerTester(command=["python", "-m", "my_mcp_server"])
        result = tester.test_list_tools()
        tester.close()
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
        self._process: subprocess.Popen[str] | None = None
        self._start_error: str | None = None

    def start(self) -> None:
        """Start the MCP server process."""
        if self._process is not None:
            return
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self.env,
            )
        except FileNotFoundError:
            self._start_error = f"Command not found: {self.command}"

    def close(self) -> None:
        """Stop the MCP server process."""
        if self._process is None:
            return
        try:
            if self._process.stdin:
                self._process.stdin.close()
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        except OSError:
            pass
        self._process = None

    def __enter__(self) -> MCPServerTester:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def _ensure_started(self) -> None:
        """Lazily start the server if not already running."""
        if self._process is None and self._start_error is None:
            self.start()

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
        """Send a request to the MCP server via persistent stdio connection."""
        self._ensure_started()

        if self._start_error:
            return {"error": {"code": -3, "message": self._start_error}}

        proc = self._process
        if proc is None or proc.stdin is None or proc.stdout is None:
            return {"error": {"code": -1, "message": "Server process not available"}}

        # Check if process has died
        if proc.poll() is not None:
            stderr = proc.stderr.read() if proc.stderr else ""
            return {"error": {"code": -1, "message": stderr.strip() or "Server process died"}}

        line = json.dumps(request) + "\n"
        try:
            proc.stdin.write(line)
            proc.stdin.flush()
        except (BrokenPipeError, OSError):
            return {"error": {"code": -1, "message": "Server process died"}}

        # Read response with timeout using selectors
        sel = selectors.DefaultSelector()
        try:
            sel.register(proc.stdout, selectors.EVENT_READ)
            ready = sel.select(timeout=self.timeout_seconds)
        finally:
            sel.close()

        if not ready:
            return {"error": {"code": -2, "message": f"Timeout after {self.timeout_seconds}s"}}

        response_line = proc.stdout.readline()
        if not response_line:
            stderr = proc.stderr.read() if proc.stderr else ""
            return {"error": {"code": -1, "message": stderr.strip() or "Server closed connection"}}

        try:
            parsed: dict[str, Any] = json.loads(response_line)
            return parsed
        except json.JSONDecodeError:
            return {"error": {"code": -1, "message": "Invalid JSON response"}}

    def test_initialize(self) -> MCPTestResult:
        """Test MCP server initialization."""
        start = time.time()
        request = self._make_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agentest", "version": agentest.__version__},
            },
        )

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

        if has_version and has_capabilities:
            # Send initialized notification as required by MCP protocol
            self._send_request({"jsonrpc": "2.0", "method": "notifications/initialized"})

        return MCPTestResult(
            test_name="initialize",
            passed=has_version and has_capabilities,
            duration_ms=duration,
            request=request,
            response=response,
            error=None
            if (has_version and has_capabilities)
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
        request = self._make_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments or {},
            },
        )

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
            error=None if passed else "Result mismatch",
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
        valid_types = {"string", "number", "integer", "boolean", "array", "object", "null"}

        for tool in tools:
            start = time.time()
            name = tool.get("name", "unknown")
            has_name = bool(tool.get("name"))
            has_description = bool(tool.get("description"))
            has_schema = "inputSchema" in tool
            valid_schema = True

            issues: list[str] = []

            if has_schema:
                schema = tool["inputSchema"]
                valid_schema = isinstance(schema, dict) and schema.get("type") == "object"

                # Validate properties
                props = schema.get("properties", {})
                if not isinstance(props, dict):
                    valid_schema = False
                    issues.append("properties is not a dict")
                else:
                    # Validate property types
                    for prop_name, prop_def in props.items():
                        if isinstance(prop_def, dict):
                            prop_type = prop_def.get("type")
                            if prop_type and prop_type not in valid_types:
                                issues.append(
                                    f"property {prop_name!r} has invalid type: {prop_type!r}"
                                )
                                valid_schema = False

                # Validate required
                required = schema.get("required", [])
                if not isinstance(required, list):
                    valid_schema = False
                    issues.append("required is not a list")
                elif isinstance(props, dict) and props:
                    missing_required = [r for r in required if r not in props]
                    if missing_required:
                        issues.append(f"required fields not in properties: {missing_required}")

            duration = (time.time() - start) * 1000

            if not has_name:
                issues.append("missing name")
            if not has_description:
                issues.append("missing description")
            if not has_schema:
                issues.append("missing inputSchema")

            results.append(
                MCPTestResult(
                    test_name=f"schema:{name}",
                    passed=has_name and has_description and valid_schema,
                    duration_ms=duration,
                    error="; ".join(issues) if issues else None,
                )
            )

        return results

    def test_all_tools(
        self, tool_arguments: dict[str, dict[str, Any]] | None = None
    ) -> list[MCPTestResult]:
        """Test every listed tool by calling it with minimal arguments.

        Args:
            tool_arguments: Optional mapping of tool_name -> arguments to use.
                Tools not in this dict will be called with arguments
                generated from their inputSchema defaults.
        """
        tool_arguments = tool_arguments or {}
        results: list[MCPTestResult] = []

        list_result = self.test_list_tools()
        if not list_result.passed or not list_result.response:
            return [list_result]

        tools = list_result.response.get("result", {}).get("tools", [])

        for tool in tools:
            name = tool.get("name", "unknown")
            args = tool_arguments.get(name, self._generate_default_args(tool))
            result = self.test_tool_call(tool_name=name, arguments=args)
            results.append(result)

        return results

    @staticmethod
    def _generate_default_args(tool: dict[str, Any]) -> dict[str, Any]:
        """Generate minimal valid arguments from a tool's inputSchema."""
        schema = tool.get("inputSchema", {})
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        args: dict[str, Any] = {}

        type_defaults: dict[str, Any] = {
            "string": "",
            "number": 0,
            "integer": 0,
            "boolean": False,
            "array": [],
            "object": {},
        }

        for field_name in required:
            prop = properties.get(field_name, {})
            field_type = prop.get("type", "string")
            # Use enum first value if available
            if "enum" in prop and prop["enum"]:
                args[field_name] = prop["enum"][0]
            elif "default" in prop:
                args[field_name] = prop["default"]
            else:
                args[field_name] = type_defaults.get(field_type, "")

        return args
