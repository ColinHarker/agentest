---
slug: /
sidebar_position: 1
title: Introduction
---

# Agentest

**Universal testing and evaluation toolkit for AI agents.**

Agentest makes it dead simple to test, evaluate, and benchmark AI agents — regardless of which framework or LLM provider you use.

## Features

- **Record & Replay** — Capture real agent sessions, replay them deterministically
- **Tool Mocking** — Mock any tool call with a fluent, pytest-style API
- **7 Built-in Evaluators** — Grade agents on task completion, safety, cost, latency, and tool usage
- **Auto-Instrumentation** — `agentest.instrument()` patches anthropic/openai clients with zero code changes
- **Framework Adapters** — Native integrations for LangChain, CrewAI, AutoGen, LlamaIndex, Claude Agent SDK, OpenAI Agents SDK
- **Model Comparison** — Run the same tasks across Claude, GPT, Gemini and compare
- **MCP Server Testing** — Test MCP servers for protocol compliance
- **GitHub Action** — Run evaluations in CI/CD with configurable limits and safety checks
- **pytest Plugin** — Drop-in integration for CI/CD pipelines
- **CLI & Web UI** — Full command-line and browser-based workflows

## Installation

```bash
pip install agentest                # Core library
pip install agentest[web]           # Web UI dashboard
pip install agentest[langchain]     # LangChain adapter
pip install agentest[all]           # Everything
```

## Quick Example

```python
from agentest import Recorder, TaskCompletionEvaluator, SafetyEvaluator

recorder = Recorder(task="Summarize README.md")
recorder.record_tool_call("read_file", {"path": "README.md"}, result="# My Project...")
recorder.record_llm_response("claude-sonnet-4-6", "This is a sample project.", 100, 20)
trace = recorder.finalize(success=True)

for evaluator in [TaskCompletionEvaluator(), SafetyEvaluator()]:
    result = evaluator.evaluate(trace)
    print(f"{result.evaluator}: {'PASS' if result.passed else 'FAIL'}")
```

## Next Steps

- [Installation](getting-started/installation.md) — set up Agentest
- [Quick Start](getting-started/quickstart.md) — walk through core features
- [Framework Integrations](guide/integrations.md) — LangChain, CrewAI, AutoGen, and more
- [API Reference](api/core.md) — full API documentation
