"""OpenAI auto-instrumentation wrappers."""

from __future__ import annotations

import functools
import time
from typing import Any

from agentest.integrations.instrument import _get_recorder


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
