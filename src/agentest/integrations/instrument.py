"""Auto-instrumentation for anthropic and openai clients.

Usage:
    import agentest
    agentest.instrument()  # Patches anthropic and openai clients globally

    # All subsequent API calls are automatically recorded
    client = anthropic.Anthropic()
    response = client.messages.create(...)  # Recorded!

    traces = agentest.get_traces()  # Get all recorded traces
    agentest.uninstrument()  # Remove patches
"""

from __future__ import annotations

import functools
import threading
import time
from typing import Any

from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder

# Thread-local storage for per-thread recorders
_local = threading.local()

# Global state
_instrumented = False
_original_anthropic_create: Any = None
_original_anthropic_create_async: Any = None
_original_openai_create: Any = None
_original_openai_create_async: Any = None
_global_traces: list[AgentTrace] = []
_lock = threading.Lock()


def _get_recorder(task: str = "auto-instrumented") -> Recorder:
    """Get the current thread's recorder, creating one if needed."""
    if not hasattr(_local, "recorder") or _local.recorder is None:
        _local.recorder = Recorder(task=task)
    recorder: Recorder = _local.recorder
    return recorder


def _finalize_and_store(success: bool = True, error: str | None = None) -> AgentTrace:
    """Finalize current recorder and store the trace."""
    recorder = _get_recorder()
    trace = recorder.finalize(success=success, error=error)
    with _lock:
        _global_traces.append(trace)
    _local.recorder = None
    return trace


def get_current_recorder() -> Recorder:
    """Get the current thread's active recorder.

    Returns:
        The active Recorder for the current thread.
    """
    return _get_recorder()


def get_traces() -> list[AgentTrace]:
    """Get all recorded traces from instrumentation.

    Returns:
        List of all AgentTrace objects recorded since instrument() was called.
    """
    with _lock:
        return list(_global_traces)


def clear_traces() -> None:
    """Clear all recorded traces."""
    with _lock:
        _global_traces.clear()


def flush_trace(task: str | None = None) -> AgentTrace | None:
    """Finalize the current thread's trace and start a new one.

    Args:
        task: Optional task name for the new recorder.

    Returns:
        The finalized AgentTrace, or None if no recorder was active.
    """
    if not hasattr(_local, "recorder") or _local.recorder is None:
        return None
    trace = _finalize_and_store(success=True)
    if task:
        _local.recorder = Recorder(task=task)
    return trace


def _wrap_anthropic_create(original: Any) -> Any:
    """Wrap anthropic.messages.create to auto-record."""

    @functools.wraps(original)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        recorder = _get_recorder()
        model = kwargs.get("model", "unknown")

        # Record user messages and extract tool results
        messages = kwargs.get("messages", [])
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                # Handle content blocks — extract tool results and text
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            tool_use_id = block.get("tool_use_id")
                            result_content = block.get("content", "")
                            if tool_use_id:
                                recorder.record_tool_result(tool_use_id, result_content)
                        elif "text" in block:
                            text_parts.append(block["text"])
                content = " ".join(text_parts)
            recorder.record_message(role, content)

        start = time.time()
        try:
            response = original(*args, **kwargs)
        except Exception as e:
            recorder.record_llm_response(
                model=model,
                content=f"Error: {e}",
                input_tokens=0,
                output_tokens=0,
                latency_ms=(time.time() - start) * 1000,
            )
            raise

        latency_ms = (time.time() - start) * 1000

        # Extract response data
        content_text = ""
        tool_calls_in_response = []

        if hasattr(response, "content"):
            for block in response.content:
                if hasattr(block, "text"):
                    content_text += block.text
                elif hasattr(block, "type") and block.type == "tool_use":
                    tool_calls_in_response.append(
                        {
                            "name": block.name,
                            "arguments": block.input if hasattr(block, "input") else {},
                            "id": block.id if hasattr(block, "id") else None,
                        }
                    )

        input_tokens = (
            getattr(response.usage, "input_tokens", 0) if hasattr(response, "usage") else 0
        )
        output_tokens = (
            getattr(response.usage, "output_tokens", 0) if hasattr(response, "usage") else 0
        )

        recorder.record_llm_response(
            model=model,
            content=content_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

        # Record tool use blocks as tool calls and track IDs for result correlation
        for tc in tool_calls_in_response:
            recorder.record_tool_call(
                name=tc["name"],
                arguments=tc["arguments"],
                result=None,
            )
            if tc.get("id"):
                recorder._pending_tool_calls[tc["id"]] = len(recorder.trace.tool_calls) - 1

        return response

    return wrapper


def _wrap_anthropic_create_async(original: Any) -> Any:
    """Wrap anthropic async messages.create to auto-record."""

    @functools.wraps(original)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        recorder = _get_recorder()
        model = kwargs.get("model", "unknown")

        messages = kwargs.get("messages", [])
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            tool_use_id = block.get("tool_use_id")
                            result_content = block.get("content", "")
                            if tool_use_id:
                                recorder.record_tool_result(tool_use_id, result_content)
                        elif "text" in block:
                            text_parts.append(block["text"])
                content = " ".join(text_parts)
            recorder.record_message(role, content)

        start = time.time()
        try:
            response = await original(*args, **kwargs)
        except Exception as e:
            recorder.record_llm_response(
                model=model,
                content=f"Error: {e}",
                input_tokens=0,
                output_tokens=0,
                latency_ms=(time.time() - start) * 1000,
            )
            raise

        latency_ms = (time.time() - start) * 1000
        content_text = ""
        tool_calls_in_response = []

        if hasattr(response, "content"):
            for block in response.content:
                if hasattr(block, "text"):
                    content_text += block.text
                elif hasattr(block, "type") and block.type == "tool_use":
                    tool_calls_in_response.append(
                        {
                            "name": block.name,
                            "arguments": block.input if hasattr(block, "input") else {},
                            "id": block.id if hasattr(block, "id") else None,
                        }
                    )

        input_tokens = (
            getattr(response.usage, "input_tokens", 0) if hasattr(response, "usage") else 0
        )
        output_tokens = (
            getattr(response.usage, "output_tokens", 0) if hasattr(response, "usage") else 0
        )

        recorder.record_llm_response(
            model=model,
            content=content_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

        for tc in tool_calls_in_response:
            recorder.record_tool_call(name=tc["name"], arguments=tc["arguments"], result=None)
            if tc.get("id"):
                recorder._pending_tool_calls[tc["id"]] = len(recorder.trace.tool_calls) - 1

        return response

    return wrapper


def _wrap_openai_create(original: Any) -> Any:
    """Wrap openai.chat.completions.create to auto-record."""

    @functools.wraps(original)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        recorder = _get_recorder()
        model = kwargs.get("model", "unknown")

        messages = kwargs.get("messages", [])
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "") or ""
            # Correlate OpenAI tool results (role: "tool" with tool_call_id)
            if role == "tool" and msg.get("tool_call_id"):
                recorder.record_tool_result(msg["tool_call_id"], content)
            recorder.record_message(role, content)

        start = time.time()
        try:
            response = original(*args, **kwargs)
        except Exception as e:
            recorder.record_llm_response(
                model=model,
                content=f"Error: {e}",
                input_tokens=0,
                output_tokens=0,
                latency_ms=(time.time() - start) * 1000,
            )
            raise

        latency_ms = (time.time() - start) * 1000

        # Extract response
        choice = response.choices[0] if hasattr(response, "choices") and response.choices else None
        content_text = ""
        if choice and hasattr(choice, "message"):
            content_text = choice.message.content or ""

            # Record tool calls from response
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    import json as _json

                    try:
                        args_dict = (
                            _json.loads(tc.function.arguments) if tc.function.arguments else {}
                        )
                    except (ValueError, AttributeError):
                        args_dict = {}
                    recorder.record_tool_call(
                        name=tc.function.name,
                        arguments=args_dict,
                        result=None,
                    )
                    tc_id = getattr(tc, "id", None)
                    if tc_id:
                        recorder._pending_tool_calls[tc_id] = len(recorder.trace.tool_calls) - 1

        usage = response.usage if hasattr(response, "usage") else None
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

        recorder.record_llm_response(
            model=model,
            content=content_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

        return response

    return wrapper


def _wrap_openai_create_async(original: Any) -> Any:
    """Wrap openai async chat.completions.create to auto-record."""

    @functools.wraps(original)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        recorder = _get_recorder()
        model = kwargs.get("model", "unknown")

        messages = kwargs.get("messages", [])
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "") or ""
            if role == "tool" and msg.get("tool_call_id"):
                recorder.record_tool_result(msg["tool_call_id"], content)
            recorder.record_message(role, content)

        start = time.time()
        try:
            response = await original(*args, **kwargs)
        except Exception as e:
            recorder.record_llm_response(
                model=model,
                content=f"Error: {e}",
                input_tokens=0,
                output_tokens=0,
                latency_ms=(time.time() - start) * 1000,
            )
            raise

        latency_ms = (time.time() - start) * 1000
        choice = response.choices[0] if hasattr(response, "choices") and response.choices else None
        content_text = ""
        if choice and hasattr(choice, "message"):
            content_text = choice.message.content or ""
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    import json as _json

                    try:
                        args_dict = (
                            _json.loads(tc.function.arguments) if tc.function.arguments else {}
                        )
                    except (ValueError, AttributeError):
                        args_dict = {}
                    recorder.record_tool_call(
                        name=tc.function.name, arguments=args_dict, result=None
                    )
                    tc_id = getattr(tc, "id", None)
                    if tc_id:
                        recorder._pending_tool_calls[tc_id] = len(recorder.trace.tool_calls) - 1

        usage = response.usage if hasattr(response, "usage") else None
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

        recorder.record_llm_response(
            model=model,
            content=content_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

        return response

    return wrapper


def instrument(
    anthropic: bool = True,
    openai: bool = True,
) -> None:
    """Auto-instrument anthropic and/or openai clients to record traces.

    Monkey-patches the create methods on anthropic.Anthropic().messages and
    openai.OpenAI().chat.completions so that every API call is automatically
    recorded into an AgentTrace.

    Args:
        anthropic: Whether to instrument the anthropic SDK.
        openai: Whether to instrument the openai SDK.

    Example:
        >>> import agentest
        >>> agentest.instrument()
        >>> # Now all anthropic/openai calls are recorded
        >>> client = anthropic.Anthropic()
        >>> response = client.messages.create(model="claude-sonnet-4-6", ...)
        >>> traces = agentest.get_traces()
    """
    global _instrumented, _original_anthropic_create, _original_anthropic_create_async
    global _original_openai_create, _original_openai_create_async

    if _instrumented:
        return

    if anthropic:
        try:
            import anthropic as anthropic_mod

            # Patch sync client
            messages_cls = anthropic_mod.resources.messages.Messages
            _original_anthropic_create = messages_cls.create
            messages_cls.create = _wrap_anthropic_create(_original_anthropic_create)

            # Patch async client
            async_messages_cls = anthropic_mod.resources.messages.AsyncMessages
            _original_anthropic_create_async = async_messages_cls.create
            async_messages_cls.create = _wrap_anthropic_create_async(
                _original_anthropic_create_async
            )
        except (ImportError, AttributeError):
            pass  # anthropic not installed or API changed

    if openai:
        try:
            import openai as openai_mod

            # Patch sync client
            completions_cls = openai_mod.resources.chat.completions.Completions
            _original_openai_create = completions_cls.create
            completions_cls.create = _wrap_openai_create(_original_openai_create)

            # Patch async client
            async_completions_cls = openai_mod.resources.chat.completions.AsyncCompletions
            _original_openai_create_async = async_completions_cls.create
            async_completions_cls.create = _wrap_openai_create_async(_original_openai_create_async)
        except (ImportError, AttributeError):
            pass  # openai not installed or API changed

    _instrumented = True


def uninstrument() -> None:
    """Remove all monkey-patches and finalize any active recorders.

    Restores the original create methods on anthropic and openai clients.
    Any in-progress recording is finalized and stored.
    """
    global _instrumented, _original_anthropic_create, _original_anthropic_create_async
    global _original_openai_create, _original_openai_create_async

    if not _instrumented:
        return

    # Finalize any active recorder
    if hasattr(_local, "recorder") and _local.recorder is not None:
        _finalize_and_store(success=True)

    # Restore anthropic
    if _original_anthropic_create is not None:
        try:
            import anthropic as anthropic_mod

            anthropic_mod.resources.messages.Messages.create = _original_anthropic_create
            _original_anthropic_create = None
        except ImportError:
            pass

    if _original_anthropic_create_async is not None:
        try:
            import anthropic as anthropic_mod

            anthropic_mod.resources.messages.AsyncMessages.create = _original_anthropic_create_async
            _original_anthropic_create_async = None
        except ImportError:
            pass

    # Restore openai
    if _original_openai_create is not None:
        try:
            import openai as openai_mod

            openai_mod.resources.chat.completions.Completions.create = _original_openai_create
            _original_openai_create = None
        except ImportError:
            pass

    if _original_openai_create_async is not None:
        try:
            import openai as openai_mod

            openai_mod.resources.chat.completions.AsyncCompletions.create = (
                _original_openai_create_async
            )
            _original_openai_create_async = None
        except ImportError:
            pass

    _instrumented = False
