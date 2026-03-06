"""Tests for MCP server tester and assertions."""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from agentest.mcp_testing.server_tester import MCPServerTester, MCPTestResult
from agentest.mcp_testing.assertions import MCPAssertions


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


# ---- MCPServerTester.test_initialize ----

def test_initialize_success():
    response = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
        },
    })
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = response + "\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        tester = MCPServerTester(command=["fake-server"])
        result = tester.test_initialize()

    assert result.passed is True
    assert result.test_name == "initialize"
    assert result.error is None


def test_initialize_missing_fields():
    response = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}})
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = response + "\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        tester = MCPServerTester(command=["fake-server"])
        result = tester.test_initialize()

    assert result.passed is False
    assert "Missing" in result.error


def test_initialize_error_response():
    response = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -1, "message": "crash"},
    })
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = response + "\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        tester = MCPServerTester(command=["fake-server"])
        result = tester.test_initialize()

    assert result.passed is False
    assert result.error == "crash"


# ---- MCPServerTester.test_list_tools ----

def test_list_tools_success():
    response = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": [{"name": "read_file"}, {"name": "write_file"}]},
    })
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = response + "\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        tester = MCPServerTester(command=["fake"])
        result = tester.test_list_tools()

    assert result.passed is True
    assert result.test_name == "list_tools"


# ---- Error handling ----

def test_timeout_handling():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=5)):
        tester = MCPServerTester(command=["slow-server"], timeout_seconds=5)
        result = tester.test_initialize()

    assert result.passed is False
    assert "Timeout" in result.error


def test_file_not_found_handling():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        tester = MCPServerTester(command=["nonexistent"])
        result = tester.test_initialize()

    assert result.passed is False
    assert "Command not found" in result.error


def test_invalid_json_handling():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "not json at all\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        tester = MCPServerTester(command=["bad-server"])
        result = tester.test_list_tools()

    assert result.passed is False
    assert "No valid JSON" in result.error


def test_nonzero_exit_no_stdout():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "segfault"

    with patch("subprocess.run", return_value=mock_result):
        tester = MCPServerTester(command=["crash-server"])
        result = tester.test_list_tools()

    assert result.passed is False
    assert "segfault" in result.error


# ---- MCPAssertions ----

def _make_results(passed_list, names=None):
    """Helper to create test results."""
    results = []
    for i, passed in enumerate(passed_list):
        name = names[i] if names else f"test_{i}"
        results.append(MCPTestResult(
            test_name=name,
            passed=passed,
            duration_ms=10.0,
            error=None if passed else f"{name} failed",
        ))
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
    results = [MCPTestResult(
        test_name="list_tools",
        passed=True,
        duration_ms=5.0,
        response={
            "result": {"tools": [{"name": "read_file"}, {"name": "write_file"}]},
        },
    )]
    a = MCPAssertions(results)
    assert a.has_tool("read_file") is a

    with pytest.raises(AssertionError, match="not found"):
        a.has_tool("delete_file")


def test_assertions_tool_count_at_least():
    results = [MCPTestResult(
        test_name="list_tools",
        passed=True,
        duration_ms=5.0,
        response={"result": {"tools": [{"name": "a"}, {"name": "b"}]}},
    )]
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
    results = [MCPTestResult(
        test_name="list_tools",
        passed=True,
        duration_ms=5.0,
        response={"result": {"tools": [{"name": "a"}]}},
    )]
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
