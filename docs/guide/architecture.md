---
sidebar_position: 11
title: Architecture & Comparison
---

# Architecture & Comparison

## Project Structure

```
agentest/
├── core.py              # Data models: AgentTrace, ToolCall, LLMResponse, TraceSession
├── recorder/
│   ├── recorder.py      # Record agent sessions to YAML/JSON
│   ├── replayer.py      # Replay sessions deterministically
│   └── streaming.py     # StreamingRecorder for real-time trace events
├── mocking/
│   └── tool_mock.py     # ToolMock, MockToolkit — fluent builder + assertions
├── evaluators/
│   ├── base.py          # Evaluator ABC, EvalResult, CompositeEvaluator, LLMJudge, Rubric
│   ├── builtin.py       # TaskCompletion, Safety, Cost, Latency, ToolUsage
│   ├── metrics.py       # Custom numeric metrics with thresholds
│   └── _llm_utils.py    # Shared LLM judge utilities
├── benchmark/
│   ├── runner.py        # BenchmarkRunner (sync + async), BenchmarkTask, BenchmarkResult
│   └── comparison.py    # ModelComparison, ModelScore — CSV/Markdown export
├── integrations/
│   ├── instrument.py    # Auto-instrumentation entry point
│   ├── _anthropic_patch.py # Anthropic client monkey-patching
│   ├── _openai_patch.py # OpenAI client monkey-patching
│   ├── middleware.py    # ASGI/WSGI middleware for FastAPI/Flask
│   ├── otel.py          # OpenTelemetry trace export
│   ├── langchain.py     # LangChain callback handler adapter
│   ├── crewai.py        # CrewAI crew recorder
│   ├── autogen.py       # AutoGen conversation recorder
│   ├── llamaindex.py    # LlamaIndex callback handler
│   ├── claude_agent_sdk.py # Claude Agent SDK tracer
│   └── openai_agents.py # OpenAI Agents SDK tracer
├── mcp_testing/
│   ├── server_tester.py # MCPServerTester — subprocess-based JSON-RPC testing
│   ├── assertions.py    # MCPAssertions — fluent assertion chains
│   └── security.py      # MCP security testing utilities
├── reporters/
│   ├── console.py       # Rich console output
│   └── json_reporter.py # Machine-readable JSON reports
├── server/
│   └── app.py           # FastAPI web UI for trace exploration
├── datasets.py          # Dataset management and test case splitting
├── regression.py        # Regression detection against baselines
├── stats.py             # Statistical analysis and SLO tracking
├── snapshots.py         # Trace snapshot testing
├── pytest_plugin.py     # Auto-registered fixtures, markers, and trace collectors
└── cli/                 # Click CLI with 15+ commands
    ├── _main.py         # CLI group and shared utilities
    ├── _evaluate.py     # evaluate command
    ├── _replay.py       # replay command
    ├── _summary.py      # summary command
    ├── _init.py         # init command with framework detection
    ├── _doctor.py       # doctor command
    ├── _diff.py         # diff command
    ├── _regression.py   # regression command
    ├── _stats.py        # stats command
    ├── _dataset.py      # dataset group (create, list, split)
    ├── _snapshot.py     # snapshot group (save, check, check-dir)
    ├── _serve.py        # serve and ui commands
    └── _watch.py        # watch command
```

## Design Principles

- **Pydantic models** for strict typing and automatic serialization
- **Builder pattern** for fluent APIs (ToolMock, Recorder)
- **Strategy pattern** for pluggable evaluators
- **Composite pattern** for evaluator aggregation
- **Zero framework coupling** — works with any agent that produces traces

## Comparison

| Feature | Agentest | LangSmith | LangFuse | Braintrust |
|---------|:---------:|:---------:|:--------:|:----------:|
| Record & Replay | Yes | — | — | — |
| Tool Mocking | Yes | Basic | — | — |
| Safety Evaluator | Yes | — | — | — |
| MCP Server Testing | Yes | — | — | — |
| pytest Integration | Yes | — | — | — |
| Framework-Agnostic | Yes | No | No | No |
| Open Source | Yes | No | No | No |
| Cost Tracking | Yes | Yes | Yes | Yes |
| Web UI | Basic | Full | Full | Full |
| Centralized Backend | — | Yes | Yes | Yes |
| Auto-Instrumentation | Yes | Yes | Yes | Yes |
| Framework Adapters | Yes (7) | No | Partial | — |
| GitHub Action | Yes | — | — | — |

**Best for:** Local development, CI/CD pipelines, deterministic testing, safety compliance, multi-model benchmarking.
