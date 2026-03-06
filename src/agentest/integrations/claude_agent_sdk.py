"""Claude Agent SDK integration for Agentest.

Provides native trace recording for applications built with the Claude Agent SDK.

Usage:
    from agentest.integrations.claude_agent_sdk import AgentestTracer

    tracer = AgentestTracer(task="My Claude agent")

    # Use as a wrapper around agent execution
    result, trace = tracer.record(agent.run, "What is 2+2?")

    # Or use the context manager
    with tracer.recording() as recorder:
        result = agent.run("What is 2+2?")
    trace = tracer.get_trace()

Requires: pip install claude-agent-sdk (or anthropic with agent support)
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from typing import Any

from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder


class AgentestTracer:
    """Tracer for Claude Agent SDK applications.

    Records agent interactions including LLM calls, tool use, and
    conversation turns into an AgentTrace for evaluation.

    Args:
        task: Description of the task.
        metadata: Optional metadata.
    """

    def __init__(self, task: str = "claude-agent", metadata: dict[str, Any] | None = None):
        self._task = task
        self._metadata = {"framework": "claude-agent-sdk", **(metadata or {})}
        self._recorder: Recorder | None = None
        self._trace: AgentTrace | None = None

    def _ensure_recorder(self) -> Recorder:
        if self._recorder is None:
            self._recorder = Recorder(task=self._task, metadata=self._metadata)
        return self._recorder

    def record(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, AgentTrace]:
        """Record a function call (typically agent.run) as an AgentTrace.

        Args:
            fn: The function to call (e.g., agent.run).
            *args: Positional arguments to pass.
            **kwargs: Keyword arguments to pass.

        Returns:
            Tuple of (function_result, AgentTrace).
        """
        recorder = self._ensure_recorder()

        # Record input if it looks like a message
        if args:
            recorder.record_message("user", str(args[0]))

        start = time.time()
        error_msg = None
        result = None

        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            duration_ms = (time.time() - start) * 1000

            if result is not None:
                self._extract_result(recorder, result, duration_ms)

            self._trace = recorder.finalize(success=error_msg is None, error=error_msg)
            self._recorder = None

        return result, self._trace

    async def record_async(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, AgentTrace]:
        """Record an async function call as an AgentTrace.

        Args:
            fn: The async function to call.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Tuple of (function_result, AgentTrace).
        """
        recorder = self._ensure_recorder()

        if args:
            recorder.record_message("user", str(args[0]))

        start = time.time()
        error_msg = None
        result = None

        try:
            result = await fn(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            duration_ms = (time.time() - start) * 1000

            if result is not None:
                self._extract_result(recorder, result, duration_ms)

            self._trace = recorder.finalize(success=error_msg is None, error=error_msg)
            self._recorder = None

        return result, self._trace

    def _extract_result(self, recorder: Recorder, result: Any, duration_ms: float) -> None:
        """Extract trace data from an agent result object."""
        # Handle string results
        if isinstance(result, str):
            recorder.record_llm_response(
                model="claude",
                content=result,
                input_tokens=0,
                output_tokens=0,
                latency_ms=duration_ms,
            )
            return

        # Handle structured results with messages/turns
        if hasattr(result, "messages"):
            for msg in result.messages:
                role = getattr(msg, "role", "assistant")
                content = getattr(msg, "content", str(msg))
                if isinstance(content, list):
                    for block in content:
                        if hasattr(block, "text"):
                            recorder.record_message(str(role), block.text)
                        elif hasattr(block, "type") and block.type == "tool_use":
                            recorder.record_tool_call(
                                name=block.name,
                                arguments=getattr(block, "input", {}),
                                result=None,
                            )
                        elif hasattr(block, "type") and block.type == "tool_result":
                            pass  # Already captured above
                elif isinstance(content, str):
                    recorder.record_message(str(role), content)

        # Handle usage info
        if hasattr(result, "usage"):
            usage = result.usage
            recorder.record_llm_response(
                model=getattr(result, "model", "claude"),
                content=str(result),
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
                latency_ms=duration_ms,
            )
        elif not hasattr(result, "messages"):
            recorder.record_llm_response(
                model="claude",
                content=str(result),
                input_tokens=0,
                output_tokens=0,
                latency_ms=duration_ms,
            )

        # Handle tool results
        if hasattr(result, "tool_results"):
            for tr in result.tool_results:
                recorder.record_tool_call(
                    name=getattr(tr, "name", "tool"),
                    arguments=getattr(tr, "arguments", {}),
                    result=getattr(tr, "result", None),
                    error=getattr(tr, "error", None),
                )

    @contextlib.contextmanager
    def recording(self):
        """Context manager for manual recording.

        Yields:
            The Recorder instance for manual interaction recording.

        Example:
            >>> with tracer.recording() as recorder:
            ...     recorder.record_message("user", "Hello")
            ...     result = agent.run("Hello")
            ...     recorder.record_llm_response(...)
            >>> trace = tracer.get_trace()
        """
        recorder = self._ensure_recorder()
        try:
            yield recorder
        except Exception as e:
            self._trace = recorder.finalize(success=False, error=str(e))
            self._recorder = None
            raise
        else:
            self._trace = recorder.finalize(success=True)
            self._recorder = None

    def get_trace(self) -> AgentTrace | None:
        """Get the last recorded trace.

        Returns:
            The most recent AgentTrace, or None if no recording has been done.
        """
        return self._trace

    def save(self, path: str, fmt: str = "yaml") -> None:
        """Save the last trace to a file."""
        if self._trace is None:
            raise RuntimeError("No trace to save. Call record() first.")
        recorder = Recorder(task=self._task)
        recorder._trace = self._trace
        recorder.save(path, format=fmt)
