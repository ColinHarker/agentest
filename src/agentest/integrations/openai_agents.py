"""OpenAI Agents SDK integration for Agentest.

Provides trace recording for applications built with the OpenAI Agents SDK.

Usage:
    from agentest.integrations.openai_agents import AgentestTracer

    tracer = AgentestTracer(task="My OpenAI agent")
    result, trace = tracer.record(runner.run, agent, "What is 2+2?")

Requires: pip install openai (with agents support)
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Generator
from typing import Any

from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder


class AgentestTracer:
    """Tracer for OpenAI Agents SDK applications.

    Records agent interactions including LLM calls, tool use,
    handoffs, and guardrail checks into an AgentTrace.

    Args:
        task: Description of the task.
        metadata: Optional metadata.
    """

    def __init__(self, task: str = "openai-agent", metadata: dict[str, Any] | None = None):
        self._task = task
        self._metadata = {"framework": "openai-agents-sdk", **(metadata or {})}
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
        """Record a function call as an AgentTrace.

        Typically used to wrap Runner.run() or Runner.run_sync().

        Args:
            fn: The function to call.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Tuple of (result, AgentTrace).
        """
        recorder = self._ensure_recorder()

        # Try to extract the initial message
        if len(args) >= 2 and isinstance(args[1], str):
            recorder.record_message("user", args[1])
        elif "input" in kwargs:
            recorder.record_message("user", str(kwargs["input"]))

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
            Tuple of (result, AgentTrace).
        """
        recorder = self._ensure_recorder()

        if len(args) >= 2 and isinstance(args[1], str):
            recorder.record_message("user", args[1])
        elif "input" in kwargs:
            recorder.record_message("user", str(kwargs["input"]))

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
        """Extract trace data from an OpenAI Agents SDK result."""
        # Handle RunResult with new_items
        if hasattr(result, "new_items"):
            for item in result.new_items:
                item_type = type(item).__name__

                if "MessageOutput" in item_type:
                    agent_name = getattr(item, "agent", None)
                    agent_label = (
                        getattr(agent_name, "name", "assistant") if agent_name else "assistant"
                    )
                    content = getattr(item, "text", str(item))
                    recorder.record_message(str(agent_label), content)

                elif "ToolCallItem" in item_type or "ToolCall" in item_type:
                    name = getattr(item, "name", "tool")
                    arguments = getattr(item, "arguments", {})
                    output = getattr(item, "output", None)
                    recorder.record_tool_call(
                        name=name,
                        arguments=arguments if isinstance(arguments, dict) else {},
                        result=output,
                    )

                elif "HandoffItem" in item_type or "Handoff" in item_type:
                    source = getattr(item, "source_agent", None)
                    target = getattr(item, "target_agent", None)
                    source_name = getattr(source, "name", "source") if source else "source"
                    target_name = getattr(target, "name", "target") if target else "target"
                    recorder.record_tool_call(
                        name="handoff",
                        arguments={"from": source_name, "to": target_name},
                        result=f"Handoff from {source_name} to {target_name}",
                    )

        # Handle final_output
        if hasattr(result, "final_output"):
            output = result.final_output
            recorder.record_llm_response(
                model="openai-agent",
                content=str(output) if output else "",
                input_tokens=0,
                output_tokens=0,
                latency_ms=duration_ms,
            )

        # Handle usage from run result
        if hasattr(result, "raw_responses"):
            for resp in result.raw_responses:
                if hasattr(resp, "usage"):
                    usage = resp.usage
                    model = getattr(resp, "model", "openai")
                    recorder.record_llm_response(
                        model=model,
                        content="",
                        input_tokens=getattr(usage, "prompt_tokens", 0),
                        output_tokens=getattr(usage, "completion_tokens", 0),
                        latency_ms=0,
                    )

    @contextlib.contextmanager
    def recording(self) -> Generator[Recorder, None, None]:
        """Context manager for manual recording.

        Yields:
            The Recorder instance.
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
        """Get the last recorded trace."""
        return self._trace
