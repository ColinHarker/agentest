"""Tests for MCP server tester and assertions."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agentest.mcp_testing.assertions import MCPAssertions
from agentest.mcp_testing.server_tester import MCPServerTester, MCPTestResult

# ---- Helpers ----


def _mock_popen(responses: list[str]) -> MagicMock:
    """Create a mock Popen that returns JSON responses in order."""
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = ""
    mock_proc.stdout.readline = MagicMock(side_effect=[r + "\n" for r in responses])
    mock_proc.stdout.fileno = MagicMock(return_value=0)
    mock_proc.poll.return_value = None  # process still running
    mock_proc.wait.return_value = 0
    return mock_proc


def _mock_selector() -> MagicMock:
    """Create a mock selector that always indicates ready."""
    mock_sel = MagicMock()
    mock_sel.select.return_value = [("ready",)]  # non-empty = ready
    return mock_sel


def _patch_popen_and_selector(mock_proc: MagicMock):
    """Return stacked context managers for Popen and selector patches."""
    return (
        patch("subprocess.Popen", return_value=mock_proc),
        patch("selectors.DefaultSelector", return_value=_mock_selector()),
    )


# ---- MCPTestResult ----


def test_mcp_test_result_repr_pass():
    r = MCPTestResult(test_name="init", passed=True, duration_ms=42.5)
    assert "PASS" in repr(r)
    assert "init" in repr(r)


def test_mcp_test_result_repr_fail():
    r = MCPTestResult(test_name="init", passed=False, duration_ms=100.0, error="bad")
    assert "FAIL" in repr(r)


# ---- MCPServerTester._make_request ----


def test_make_request_basic():
    tester = MCPServerTester(command=["echo"])
    req = tester._make_request("initialize")
    assert req["jsonrpc"] == "2.0"
    assert req["method"] == "initialize"
    assert req["id"] == 1
    assert "params" not in req


def test_make_request_with_params():
    tester = MCPServerTester(command=["echo"])
    req = tester._make_request("tools/call", {"name": "foo"})
    assert req["params"] == {"name": "foo"}


def test_make_request_increments_id():
    tester = MCPServerTester(command=["echo"])
    r1 = tester._make_request("a")
    r2 = tester._make_request("b")
    assert r2["id"] == r1["id"] + 1


# ---- MCPServerTester lifecycle ----


def test_context_manager_lifecycle():
    mock_proc = _mock_popen([])
    with patch("subprocess.Popen", return_value=mock_proc):
        with MCPServerTester(command=["fake-server"]) as tester:
            assert tester._process is not None
        # After exit, process should be cleaned up
        mock_proc.terminate.assert_called_once()


def test_lazy_start():
    response = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})
    mock_proc = _mock_popen([response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake"])
        assert tester._process is None  # not started yet
        tester.test_list_tools()
        assert tester._process is not None  # started on first request
        tester.close()


def test_close_idempotent():
    mock_proc = _mock_popen([])
    with patch("subprocess.Popen", return_value=mock_proc):
        tester = MCPServerTester(command=["fake"])
        tester.start()
        tester.close()
        tester.close()  # second close should not raise
        assert tester._process is None


# ---- MCPServerTester.test_initialize ----


def test_initialize_success():
    response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
            },
        }
    )
    # Two responses: one for initialize, one consumed by the initialized notification
    mock_proc = _mock_popen([response, "{}"])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake-server"])
        result = tester.test_initialize()
        tester.close()

    assert result.passed is True
    assert result.test_name == "initialize"
    assert result.error is None


def test_initialize_missing_fields():
    response = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}})
    mock_proc = _mock_popen([response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake-server"])
        result = tester.test_initialize()
        tester.close()

    assert result.passed is False
    assert "Missing" in result.error


def test_initialize_error_response():
    response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -1, "message": "crash"},
        }
    )
    mock_proc = _mock_popen([response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake-server"])
        result = tester.test_initialize()
        tester.close()

    assert result.passed is False
    assert result.error == "crash"


# ---- MCPServerTester.test_list_tools ----


def test_list_tools_success():
    response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": [{"name": "read_file"}, {"name": "write_file"}]},
        }
    )
    mock_proc = _mock_popen([response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake"])
        result = tester.test_list_tools()
        tester.close()

    assert result.passed is True
    assert result.test_name == "list_tools"


# ---- Error handling ----


def test_timeout_handling():
    mock_proc = _mock_popen([])
    mock_sel = MagicMock()
    mock_sel.select.return_value = []  # empty = timeout

    with (
        patch("subprocess.Popen", return_value=mock_proc),
        patch("selectors.DefaultSelector", return_value=mock_sel),
    ):
        tester = MCPServerTester(command=["slow-server"], timeout_seconds=5)
        result = tester.test_initialize()
        tester.close()

    assert result.passed is False
    assert "Timeout" in result.error


def test_file_not_found_handling():
    with patch("subprocess.Popen", side_effect=FileNotFoundError()):
        tester = MCPServerTester(command=["nonexistent"])
        result = tester.test_initialize()

    assert result.passed is False
    assert "Command not found" in result.error


def test_invalid_json_handling():
    mock_proc = _mock_popen(["not json at all"])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["bad-server"])
        result = tester.test_list_tools()
        tester.close()

    assert result.passed is False
    assert "Invalid JSON" in result.error


def test_process_crash_detection():
    mock_proc = _mock_popen([])
    mock_proc.stdout.readline = MagicMock(return_value="")  # empty = EOF
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["crash-server"])
        result = tester.test_list_tools()
        tester.close()

    assert result.passed is False


# ---- Schema validation ----


def test_schema_validation_valid():
    tools_response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {
                        "name": "read_file",
                        "description": "Read a file",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"path": {"type": "string"}},
                            "required": ["path"],
                        },
                    }
                ]
            },
        }
    )
    mock_proc = _mock_popen([tools_response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake"])
        results = tester.test_tool_schema_validation()
        tester.close()

    assert len(results) == 1
    assert results[0].passed is True


def test_schema_validation_invalid_properties():
    tools_response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {
                        "name": "bad_tool",
                        "description": "Has bad schema",
                        "inputSchema": {
                            "type": "object",
                            "properties": "not a dict",
                        },
                    }
                ]
            },
        }
    )
    mock_proc = _mock_popen([tools_response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake"])
        results = tester.test_tool_schema_validation()
        tester.close()

    assert len(results) == 1
    assert results[0].passed is False
    assert "properties is not a dict" in results[0].error


def test_schema_validation_missing_required_in_properties():
    tools_response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {
                        "name": "tool",
                        "description": "Missing required field",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"a": {"type": "string"}},
                            "required": ["a", "b"],
                        },
                    }
                ]
            },
        }
    )
    mock_proc = _mock_popen([tools_response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake"])
        results = tester.test_tool_schema_validation()
        tester.close()

    assert len(results) == 1
    assert "required fields not in properties" in results[0].error


def test_schema_validation_invalid_property_type():
    tools_response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {
                        "name": "tool",
                        "description": "Bad type",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"x": {"type": "banana"}},
                        },
                    }
                ]
            },
        }
    )
    mock_proc = _mock_popen([tools_response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake"])
        results = tester.test_tool_schema_validation()
        tester.close()

    assert len(results) == 1
    assert results[0].passed is False
    assert "invalid type" in results[0].error


# ---- test_all_tools ----


def test_all_tools_calls_each_tool():
    tools_response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {"name": "tool_a", "inputSchema": {"type": "object"}},
                    {"name": "tool_b", "inputSchema": {"type": "object"}},
                ]
            },
        }
    )
    call_a_response = json.dumps(
        {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "ok"}]}}
    )
    call_b_response = json.dumps(
        {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "ok"}]}}
    )
    mock_proc = _mock_popen([tools_response, call_a_response, call_b_response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake"])
        results = tester.test_all_tools()
        tester.close()

    assert len(results) == 2
    assert results[0].test_name == "tool_call:tool_a"
    assert results[1].test_name == "tool_call:tool_b"
    assert all(r.passed for r in results)


def test_all_tools_with_custom_args():
    tools_response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]},
        }
    )
    call_response = json.dumps(
        {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "hello"}]}}
    )
    mock_proc = _mock_popen([tools_response, call_response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake"])
        results = tester.test_all_tools(tool_arguments={"echo": {"input": "hello"}})
        tester.close()

    assert len(results) == 1
    assert results[0].passed


def test_all_tools_generates_defaults():
    tools_response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {
                        "name": "greet",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "count": {"type": "integer"},
                            },
                            "required": ["name"],
                        },
                    }
                ]
            },
        }
    )
    call_response = json.dumps(
        {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "hi"}]}}
    )
    mock_proc = _mock_popen([tools_response, call_response])
    popen_patch, sel_patch = _patch_popen_and_selector(mock_proc)

    with popen_patch, sel_patch:
        tester = MCPServerTester(command=["fake"])
        results = tester.test_all_tools()
        tester.close()

    assert len(results) == 1
    assert results[0].passed
    # Verify default args were generated (name is required, should get "")
    call_args = json.loads(mock_proc.stdin.write.call_args_list[1][0][0])
    assert call_args["params"]["arguments"]["name"] == ""


def test_generate_default_args_enum():
    tool = {
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["json", "yaml"]},
            },
            "required": ["format"],
        }
    }
    args = MCPServerTester._generate_default_args(tool)
    assert args == {"format": "json"}


def test_generate_default_args_with_default_value():
    tool = {
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "default": 10},
            },
            "required": ["count"],
        }
    }
    args = MCPServerTester._generate_default_args(tool)
    assert args == {"count": 10}


# ---- MCPAssertions ----


def _make_results(passed_list, names=None):
    """Helper to create test results."""
    results = []
    for i, passed in enumerate(passed_list):
        name = names[i] if names else f"test_{i}"
        results.append(
            MCPTestResult(
                test_name=name,
                passed=passed,
                duration_ms=10.0,
                error=None if passed else f"{name} failed",
            )
        )
    return results


def test_assertions_all_passed_success():
    results = _make_results([True, True, True])
    a = MCPAssertions(results)
    assert a.all_passed() is a  # returns self for chaining


def test_assertions_all_passed_failure():
    results = _make_results([True, False])
    with pytest.raises(AssertionError, match="MCP tests failed"):
        MCPAssertions(results).all_passed()


def test_assertions_test_passed():
    results = _make_results([True, False], names=["init", "list"])
    a = MCPAssertions(results)
    assert a.test_passed("init") is a

    with pytest.raises(AssertionError, match="failed"):
        a.test_passed("list")


def test_assertions_test_passed_not_found():
    results = _make_results([True], names=["init"])
    with pytest.raises(AssertionError, match="No test found"):
        MCPAssertions(results).test_passed("nonexistent")


def test_assertions_has_tool():
    results = [
        MCPTestResult(
            test_name="list_tools",
            passed=True,
            duration_ms=5.0,
            response={
                "result": {"tools": [{"name": "read_file"}, {"name": "write_file"}]},
            },
        )
    ]
    a = MCPAssertions(results)
    assert a.has_tool("read_file") is a

    with pytest.raises(AssertionError, match="not found"):
        a.has_tool("delete_file")


def test_assertions_tool_count_at_least():
    results = [
        MCPTestResult(
            test_name="list_tools",
            passed=True,
            duration_ms=5.0,
            response={"result": {"tools": [{"name": "a"}, {"name": "b"}]}},
        )
    ]
    a = MCPAssertions(results)
    assert a.tool_count_at_least(2) is a
    assert a.tool_count_at_least(1) is a

    with pytest.raises(AssertionError, match="Expected at least 5"):
        a.tool_count_at_least(5)


def test_assertions_max_latency():
    results = _make_results([True, True])
    results[0].duration_ms = 50
    results[1].duration_ms = 200

    a = MCPAssertions(results)
    assert a.max_latency(300) is a

    with pytest.raises(AssertionError, match="exceeded"):
        a.max_latency(100)


def test_assertions_no_errors():
    results = _make_results([True, True])
    MCPAssertions(results).no_errors()  # should not raise

    # "Not supported" errors should be ignored
    results[0].error = "Not supported (OK)"
    MCPAssertions(results).no_errors()

    # Real errors should raise
    results[1].error = "connection refused"
    with pytest.raises(AssertionError, match="errors"):
        MCPAssertions(results).no_errors()


def test_assertions_chaining():
    results = [
        MCPTestResult(
            test_name="list_tools",
            passed=True,
            duration_ms=5.0,
            response={"result": {"tools": [{"name": "a"}]}},
        )
    ]
    # Chained calls should all return self
    a = (
        MCPAssertions(results)
        .all_passed()
        .test_passed("list_tools")
        .has_tool("a")
        .tool_count_at_least(1)
        .max_latency(1000)
        .no_errors()
    )
    assert isinstance(a, MCPAssertions)
