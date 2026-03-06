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

import threading
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
_exporter: Any | None = None


def _get_recorder(task: str = "auto-instrumented") -> Recorder:
    """Get the current thread's recorder, creating one if needed."""
    if not hasattr(_local, "recorder") or _local.recorder is None:
        _local.recorder = Recorder(task=task)
    recorder: Recorder = _local.recorder
    return recorder


def _finalize_and_store(success: bool = True, error: str | None = None) -> AgentTrace:
    """Finalize current recorder and store the trace."""
    recorder = _get_recorder()
    recorder._suppress_empty_warning = True
    trace = recorder.finalize(success=success, error=error)
    with _lock:
        _global_traces.append(trace)
    if _exporter is not None:
        _exporter.export(trace)
    _local.recorder = None
    return trace


def set_exporter(exporter: Any) -> None:
    """Set a trace exporter for auto-instrumented traces.

    When set, every finalized trace is automatically exported.
    Typically used with ``OTelExporter`` for OpenTelemetry integration.

    Args:
        exporter: An object with an ``export(trace)`` method (e.g., OTelExporter).

    Example:
        >>> from agentest.integrations.otel import OTelExporter
        >>> agentest.instrument()
        >>> agentest.set_exporter(OTelExporter())
    """
    global _exporter
    _exporter = exporter


def clear_exporter() -> None:
    """Remove the current trace exporter."""
    global _exporter
    _exporter = None


def is_instrumented() -> bool:
    """Return whether auto-instrumentation is currently active."""
    return _instrumented


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

            from agentest.integrations._anthropic_patch import (
                _wrap_anthropic_create,
                _wrap_anthropic_create_async,
            )

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

            from agentest.integrations._openai_patch import (
                _wrap_openai_create,
                _wrap_openai_create_async,
            )

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
