---
sidebar_position: 9
title: OpenTelemetry Export
---

# OpenTelemetry Export

Export Agentest traces to any OpenTelemetry-compatible backend — Datadog, Grafana Tempo, Honeycomb, Jaeger, and more. Agent traces become first-class spans alongside your HTTP requests, database queries, and API calls.

## Installation

OpenTelemetry support is an optional extra:

```bash
pip install agentest[otel]
```

This installs `opentelemetry-api`, `opentelemetry-sdk`, and `opentelemetry-semantic-conventions`.

---

## Basic Usage

Export a single trace after an agent run:

```python
from agentest import Recorder
from agentest.integrations.otel import OTelExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Wire up your existing OTel provider
provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

exporter = OTelExporter(tracer_provider=provider)

# After any agent run, export the trace
recorder = Recorder(task="Summarize document")
# ... agent work ...
trace = recorder.finalize(success=True)
exporter.export(trace)
```

---

## Auto-Export Mode

Combine with auto-instrumentation to export every trace automatically:

```python
import agentest
from agentest.integrations.otel import OTelExporter

agentest.instrument()
agentest.set_exporter(OTelExporter())

# Normal agent code — all traces auto-exported on finalization
import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=100,
)

# Flush to finalize and export the current trace
agentest.flush_trace(task="next task")

# Stop auto-exporting
agentest.clear_exporter()
```

---

## Attaching Evaluation Scores

The differentiated part: OTel backends show not just that an agent ran, but whether it passed safety checks.

```python
from agentest import CompositeEvaluator, SafetyEvaluator, CostEvaluator

suite = CompositeEvaluator([SafetyEvaluator(), CostEvaluator(max_cost=0.10)])
results = suite.evaluate_all(trace)

exporter.export(trace, eval_results=results)
```

Eval scores appear as span attributes on the root span:
- `agentest.eval.safety` = 1.0
- `agentest.eval.safety.passed` = true
- `agentest.eval.cost` = 0.8
- `agentest.eval.cost.passed` = true

---

## Span Structure

Each `AgentTrace` maps to a root span with child spans for LLM calls and tool calls:

```
AgentTrace (root span)
├── gen_ai.request (LLM call 1)
│   ├── gen_ai.system = "anthropic"
│   ├── gen_ai.request.model = "claude-sonnet-4-6"
│   ├── gen_ai.usage.input_tokens = 1250
│   ├── gen_ai.usage.output_tokens = 340
│   └── agentest.cost = 0.0089
├── tool_call.read_file
│   ├── agentest.tool.name = "read_file"
│   ├── agentest.tool.arguments = '{"path": "README.md"}'
│   ├── agentest.tool.succeeded = true
│   └── agentest.tool.duration_ms = 12.4
├── gen_ai.request (LLM call 2)
│   └── ...
└── Root span attributes:
    agentest.eval.safety = 1.0
    agentest.eval.cost = 0.8
    agentest.eval.task_completion = 1.0
```

---

## Attribute Reference

### LLM Spans (`gen_ai.*` — OTel Semantic Conventions)

| Attribute | Type | Description |
|---|---|---|
| `gen_ai.system` | string | Provider: "anthropic", "openai", "google" |
| `gen_ai.request.model` | string | Model name (e.g., "claude-sonnet-4-6") |
| `gen_ai.usage.input_tokens` | int | Input tokens consumed |
| `gen_ai.usage.output_tokens` | int | Output tokens generated |

### Tool Spans (`agentest.tool.*`)

| Attribute | Type | Description |
|---|---|---|
| `agentest.tool.name` | string | Tool function name |
| `agentest.tool.arguments` | string | JSON-encoded arguments |
| `agentest.tool.succeeded` | bool | Whether the tool call succeeded |
| `agentest.tool.duration_ms` | float | Execution time in milliseconds |

### Root Span (`agentest.*`)

| Attribute | Type | Description |
|---|---|---|
| `agentest.trace.id` | string | Agentest trace ID |
| `agentest.task` | string | Task description |
| `agentest.total_cost` | float | Total estimated cost in USD |
| `agentest.total_tokens` | int | Total tokens across all LLM calls |
| `agentest.eval.<name>` | float | Evaluator score (0.0–1.0) |
| `agentest.eval.<name>.passed` | bool | Whether the evaluator passed |
| `agentest.cost` | float | Per-LLM-call cost estimate |
| `agentest.latency_ms` | float | Per-LLM-call latency |

---

## Backend Examples

### Console Exporter (debugging)

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

exporter = OTelExporter(tracer_provider=provider)
```

### OTLP gRPC (Datadog, Grafana Tempo, Honeycomb)

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317"))
)

exporter = OTelExporter(tracer_provider=provider)
```

### Jaeger

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(JaegerExporter(agent_host_name="localhost", agent_port=6831))
)

exporter = OTelExporter(tracer_provider=provider)
```
