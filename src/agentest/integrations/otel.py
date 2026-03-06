"""OpenTelemetry export integration for Agentest.

Converts AgentTrace objects into OpenTelemetry spans and exports them
to any OTel-compatible backend (Datadog, Grafana Tempo, Honeycomb, Jaeger, etc.).

Usage:
    from agentest.integrations.otel import OTelExporter
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    exporter = OTelExporter(tracer_provider=provider)
    exporter.export(trace)

Install with: pip install agentest[otel]
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import agentest
from agentest.core import AgentTrace, LLMResponse, ToolCall

if TYPE_CHECKING:
    from agentest.evaluators.base import EvalResult

# Lazy check for opentelemetry availability
_otel_available = False
try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode

    _otel_available = True
except ImportError:
    pass


def _require_otel() -> None:
    """Raise ImportError if opentelemetry is not installed."""
    if not _otel_available:
        raise ImportError(
            "OpenTelemetry packages are required for OTel export. "
            "Install with: pip install agentest[otel]"
        )


def _ns(timestamp: float) -> int:
    """Convert seconds (float) to nanoseconds (int) for OTel."""
    return int(timestamp * 1_000_000_000)


def _infer_system(model: str) -> str:
    """Infer the gen_ai.system value from a model name."""
    model_lower = model.lower()
    if "claude" in model_lower:
        return "anthropic"
    if "gpt" in model_lower or "o3" in model_lower or "o4" in model_lower:
        return "openai"
    if "gemini" in model_lower:
        return "google"
    return "unknown"


class OTelExporter:
    """Export AgentTrace objects as OpenTelemetry spans.

    Each AgentTrace becomes a root span with child spans for LLM calls
    and tool calls. Eval results are attached as attributes on the root span.

    Uses ``gen_ai.*`` attributes following OTel semantic conventions for LLM
    spans, and ``agentest.*`` for tool calls, costs, and evaluation scores.

    Args:
        tracer_provider: An OTel TracerProvider. If None, uses the global provider.
        service_name: Service name for the tracer. Defaults to "agentest".
    """

    def __init__(
        self,
        tracer_provider: Any | None = None,
        service_name: str = "agentest",
    ) -> None:
        _require_otel()
        provider = tracer_provider or trace.get_tracer_provider()
        self.tracer = provider.get_tracer(service_name, agentest.__version__)

    def export(
        self,
        agent_trace: AgentTrace,
        eval_results: list[EvalResult] | None = None,
    ) -> None:
        """Export an AgentTrace as OTel spans.

        Creates a root span for the agent run with child spans for each
        LLM call and tool call. Optionally attaches evaluation scores
        as attributes on the root span.

        Args:
            agent_trace: The trace to export.
            eval_results: Optional evaluation results to attach as root span attributes.
        """
        start = _ns(agent_trace.start_time)

        with self.tracer.start_as_current_span(
            name=agent_trace.task or "agent.run",
            start_time=start,
            attributes={
                "agentest.trace.id": agent_trace.id,
                "agentest.task": agent_trace.task or "",
                "agentest.total_cost": agent_trace.total_cost,
                "agentest.total_tokens": agent_trace.total_tokens,
            },
        ) as root:
            for resp in agent_trace.llm_responses:
                self._export_llm_span(resp)

            for tc in agent_trace.tool_calls:
                self._export_tool_span(tc)

            if eval_results:
                for r in eval_results:
                    root.set_attribute(f"agentest.eval.{r.evaluator}", r.score)
                    root.set_attribute(f"agentest.eval.{r.evaluator}.passed", r.passed)

            if agent_trace.success is False:
                root.set_status(StatusCode.ERROR, agent_trace.error or "agent failed")

            if agent_trace.end_time is not None:
                root.end(end_time=_ns(agent_trace.end_time))

    def _export_llm_span(self, resp: LLMResponse) -> None:
        """Create a child span for an LLM call."""
        attrs: dict[str, Any] = {
            "gen_ai.system": _infer_system(resp.model),
            "gen_ai.request.model": resp.model,
            "gen_ai.usage.input_tokens": resp.input_tokens,
            "gen_ai.usage.output_tokens": resp.output_tokens,
            "agentest.cost": resp.cost_estimate,
        }
        if resp.latency_ms:
            attrs["agentest.latency_ms"] = resp.latency_ms

        with self.tracer.start_as_current_span(
            "gen_ai.request",
            start_time=_ns(resp.timestamp),
            attributes=attrs,
        ) as span:
            if resp.latency_ms:
                end_ns = _ns(resp.timestamp) + int(resp.latency_ms * 1_000_000)
                span.end(end_time=end_ns)

    def _export_tool_span(self, tc: ToolCall) -> None:
        """Create a child span for a tool call."""
        attrs: dict[str, Any] = {
            "agentest.tool.name": tc.name,
            "agentest.tool.arguments": json.dumps(tc.arguments, default=str),
            "agentest.tool.succeeded": tc.succeeded,
        }
        if tc.duration_ms is not None:
            attrs["agentest.tool.duration_ms"] = tc.duration_ms

        with self.tracer.start_as_current_span(
            f"tool_call.{tc.name}",
            start_time=_ns(tc.timestamp),
            attributes=attrs,
        ) as span:
            if not tc.succeeded:
                span.set_status(StatusCode.ERROR, tc.error or "tool failed")
            if tc.duration_ms is not None:
                end_ns = _ns(tc.timestamp) + int(tc.duration_ms * 1_000_000)
                span.end(end_time=end_ns)
