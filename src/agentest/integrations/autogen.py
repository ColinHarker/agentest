"""AutoGen integration for Agentest.

Provides a wrapper that records AutoGen agent conversations as AgentTrace objects.

Usage:
    from agentest.integrations.autogen import record_autogen_chat

    result, trace = record_autogen_chat(
        initiator=user_proxy,
        recipient=assistant,
        message="Write a hello world program",
    )

Requires: pip install agentest[autogen]
"""

from __future__ import annotations

import time
from typing import Any

from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder


def record_autogen_chat(
    initiator: Any,
    recipient: Any,
    message: str,
    task: str | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> tuple[Any, AgentTrace]:
    """Record an AutoGen chat conversation as an AgentTrace.

    Args:
        initiator: The AutoGen agent that starts the conversation.
        recipient: The AutoGen agent that receives the message.
        message: The initial message to send.
        task: Task description. Defaults to the message content.
        metadata: Optional metadata.
        **kwargs: Additional arguments passed to initiate_chat.

    Returns:
        Tuple of (chat_result, AgentTrace).

    Example:
        >>> result, trace = record_autogen_chat(
        ...     initiator=user_proxy,
        ...     recipient=assistant,
        ...     message="Write hello world in Python",
        ... )
    """
    task_desc = task or message[:100]
    meta = {"framework": "autogen", **(metadata or {})}

    recorder = Recorder(task=task_desc, metadata=meta)
    recorder.record_message("user", message)

    # Record agent info
    initiator_name = getattr(initiator, "name", type(initiator).__name__)
    recipient_name = getattr(recipient, "name", type(recipient).__name__)
    recorder.record_message(
        "system",
        f"AutoGen chat: {initiator_name} -> {recipient_name}",
    )

    start = time.time()
    error_msg = None
    result = None

    try:
        result = initiator.initiate_chat(recipient, message=message, **kwargs)
    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration_ms = (time.time() - start) * 1000

        # Extract chat history
        chat_history = []
        if result is not None and hasattr(result, "chat_history"):
            chat_history = result.chat_history
        elif hasattr(recipient, "chat_messages"):
            msgs = recipient.chat_messages.get(initiator, [])
            chat_history = msgs

        for msg in chat_history:
            if isinstance(msg, dict):
                role = msg.get("role", "assistant")
                content = msg.get("content", "")
                if content:
                    recorder.record_message(role, str(content))

                # Check for function/tool calls
                if "function_call" in msg:
                    fc = msg["function_call"]
                    recorder.record_tool_call(
                        name=fc.get("name", "function"),
                        arguments=fc.get("arguments", {}),
                        result=None,
                    )
                if "tool_calls" in msg:
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        recorder.record_tool_call(
                            name=fn.get("name", "tool"),
                            arguments=fn.get("arguments", {}),
                            result=None,
                        )

        # Record summary as LLM response
        summary = ""
        if result is not None:
            summary = getattr(result, "summary", str(result))

        if summary:
            recorder.record_llm_response(
                model="autogen",
                content=str(summary),
                input_tokens=0,
                output_tokens=0,
                latency_ms=duration_ms,
            )

        trace = recorder.finalize(success=error_msg is None, error=error_msg)

    return result, trace


class AutoGenAdapter:
    """Persistent adapter for recording multiple AutoGen conversations.

    Args:
        default_metadata: Default metadata to attach to all traces.
    """

    def __init__(self, default_metadata: dict[str, Any] | None = None):
        self._metadata = default_metadata or {}
        self._traces: list[AgentTrace] = []

    def record_chat(
        self,
        initiator: Any,
        recipient: Any,
        message: str,
        task: str | None = None,
        **kwargs: Any,
    ) -> tuple[Any, AgentTrace]:
        """Record a chat conversation.

        Returns:
            Tuple of (chat_result, AgentTrace).
        """
        result, trace = record_autogen_chat(
            initiator=initiator,
            recipient=recipient,
            message=message,
            task=task,
            metadata=self._metadata,
            **kwargs,
        )
        self._traces.append(trace)
        return result, trace

    @property
    def traces(self) -> list[AgentTrace]:
        """All recorded traces."""
        return list(self._traces)

    def clear(self) -> None:
        """Clear all recorded traces."""
        self._traces.clear()
