"""Tests for tool mocking framework."""

import pytest

from agentest.mocking.tool_mock import MockToolkit, ToolMock


def test_tool_mock_simple_return():
    mock = ToolMock("read_file").returns("file contents")
    result = mock(path="test.txt")
    assert result == "file contents"
    assert mock.call_count == 1


def test_tool_mock_conditional():
    mock = (
        ToolMock("search")
        .when(query="python").returns(["py_result"])
        .when(query="rust").returns(["rs_result"])
        .otherwise().returns([])
    )

    assert mock(query="python") == ["py_result"]
    assert mock(query="rust") == ["rs_result"]
    assert mock(query="javascript") == []


def test_tool_mock_sequence():
    mock = ToolMock("get_page").returns_sequence(["page1", "page2", "page3"])

    assert mock() == "page1"
    assert mock() == "page2"
    assert mock() == "page3"

    with pytest.raises(IndexError):
        mock()


def test_tool_mock_raises():
    mock = ToolMock("dangerous").raises(PermissionError("denied"))

    with pytest.raises(PermissionError, match="denied"):
        mock()


def test_tool_mock_conditional_error():
    mock = (
        ToolMock("write")
        .when(path="/etc/passwd").raises(PermissionError("no"))
        .otherwise().returns(True)
    )

    assert mock(path="/tmp/test.txt") is True
    with pytest.raises(PermissionError):
        mock(path="/etc/passwd")


def test_tool_mock_custom_handler():
    mock = ToolMock("calc").responds_with(lambda args: args["a"] + args["b"])

    assert mock(a=3, b=4) == 7
    assert mock(a=10, b=20) == 30


def test_tool_mock_assertions():
    mock = ToolMock("search").returns([])

    with pytest.raises(AssertionError):
        mock.assert_called()

    mock(query="test")
    mock.assert_called()
    mock.assert_called_times(1)
    mock.assert_called_with(query="test")


def test_tool_mock_regex_matching():
    mock = (
        ToolMock("search")
        .when(query=r"python.*async").returns(["async_result"])
        .otherwise().returns([])
    )

    assert mock(query="python async await") == ["async_result"]
    assert mock(query="javascript") == []


def test_tool_mock_reset():
    mock = ToolMock("tool").returns("ok")
    mock()
    mock()
    assert mock.call_count == 2

    mock.reset()
    assert mock.call_count == 0


def test_mock_toolkit():
    toolkit = MockToolkit()
    toolkit.mock("read_file").returns("contents")
    toolkit.mock("write_file").returns(True)

    assert toolkit.execute("read_file", path="test.txt") == "contents"
    assert toolkit.execute("write_file", path="out.txt", data="hello") is True


def test_mock_toolkit_missing_tool():
    toolkit = MockToolkit()

    with pytest.raises(KeyError, match="read_file"):
        toolkit.execute("read_file")


def test_mock_toolkit_assert_all_called():
    toolkit = MockToolkit()
    toolkit.mock("tool1").returns("a")
    toolkit.mock("tool2").returns("b")

    toolkit.execute("tool1")

    with pytest.raises(AssertionError, match="tool2"):
        toolkit.assert_all_called()


def test_mock_toolkit_summary():
    toolkit = MockToolkit()
    toolkit.mock("read").returns("ok")
    toolkit.mock("write").returns(True)

    toolkit.execute("read")
    toolkit.execute("read")
    toolkit.execute("write")

    summary = toolkit.summary()
    assert summary["read"] == 2
    assert summary["write"] == 1
