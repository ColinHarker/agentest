"""LlamaIndex integration for Agentest.

Provides a callback handler that records LlamaIndex query pipeline
executions as AgentTrace objects.

Usage:
    from agentest.integrations.llamaindex import AgentestHandler

    handler = AgentestHandler(task="RAG query")
    # Set as global handler or pass to query engine
    index.as_query_engine(callbacks=[handler])
    response = query_engine.query("What is Agentest?")
    trace = handler.get_trace()

Requires: pip install agentest[llamaindex]
"""

from __future__ import annotations

import time
from typing import Any

from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder

try:
    from llama_index.core.callbacks import CallbackManager, CBEventType, EventPayload
    from llama_index.core.callbacks.base_handler import BaseCallbackHandler
except ImportError:
    raise ImportError(
        "LlamaIndex integration requires llama-index-core. "
        "Install with: pip install agentest[llamaindex]"
    )


class AgentestHandler(BaseCallbackHandler):
    """LlamaIndex callback handler that records interactions into an AgentTrace.

    Captures LLM calls, retrieval events, and tool usage to build
    a complete AgentTrace for evaluation.

    Args:
        task: Description of the task being executed.
        metadata: Optional metadata to attach to the trace.
    """

    def __init__(
        self,
        task: str = "llamaindex-query",
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(
            event_starts_to_ignore=[],
            event_ends_to_ignore=[],
        )
        self._recorder = Recorder(task=task, metadata={"framework": "llamaindex", **(metadata or {})})
        self._event_starts: dict[str, float] = {}
        self._finalized = False

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Record the start of an event."""
        self._event_starts[event_id] = time.time()

        if payload:
            if event_type == CBEventType.LLM:
                # Record input messages
                messages = payload.get(EventPayload.MESSAGES, [])
                for msg in messages:
                    role = getattr(msg, "role", "user")
                    content = getattr(msg, "content", str(msg))
                    if isinstance(role, str) and isinstance(content, str):
                        self._recorder.record_message(role, content)

            elif event_type == CBEventType.QUERY:
                query_str = payload.get(EventPayload.QUERY_STR, "")
                if query_str:
                    self._recorder.record_message("user", query_str)

        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        """Record event completion."""
        start_time = self._event_starts.pop(event_id, time.time())
        duration_ms = (time.time() - start_time) * 1000

        if not payload:
            return

        if event_type == CBEventType.LLM:
            response = payload.get(EventPayload.RESPONSE, None)
            completion = payload.get(EventPayload.COMPLETION, "")

            content = ""
            model = "unknown"
            input_tokens = 0
            output_tokens = 0

            if response is not None:
                if hasattr(response, "message"):
                    content = getattr(response.message, "content", "") or ""
                elif hasattr(response, "text"):
                    content = response.text
                else:
                    content = str(response)

                # Extract token usage
                if hasattr(response, "raw"):
                    raw = response.raw
                    if hasattr(raw, "usage"):
                        usage = raw.usage
                        input_tokens = getattr(usage, "prompt_tokens", 0) or getattr(
                            usage, "input_tokens", 0
                        )
                        output_tokens = getattr(usage, "completion_tokens", 0) or getattr(
                            usage, "output_tokens", 0
                        )
                    if hasattr(raw, "model"):
                        model = raw.model
            elif completion:
                content = str(completion)

            self._recorder.record_llm_response(
                model=model,
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=duration_ms,
            )

        elif event_type == CBEventType.RETRIEVE:
            nodes = payload.get(EventPayload.NODES, [])
            self._recorder.record_tool_call(
                name="retrieve",
                arguments={},
                result=f"Retrieved {len(nodes)} nodes",
                duration_ms=duration_ms,
            )

        elif event_type == CBEventType.FUNCTION_CALL:
            tool_name = payload.get(EventPayload.TOOL, None)
            tool_output = payload.get("function_call_response", "")
            name = getattr(tool_name, "name", "function") if tool_name else "function"
            self._recorder.record_tool_call(
                name=name,
                arguments={},
                result=str(tool_output),
                duration_ms=duration_ms,
            )

    def start_trace(self, trace_id: str | None = None) -> None:
        """Called when a trace starts (LlamaIndex callback protocol)."""
        pass

    def end_trace(
        self,
        trace_id: str | None = None,
        trace_map: dict[str, list[str]] | None = None,
    ) -> None:
        """Called when a trace ends (LlamaIndex callback protocol)."""
        pass

    def get_trace(self, success: bool | None = None) -> AgentTrace:
        """Finalize and return the recorded AgentTrace.

        Args:
            success: Whether the task succeeded. If None, inferred from errors.

        Returns:
            The complete AgentTrace.
        """
        if self._finalized:
            return self._recorder.trace

        if success is None:
            success = len(self._recorder.trace.failed_tool_calls) == 0

        trace = self._recorder.finalize(success=success)
        self._finalized = True
        return trace

    def save(self, path: str, fmt: str = "yaml") -> None:
        """Save the trace to a file."""
        if not self._finalized:
            self.get_trace()
        self._recorder.save(path, format=fmt)
