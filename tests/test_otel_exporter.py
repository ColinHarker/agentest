"""Tests for the OpenTelemetry export integration."""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock

import pytest

from agentest.core import AgentTrace, LLMResponse, ToolCall
from agentest.evaluators.base import EvalResult
from agentest.integrations.otel import _infer_system, _ns

# ---- Helper to check if opentelemetry is installed ----

otel_installed = True
try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
except ImportError:
    otel_installed = False

pytestmark = pytest.mark.skipif(not otel_installed, reason="opentelemetry-sdk not installed")


# ---- Fixtures ----


@pytest.fixture
def otel_setup():
    """Set up an in-memory OTel exporter and return (provider, memory_exporter)."""
    memory_exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    return provider, memory_exporter


@pytest.fixture
def sample_trace():
    """Create a sample AgentTrace with LLM responses and tool calls."""
    now = time.time()
    trace = AgentTrace(
        task="Summarize document",
        start_time=now,
        end_time=now + 2.5,
        success=True,
        llm_responses=[
            LLMResponse(
                model="claude-sonnet-4-6",
                content="Here is the summary.",
                input_tokens=1250,
                output_tokens=340,
                latency_ms=1200.0,
                timestamp=now + 0.1,
            ),
        ],
        tool_calls=[
            ToolCall(
                name="read_file",
                arguments={"path": "README.md"},
                result="# Project\nThis is a project.",
                duration_ms=12.4,
                timestamp=now + 0.05,
            ),
        ],
    )
    return trace


# ---- Unit tests for helpers ----


class TestHelpers:
    def test_ns_conversion(self):
        assert _ns(1.0) == 1_000_000_000
        assert _ns(0.001) == 1_000_000
        assert _ns(0.0) == 0

    def test_infer_system_anthropic(self):
        assert _infer_system("claude-sonnet-4-6") == "anthropic"
        assert _infer_system("claude-opus-4-6") == "anthropic"
        assert _infer_system("Claude-Haiku") == "anthropic"

    def test_infer_system_openai(self):
        assert _infer_system("gpt-4o") == "openai"
        assert _infer_system("gpt-4o-mini") == "openai"
        assert _infer_system("o3") == "openai"
        assert _infer_system("o4-mini") == "openai"

    def test_infer_system_google(self):
        assert _infer_system("gemini-2.5-pro") == "google"
        assert _infer_system("gemini-2.5-flash") == "google"

    def test_infer_system_unknown(self):
        assert _infer_system("llama-3.1-70b") == "unknown"
        assert _infer_system("my-custom-model") == "unknown"


# ---- OTelExporter tests ----


class TestOTelExporter:
    def test_export_basic_trace(self, otel_setup, sample_trace):
        from agentest.integrations.otel import OTelExporter

        provider, memory = otel_setup
        exporter = OTelExporter(tracer_provider=provider)

        exporter.export(sample_trace)
        provider.force_flush()

        spans = memory.get_finished_spans()
        assert len(spans) == 3  # root + 1 LLM + 1 tool

        # Find spans by name
        span_names = {s.name for s in spans}
        assert "Summarize document" in span_names
        assert "gen_ai.request" in span_names
        assert "tool_call.read_file" in span_names

    def test_root_span_attributes(self, otel_setup, sample_trace):
        from agentest.integrations.otel import OTelExporter

        provider, memory = otel_setup
        exporter = OTelExporter(tracer_provider=provider)

        exporter.export(sample_trace)
        provider.force_flush()

        spans = memory.get_finished_spans()
        root = next(s for s in spans if s.name == "Summarize document")

        assert root.attributes["agentest.trace.id"] == sample_trace.id
        assert root.attributes["agentest.task"] == "Summarize document"
        assert root.attributes["agentest.total_tokens"] == sample_trace.total_tokens

    def test_llm_span_gen_ai_attributes(self, otel_setup, sample_trace):
        from agentest.integrations.otel import OTelExporter

        provider, memory = otel_setup
        exporter = OTelExporter(tracer_provider=provider)

        exporter.export(sample_trace)
        provider.force_flush()

        spans = memory.get_finished_spans()
        llm_span = next(s for s in spans if s.name == "gen_ai.request")

        assert llm_span.attributes["gen_ai.system"] == "anthropic"
        assert llm_span.attributes["gen_ai.request.model"] == "claude-sonnet-4-6"
        assert llm_span.attributes["gen_ai.usage.input_tokens"] == 1250
        assert llm_span.attributes["gen_ai.usage.output_tokens"] == 340
        assert llm_span.attributes["agentest.latency_ms"] == 1200.0

    def test_tool_span_attributes(self, otel_setup, sample_trace):
        from agentest.integrations.otel import OTelExporter

        provider, memory = otel_setup
        exporter = OTelExporter(tracer_provider=provider)

        exporter.export(sample_trace)
        provider.force_flush()

        spans = memory.get_finished_spans()
        tool_span = next(s for s in spans if s.name == "tool_call.read_file")

        assert tool_span.attributes["agentest.tool.name"] == "read_file"
        assert tool_span.attributes["agentest.tool.succeeded"] is True
        assert tool_span.attributes["agentest.tool.duration_ms"] == 12.4

    def test_export_with_eval_results(self, otel_setup, sample_trace):
        from agentest.integrations.otel import OTelExporter

        provider, memory = otel_setup
        exporter = OTelExporter(tracer_provider=provider)

        eval_results = [
            EvalResult(evaluator="safety", score=1.0, passed=True, message="Safe"),
            EvalResult(evaluator="cost", score=0.8, passed=True, message="Within budget"),
            EvalResult(
                evaluator="task_completion", score=0.0, passed=False, message="Incomplete"
            ),
        ]

        exporter.export(sample_trace, eval_results=eval_results)
        provider.force_flush()

        spans = memory.get_finished_spans()
        root = next(s for s in spans if s.name == "Summarize document")

        assert root.attributes["agentest.eval.safety"] == 1.0
        assert root.attributes["agentest.eval.safety.passed"] is True
        assert root.attributes["agentest.eval.cost"] == 0.8
        assert root.attributes["agentest.eval.cost.passed"] is True
        assert root.attributes["agentest.eval.task_completion"] == 0.0
        assert root.attributes["agentest.eval.task_completion.passed"] is False

    def test_export_failed_trace(self, otel_setup):
        from opentelemetry.trace import StatusCode

        from agentest.integrations.otel import OTelExporter

        provider, memory = otel_setup
        exporter = OTelExporter(tracer_provider=provider)

        now = time.time()
        trace = AgentTrace(
            task="Failing task",
            start_time=now,
            end_time=now + 1.0,
            success=False,
            error="LLM rate limited",
        )

        exporter.export(trace)
        provider.force_flush()

        spans = memory.get_finished_spans()
        root = next(s for s in spans if s.name == "Failing task")
        assert root.status.status_code == StatusCode.ERROR
        assert "rate limited" in root.status.description

    def test_export_failed_tool_call(self, otel_setup):
        from opentelemetry.trace import StatusCode

        from agentest.integrations.otel import OTelExporter

        provider, memory = otel_setup
        exporter = OTelExporter(tracer_provider=provider)

        now = time.time()
        trace = AgentTrace(
            task="Tool failure test",
            start_time=now,
            end_time=now + 1.0,
            success=True,
            tool_calls=[
                ToolCall(
                    name="fetch_data",
                    arguments={"url": "https://example.com"},
                    error="Connection timeout",
                    timestamp=now + 0.1,
                ),
            ],
        )

        exporter.export(trace)
        provider.force_flush()

        spans = memory.get_finished_spans()
        tool_span = next(s for s in spans if s.name == "tool_call.fetch_data")
        assert tool_span.status.status_code == StatusCode.ERROR
        assert tool_span.attributes["agentest.tool.succeeded"] is False

    def test_export_empty_task_name(self, otel_setup):
        from agentest.integrations.otel import OTelExporter

        provider, memory = otel_setup
        exporter = OTelExporter(tracer_provider=provider)

        now = time.time()
        trace = AgentTrace(start_time=now, end_time=now + 0.5, success=True)

        exporter.export(trace)
        provider.force_flush()

        spans = memory.get_finished_spans()
        root = next(s for s in spans if s.name == "agent.run")
        assert root is not None

    def test_span_parent_child_relationship(self, otel_setup, sample_trace):
        from agentest.integrations.otel import OTelExporter

        provider, memory = otel_setup
        exporter = OTelExporter(tracer_provider=provider)

        exporter.export(sample_trace)
        provider.force_flush()

        spans = memory.get_finished_spans()
        root = next(s for s in spans if s.name == "Summarize document")
        children = [s for s in spans if s.name != "Summarize document"]

        # All child spans should reference the root's context
        for child in children:
            assert child.parent is not None
            assert child.parent.span_id == root.context.span_id

    def test_custom_service_name(self, otel_setup):
        from agentest.integrations.otel import OTelExporter

        provider, _ = otel_setup
        exporter = OTelExporter(tracer_provider=provider, service_name="my-agent-service")
        assert exporter.tracer is not None


# ---- set_exporter / clear_exporter tests ----


class TestSetExporter:
    _inst_mod = sys.modules["agentest.integrations.instrument"]

    def setup_method(self):
        """Reset instrumentation state."""
        from agentest.integrations.instrument import clear_exporter, clear_traces

        clear_traces()
        clear_exporter()
        self._inst_mod._local.recorder = None

    def teardown_method(self):
        from agentest.integrations.instrument import clear_exporter

        clear_exporter()
        self._inst_mod._local.recorder = None

    def test_set_exporter_auto_export(self):
        from agentest.integrations.instrument import (
            _finalize_and_store,
            _get_recorder,
            set_exporter,
        )

        mock_exporter = MagicMock()
        set_exporter(mock_exporter)

        recorder = _get_recorder("test task")
        recorder.record_message("user", "hello")
        trace = _finalize_and_store(success=True)

        mock_exporter.export.assert_called_once_with(trace)

    def test_clear_exporter(self):
        from agentest.integrations.instrument import (
            _finalize_and_store,
            _get_recorder,
            clear_exporter,
            set_exporter,
        )

        mock_exporter = MagicMock()
        set_exporter(mock_exporter)
        clear_exporter()

        _get_recorder("test")
        _finalize_and_store(success=True)

        mock_exporter.export.assert_not_called()


# ---- Import guard test ----


class TestImportGuard:
    def test_import_without_otel_raises(self):
        """When opentelemetry is not available, OTelExporter raises ImportError."""
        import agentest.integrations.otel as otel_mod

        original = otel_mod._otel_available
        try:
            otel_mod._otel_available = False
            with pytest.raises(ImportError, match="pip install agentest"):
                otel_mod.OTelExporter()
        finally:
            otel_mod._otel_available = original
