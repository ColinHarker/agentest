"""LangChain integration for Agentest.

Provides a callback handler that automatically converts LangChain
chain/agent runs into AgentTrace objects.

Usage:
    from agentest.integrations.langchain import AgentestCallbackHandler

    handler = AgentestCallbackHandler(task="My LangChain agent")
    result = chain.invoke({"input": "Hello"}, config={"callbacks": [handler]})
    trace = handler.get_trace()

Requires: pip install agentest[langchain]
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:
    raise ImportError(
        "LangChain integration requires langchain-core. "
        "Install with: pip install agentest[langchain]"
    )


class AgentestCallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    """LangChain callback handler that records interactions into an AgentTrace.

    Captures LLM calls, tool invocations, chain starts/ends, and errors
    to build a complete AgentTrace for evaluation.

    Args:
        task: Description of the task being executed.
        metadata: Optional metadata to attach to the trace.
    """

    def __init__(self, task: str = "langchain-agent", metadata: dict[str, Any] | None = None):
        super().__init__()
        self._recorder = Recorder(task=task, metadata=metadata or {})
        self._llm_starts: dict[UUID, float] = {}
        self._tool_starts: dict[UUID, float] = {}
        self._finalized = False

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record when a chat model starts."""
        self._llm_starts[run_id] = time.time()
        # Record input messages
        for message_list in messages:
            for msg in message_list:
                role = getattr(msg, "type", "user")
                content = getattr(msg, "content", str(msg))
                if isinstance(content, str):
                    self._recorder.record_message(role, content)

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record when an LLM starts (non-chat models)."""
        self._llm_starts[run_id] = time.time()
        for prompt in prompts:
            self._recorder.record_message("user", prompt)

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        """Record LLM response when it completes."""
        start_time = self._llm_starts.pop(run_id, time.time())
        latency_ms = (time.time() - start_time) * 1000

        # Extract model info
        model = "unknown"
        if hasattr(response, "llm_output") and response.llm_output:
            model = response.llm_output.get("model_name", "unknown")

        # Extract generation text
        content = ""
        input_tokens = 0
        output_tokens = 0

        if hasattr(response, "generations") and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    content += getattr(gen, "text", "")
                    if hasattr(gen, "generation_info") and gen.generation_info:
                        info = gen.generation_info
                        input_tokens += info.get("input_tokens", 0)
                        output_tokens += info.get("output_tokens", 0)

        # Try token usage from llm_output
        if hasattr(response, "llm_output") and response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            if usage:
                input_tokens = input_tokens or usage.get("prompt_tokens", 0)
                output_tokens = output_tokens or usage.get("completion_tokens", 0)

        self._recorder.record_llm_response(
            model=model,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        """Record LLM errors."""
        start_time = self._llm_starts.pop(run_id, time.time())
        latency_ms = (time.time() - start_time) * 1000
        self._recorder.record_llm_response(
            model="unknown",
            content=f"Error: {error}",
            input_tokens=0,
            output_tokens=0,
            latency_ms=latency_ms,
        )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record when a tool starts executing."""
        self._tool_starts[run_id] = time.time()

    def on_tool_end(self, output: str, *, run_id: UUID, **kwargs: Any) -> None:
        """Record tool completion."""
        start_time = self._tool_starts.pop(run_id, time.time())
        duration_ms = (time.time() - start_time) * 1000

        # Try to get tool name from kwargs
        name = kwargs.get("name", "tool")
        tags = kwargs.get("tags", [])
        if tags and not name:
            name = tags[0]

        self._recorder.record_tool_call(
            name=name,
            arguments={},
            result=output,
            duration_ms=duration_ms,
        )

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        """Record tool errors."""
        start_time = self._tool_starts.pop(run_id, time.time())
        duration_ms = (time.time() - start_time) * 1000
        name = kwargs.get("name", "tool")
        self._recorder.record_tool_call(
            name=name,
            arguments={},
            result=None,
            error=str(error),
            duration_ms=duration_ms,
        )

    def get_trace(self, success: bool | None = None) -> AgentTrace:
        """Finalize and return the recorded AgentTrace.

        Args:
            success: Whether the overall task succeeded. If None, inferred
                from whether any errors occurred.

        Returns:
            The complete AgentTrace with all recorded interactions.
        """
        if self._finalized:
            return self._recorder.trace

        if success is None:
            # Infer from whether there are failed tool calls
            success = len(self._recorder.trace.failed_tool_calls) == 0

        trace = self._recorder.finalize(success=success)
        self._finalized = True
        return trace

    def save(self, path: str, fmt: str = "yaml") -> None:
        """Save the trace to a file.

        Args:
            path: File path to save to.
            fmt: Format - "yaml" or "json".
        """
        if not self._finalized:
            self.get_trace()
        self._recorder.save(path, format=fmt)
