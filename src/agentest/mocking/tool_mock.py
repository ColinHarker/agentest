"""Mock tools for deterministic agent testing."""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_global_call_counter = itertools.count()
# Internal sentinel to distinguish "no default provided" from None.
# When default_after_exhaustion is _SENTINEL, IndexError is raised on sequence
# exhaustion. This allows None to be a valid explicit default value.
_SENTINEL = object()


@dataclass
class ToolCallRecord:
    """Record of a mock tool being called."""

    name: str
    arguments: dict[str, Any]
    result: Any
    call_index: int
    global_index: int = 0


class ToolMock:
    """A configurable mock for a single tool.

    Usage:
        # Simple static return
        mock = ToolMock("read_file").returns("file contents here")

        # Conditional returns
        mock = (ToolMock("search")
            .when(query="python").returns(["result1", "result2"])
            .when(query="rust").returns(["result3"])
            .otherwise().returns([]))

        # Sequential returns
        mock = ToolMock("get_page").returns_sequence([
            "page 1 content",
            "page 2 content",
            "page 3 content",
        ])

        # Side effects
        mock = ToolMock("dangerous_action").raises(PermissionError("denied"))

        # Custom logic
        mock = ToolMock("calculator").responds_with(
            lambda args: args["a"] + args["b"]
        )
    """

    def __init__(self, name: str) -> None:
        """Initialize a mock for the tool with the given name."""
        self.name = name
        self._default_result: Any = None
        self._default_error: type[Exception] | Exception | None = None
        self._conditions: list[tuple[dict[str, Any], Any, type[Exception] | Exception | None]] = []
        self._sequence: list[Any] = []
        self._sequence_index = 0
        self._sequence_loop = False
        self._sequence_default: Any = _SENTINEL
        self._custom_handler: Callable[[dict[str, Any]], Any] | None = None
        self._calls: list[ToolCallRecord] = []
        self._building_condition: dict[str, Any] | None = None

    # --- Builder pattern ---

    def when(self, **kwargs: Any) -> ToolMock:
        """Set conditions for the next return value."""
        self._building_condition = kwargs
        return self

    def returns(self, value: Any) -> ToolMock:
        """Set the return value (for default or current condition)."""
        if self._building_condition is not None:
            self._conditions.append((self._building_condition, value, None))
            self._building_condition = None
        else:
            self._default_result = value
        return self

    def otherwise(self) -> ToolMock:
        """Set up the default/fallback return."""
        self._building_condition = None
        return self

    def returns_sequence(
        self,
        values: list[Any],
        *,
        loop: bool = False,
        default_after_exhaustion: Any = _SENTINEL,
    ) -> ToolMock:
        """Return values in sequence, one per call.

        Args:
            values: The sequence of return values.
            loop: If True, cycle through values indefinitely.
            default_after_exhaustion: Value to return after sequence is exhausted.
                If not set and loop is False, raises IndexError on exhaustion.
        """
        self._sequence = values
        self._sequence_loop = loop
        self._sequence_default = default_after_exhaustion
        return self

    def raises(self, error: type[Exception] | Exception) -> ToolMock:
        """Raise an error when called."""
        if self._building_condition is not None:
            self._conditions.append((self._building_condition, None, error))
            self._building_condition = None
        else:
            self._default_error = error
        return self

    def responds_with(self, handler: Callable[[dict[str, Any]], Any]) -> ToolMock:
        """Use a custom function to generate responses."""
        self._custom_handler = handler
        return self

    # --- Execution ---

    def __call__(self, **kwargs: Any) -> Any:
        """Execute the mock tool."""
        result = self._resolve(kwargs)
        self._calls.append(
            ToolCallRecord(
                name=self.name,
                arguments=kwargs,
                result=result,
                call_index=len(self._calls),
                global_index=next(_global_call_counter),
            )
        )
        return result

    def _resolve(self, arguments: dict[str, Any]) -> Any:
        """Resolve the return value for a call.

        Resolution order: custom handler > sequence > conditional match > default.
        """
        # Custom handler takes priority
        if self._custom_handler:
            return self._custom_handler(arguments)

        # Sequence mode
        if self._sequence:
            if self._sequence_index >= len(self._sequence):
                if self._sequence_loop:
                    self._sequence_index = 0
                elif self._sequence_default is not _SENTINEL:
                    return self._sequence_default
                else:
                    raise IndexError(
                        f"ToolMock {self.name!r}: exhausted sequence "
                        f"after {len(self._sequence)} calls"
                    )
            result = self._sequence[self._sequence_index]
            self._sequence_index += 1
            return result

        # Conditional matching
        for condition, value, error in self._conditions:
            if self._matches(arguments, condition):
                if error:
                    raise error if isinstance(error, Exception) else error()
                return value

        # Default
        if self._default_error:
            err = self._default_error
            raise err if isinstance(err, Exception) else err()

        return self._default_result

    @staticmethod
    def _matches(arguments: dict[str, Any], condition: dict[str, Any]) -> bool:
        """Check if arguments match condition (supports regex for strings)."""
        for key, expected in condition.items():
            actual = arguments.get(key)
            if isinstance(expected, str) and isinstance(actual, str):
                if not re.search(expected, actual):
                    return False
            elif actual != expected:
                return False
        return True

    # --- Assertions ---

    @property
    def call_count(self) -> int:
        """Return the number of times this mock was called."""
        return len(self._calls)

    @property
    def calls(self) -> list[ToolCallRecord]:
        """Return the list of all call records."""
        return self._calls

    @property
    def last_call(self) -> ToolCallRecord | None:
        """Return the most recent call record, or None if never called."""
        return self._calls[-1] if self._calls else None

    def was_called(self) -> bool:
        """Return True if the mock was called at least once."""
        return len(self._calls) > 0

    def was_called_with(self, **kwargs: Any) -> bool:
        """Return True if any call matched the given keyword arguments."""
        return any(
            all(call.arguments.get(k) == v for k, v in kwargs.items()) for call in self._calls
        )

    def assert_called(self) -> None:
        """Assert that the mock was called at least once."""
        assert self._calls, f"ToolMock {self.name!r} was never called"

    def assert_called_times(self, n: int) -> None:
        """Assert that the mock was called exactly n times."""
        assert len(self._calls) == n, (
            f"ToolMock {self.name!r} was called {len(self._calls)} times, expected {n}"
        )

    def assert_called_with(self, **kwargs: Any) -> None:
        """Assert that the mock was called with the given arguments at least once."""
        assert self.was_called_with(**kwargs), (
            f"ToolMock {self.name!r} was never called with {kwargs}. "
            f"Calls: {[c.arguments for c in self._calls]}"
        )

    def reset(self) -> None:
        """Reset call history."""
        self._calls.clear()
        self._sequence_index = 0


class MockToolkit:
    """A collection of tool mocks that acts as a tool registry.

    Usage:
        toolkit = MockToolkit()
        toolkit.mock("read_file").returns("contents")
        toolkit.mock("write_file").returns(True)
        toolkit.mock("search").when(query="python").returns(["result"])

        # Use as tool executor
        result = toolkit.execute("read_file", path="/tmp/test.txt")

        # Check assertions
        toolkit.assert_all_called()
    """

    def __init__(self, strict: bool = True) -> None:
        """Initialize an empty mock toolkit.

        Args:
            strict: If True (default), raises KeyError for unregistered tools.
                If False, auto-creates passthrough mocks for unregistered tools.
        """
        self._mocks: dict[str, ToolMock] = {}
        self._strict = strict

    def mock(self, name: str) -> ToolMock:
        """Get or create a mock for a tool."""
        if name not in self._mocks:
            self._mocks[name] = ToolMock(name)
        return self._mocks[name]

    def add(self, mock: ToolMock) -> None:
        """Add a pre-configured mock."""
        self._mocks[mock.name] = mock

    def execute(self, name: str, **kwargs: Any) -> Any:
        """Execute a mocked tool by name."""
        if name not in self._mocks:
            if self._strict:
                raise KeyError(
                    f"No mock registered for tool {name!r}. Available: {list(self._mocks.keys())}"
                )
            self._mocks[name] = ToolMock(name)
        return self._mocks[name](**kwargs)

    def has_mock(self, name: str) -> bool:
        """Return True if a mock is registered for the given tool name."""
        return name in self._mocks

    @property
    def all_calls(self) -> list[ToolCallRecord]:
        """All calls across all mocks, sorted by call index."""
        calls = []
        for mock in self._mocks.values():
            calls.extend(mock.calls)
        return sorted(calls, key=lambda c: c.global_index)

    def assert_all_called(self) -> None:
        """Assert that every registered mock was called at least once."""
        uncalled = [name for name, mock in self._mocks.items() if not mock.was_called()]
        assert not uncalled, f"The following tools were never called: {uncalled}"

    def assert_no_unexpected_calls(self, expected_tools: list[str]) -> None:
        """Assert that only expected tools were called."""
        called = {name for name, mock in self._mocks.items() if mock.was_called()}
        unexpected = called - set(expected_tools)
        assert not unexpected, f"Unexpected tools were called: {unexpected}"

    def reset_all(self) -> None:
        """Reset all mocks."""
        for mock in self._mocks.values():
            mock.reset()

    def summary(self) -> dict[str, int]:
        """Get call counts for all mocks."""
        return {name: mock.call_count for name, mock in self._mocks.items()}
