"""Anthropic auto-instrumentation wrappers."""

from __future__ import annotations

import functools
import time
from typing import Any

from agentest.integrations.instrument import _get_recorder


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
