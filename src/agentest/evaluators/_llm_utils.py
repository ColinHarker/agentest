"""Shared utilities for LLM-based evaluators."""

from __future__ import annotations

import json as _json
from typing import Any


def call_judge_llm(client: Any, model: str, prompt: str) -> str:
    """Send a judge prompt to an LLM client (Anthropic or OpenAI).

    Args:
        client: An Anthropic or OpenAI client instance.
        model: The model name to use.
        prompt: The prompt to send.

    Returns:
        The response text from the LLM.

    Raises:
        TypeError: If the client type is not recognized.
    """
    if hasattr(client, "messages"):
        # Anthropic
        response = client.messages.create(
            model=model,
            max_tokens=200,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        result: str = response.content[0].text
        return result
    elif hasattr(client, "chat"):
        # OpenAI — use JSON response format for structured output
        response = client.chat.completions.create(
            model=model,
            max_tokens=200,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
    else:
        raise TypeError(f"Unsupported client type: {type(client)}")


def parse_judge_response(response: str) -> tuple[float, str]:
    """Parse score and reasoning from an LLM judge response.

    Tries JSON first, falls back to line-based parsing for backward compat.

    Args:
        response: Raw text response from the LLM.

    Returns:
        Tuple of (score between 0.0-1.0, reasoning string).
    """
    # Try JSON first
    text = response.strip()
    try:
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = _json.loads(text)
        score = max(0.0, min(1.0, float(data.get("score", 0.5))))
        reasoning = str(data.get("reasoning", ""))
        return score, reasoning
    except (_json.JSONDecodeError, ValueError, KeyError, TypeError):
        pass

    # Fall back to line-based parsing
    score = 0.5
    reasoning = response.strip()

    for line in response.strip().split("\n"):
        if line.startswith("SCORE:"):
            try:
                score = float(line.split(":", 1)[1].strip())
                score = max(0.0, min(1.0, score))
            except ValueError:
                pass
        elif line.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    return score, reasoning
