"""Core data models for Agentest."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    """Roles that participants can have in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ToolCall(BaseModel):
    """A single tool/function call made by an agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: str | None = None
    duration_ms: float | None = None
    timestamp: float = Field(default_factory=time.time)

    @property
    def succeeded(self) -> bool:
        """Whether the tool call completed without error."""
        return self.error is None


# Default model pricing: (input_price_per_1M, output_price_per_1M)
DEFAULT_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o3": (2.0, 8.0),
    "o4-mini": (1.10, 4.40),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.15, 0.60),
}

# Mutable registry for user-added pricing
_custom_pricing: dict[str, tuple[float, float]] = {}


def set_model_pricing(model: str, input_price_per_1m: float, output_price_per_1m: float) -> None:
    """Register custom pricing for a model (per 1M tokens).

    Args:
        model: Model name or prefix to match (e.g. "my-model").
        input_price_per_1m: Cost per 1M input tokens in USD.
        output_price_per_1m: Cost per 1M output tokens in USD.

    Example:
        >>> set_model_pricing("my-fine-tune", 5.0, 15.0)
    """
    _custom_pricing[model] = (input_price_per_1m, output_price_per_1m)


def get_model_pricing() -> dict[str, tuple[float, float]]:
    """Get the full pricing table (defaults + custom overrides)."""
    return {**DEFAULT_MODEL_PRICING, **_custom_pricing}


class LLMResponse(BaseModel):
    """A response from an LLM provider."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model: str
    role: Role = Role.ASSISTANT
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0
    timestamp: float = Field(default_factory=time.time)
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def cost_estimate(self) -> float:
        """Cost estimate based on model pricing (per 1M tokens).

        Uses custom pricing (set via ``set_model_pricing``) first,
        then falls back to built-in defaults. Returns 0.0 for unknown models.
        """
        pricing = get_model_pricing()
        for model_prefix, (input_price, output_price) in pricing.items():
            if model_prefix in self.model:
                return (
                    self.input_tokens * input_price / 1_000_000
                    + self.output_tokens * output_price / 1_000_000
                )
        return 0.0


class Message(BaseModel):
    """A message in a conversation."""

    role: Role
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class AgentTrace(BaseModel):
    """A complete trace of an agent's execution on a task."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task: str = ""
    messages: list[Message] = Field(default_factory=list)
    llm_responses: list[LLMResponse] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    success: bool | None = None
    error: str | None = None

    @property
    def duration_ms(self) -> float | None:
        """Total execution time in milliseconds, or None if not yet finalized."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    @property
    def total_tokens(self) -> int:
        """Sum of tokens used across all LLM responses in this trace."""
        return sum(r.total_tokens for r in self.llm_responses)

    @property
    def total_cost(self) -> float:
        """Estimated total cost across all LLM responses."""
        return sum(r.cost_estimate for r in self.llm_responses)

    @property
    def total_tool_calls(self) -> int:
        """Number of tool calls made during this trace."""
        return len(self.tool_calls)

    @property
    def failed_tool_calls(self) -> list[ToolCall]:
        """Tool calls that completed with an error."""
        return [tc for tc in self.tool_calls if not tc.succeeded]

    def finalize(self, success: bool = True, error: str | None = None) -> None:
        """Mark the trace as complete, recording end time and outcome.

        Args:
            success: Whether the agent task succeeded.
            error: Optional error message if the task failed.
        """
        self.end_time = time.time()
        self.success = success
        self.error = error


class TraceSession(BaseModel):
    """A collection of traces, typically from a test run or benchmark."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    traces: list[AgentTrace] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)

    @property
    def total_traces(self) -> int:
        """Number of traces in this session."""
        return len(self.traces)

    @property
    def successful_traces(self) -> int:
        """Number of traces that completed successfully."""
        return sum(1 for t in self.traces if t.success is True)

    @property
    def success_rate(self) -> float:
        """Fraction of traces that succeeded (0.0 to 1.0)."""
        if not self.traces:
            return 0.0
        return self.successful_traces / self.total_traces


def diff_traces(trace_a: AgentTrace, trace_b: AgentTrace) -> dict[str, Any]:
    """Compare two traces and return a structured diff.

    Useful for debugging regressions between runs of the same task.

    Returns a dict with:
        - summary: high-level metric comparison
        - tool_calls: added/removed/changed tool calls
        - models: models used in each trace
    """
    # High-level metric comparison
    summary: dict[str, Any] = {
        "task": {"a": trace_a.task, "b": trace_b.task},
        "success": {"a": trace_a.success, "b": trace_b.success},
        "total_tokens": {
            "a": trace_a.total_tokens,
            "b": trace_b.total_tokens,
            "delta": trace_b.total_tokens - trace_a.total_tokens,
        },
        "total_cost": {
            "a": trace_a.total_cost,
            "b": trace_b.total_cost,
            "delta": trace_b.total_cost - trace_a.total_cost,
        },
        "tool_call_count": {
            "a": trace_a.total_tool_calls,
            "b": trace_b.total_tool_calls,
            "delta": trace_b.total_tool_calls - trace_a.total_tool_calls,
        },
        "llm_call_count": {
            "a": len(trace_a.llm_responses),
            "b": len(trace_b.llm_responses),
            "delta": len(trace_b.llm_responses) - len(trace_a.llm_responses),
        },
    }

    if trace_a.duration_ms is not None and trace_b.duration_ms is not None:
        summary["duration_ms"] = {
            "a": trace_a.duration_ms,
            "b": trace_b.duration_ms,
            "delta": trace_b.duration_ms - trace_a.duration_ms,
        }

    # Tool call comparison by name sequence
    tool_names_a = [tc.name for tc in trace_a.tool_calls]
    tool_names_b = [tc.name for tc in trace_b.tool_calls]

    added_tools = [name for name in tool_names_b if name not in set(tool_names_a)]
    removed_tools = [name for name in tool_names_a if name not in set(tool_names_b)]

    # Models used
    models_a = sorted({r.model for r in trace_a.llm_responses})
    models_b = sorted({r.model for r in trace_b.llm_responses})

    # Error comparison
    errors_a = [tc.error for tc in trace_a.tool_calls if tc.error]
    errors_b = [tc.error for tc in trace_b.tool_calls if tc.error]

    return {
        "summary": summary,
        "tool_calls": {
            "sequence_a": tool_names_a,
            "sequence_b": tool_names_b,
            "added": added_tools,
            "removed": removed_tools,
            "same_sequence": tool_names_a == tool_names_b,
        },
        "models": {"a": models_a, "b": models_b, "changed": models_a != models_b},
        "errors": {
            "a": errors_a,
            "b": errors_b,
            "new_errors": [e for e in errors_b if e not in errors_a],
            "resolved_errors": [e for e in errors_a if e not in errors_b],
        },
    }
