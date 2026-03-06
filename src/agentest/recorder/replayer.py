"""Replay recorded agent sessions for deterministic testing."""

from __future__ import annotations

from typing import Any

from agentest.core import AgentTrace, LLMResponse, ToolCall


class ReplayMismatchError(Exception):
    """Raised when a replay diverges from the recorded session."""

    def __init__(self, expected: str, actual: str, step: int):
        self.expected = expected
        self.actual = actual
        self.step = step
        super().__init__(f"Replay mismatch at step {step}: expected {expected!r}, got {actual!r}")


class Replayer:
    """Replays a recorded trace, providing deterministic LLM and tool responses.

    Usage:
        trace = Recorder.load("traces/my_trace.yaml")
        replayer = Replayer(trace)

        # Get the next LLM response (returns the recorded response)
        response = replayer.next_llm_response()

        # Get the next tool result (returns the recorded result)
        result = replayer.next_tool_result("read_file", {"path": "doc.txt"})

        # Check if replay is complete
        assert replayer.is_complete
    """

    def __init__(self, trace: AgentTrace, strict: bool = True) -> None:
        """Initialize replayer with a recorded trace.

        Args:
            trace: The recorded trace to replay.
            strict: If True, raise errors on mismatches. If False, log warnings.
        """
        self.trace = trace
        self.strict = strict
        self._llm_index = 0
        self._tool_index = 0
        self._mismatches: list[ReplayMismatchError] = []

    @property
    def is_complete(self) -> bool:
        """Whether all recorded interactions have been replayed."""
        return self._llm_index >= len(self.trace.llm_responses) and self._tool_index >= len(
            self.trace.tool_calls
        )

    @property
    def mismatches(self) -> list[ReplayMismatchError]:
        """List of mismatches encountered during replay."""
        return self._mismatches

    @property
    def remaining_llm_responses(self) -> int:
        return len(self.trace.llm_responses) - self._llm_index

    @property
    def remaining_tool_calls(self) -> int:
        return len(self.trace.tool_calls) - self._tool_index

    def next_llm_response(self, model: str | None = None) -> LLMResponse:
        """Get the next recorded LLM response.

        Args:
            model: Expected model name. If provided and strict, verifies it matches.

        Returns:
            The recorded LLM response.

        Raises:
            IndexError: If no more recorded responses.
            ReplayMismatchError: If model doesn't match (strict mode).
        """
        if self._llm_index >= len(self.trace.llm_responses):
            raise IndexError(
                f"No more recorded LLM responses "
                f"(replayed {self._llm_index}/{len(self.trace.llm_responses)})"
            )

        response = self.trace.llm_responses[self._llm_index]

        if model and model != response.model:
            error = ReplayMismatchError(expected=response.model, actual=model, step=self._llm_index)
            self._mismatches.append(error)
            if self.strict:
                raise error

        self._llm_index += 1
        return response

    def next_tool_result(
        self,
        name: str | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> ToolCall:
        """Get the next recorded tool call result.

        Args:
            name: Expected tool name. If provided and strict, verifies it matches.
            arguments: Expected arguments. If provided, verifies they match.

        Returns:
            The recorded tool call with its result.

        Raises:
            IndexError: If no more recorded tool calls.
            ReplayMismatchError: If tool name or arguments don't match (strict mode).
        """
        if self._tool_index >= len(self.trace.tool_calls):
            raise IndexError(
                f"No more recorded tool calls "
                f"(replayed {self._tool_index}/{len(self.trace.tool_calls)})"
            )

        tool_call = self.trace.tool_calls[self._tool_index]

        if name and name != tool_call.name:
            error = ReplayMismatchError(expected=tool_call.name, actual=name, step=self._tool_index)
            self._mismatches.append(error)
            if self.strict:
                raise error

        if arguments and arguments != tool_call.arguments:
            error = ReplayMismatchError(
                expected=str(tool_call.arguments),
                actual=str(arguments),
                step=self._tool_index,
            )
            self._mismatches.append(error)
            if self.strict:
                raise error

        self._tool_index += 1
        return tool_call

    def create_tool_mock(self) -> dict[str, Any]:
        """Create a dict of tool name -> mock function using recorded results.

        Returns a dictionary where each key is a tool name and each value is a
        callable that returns the recorded result for that tool.
        """
        tool_results: dict[str, list[ToolCall]] = {}
        for tc in self.trace.tool_calls:
            tool_results.setdefault(tc.name, []).append(tc)

        counters: dict[str, int] = {}
        mocks: dict[str, Any] = {}

        for tool_name, calls in tool_results.items():
            counters[tool_name] = 0

            def make_mock(name: str, recorded_calls: list[ToolCall]) -> Any:
                def mock_fn(**kwargs: Any) -> Any:
                    idx = counters[name]
                    if idx >= len(recorded_calls):
                        raise IndexError(f"No more recorded results for tool {name!r}")
                    call = recorded_calls[idx]
                    counters[name] = idx + 1
                    if call.error:
                        raise RuntimeError(call.error)
                    return call.result

                return mock_fn

            mocks[tool_name] = make_mock(tool_name, calls)

        return mocks

    def reset(self) -> None:
        """Reset replay to the beginning."""
        self._llm_index = 0
        self._tool_index = 0
        self._mismatches.clear()
