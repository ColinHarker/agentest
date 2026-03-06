---
sidebar_position: 1
title: Quick Start
---

# Quick Start

Get from install to first passing test in under a minute.

## Install

```bash
pip install agentest
```

## 1. Evaluate a Trace

The simplest path — create a trace and evaluate it:

```python
import agentest
from agentest import Recorder

# Record what your agent did
recorder = Recorder(task="Summarize README")
recorder.record_message("user", "Summarize README.md")
recorder.record_llm_response(
    model="claude-sonnet-4-6",
    content="This project is a testing toolkit.",
    input_tokens=100,
    output_tokens=20,
)
trace = recorder.finalize(success=True)

# Evaluate it
results = agentest.evaluate(trace)
for r in results:
    print(f"{r.evaluator}: {'PASS' if r.passed else 'FAIL'} (score={r.score:.2f})")
```

## 2. Auto-Instrument LLM Calls

If you're using the Anthropic or OpenAI SDK, instrument once and every API call is recorded automatically:

```python
import agentest

agentest.instrument()

# Your normal agent code — no changes needed
import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=100,
)

# Get and evaluate traces
traces = agentest.get_traces()
results = agentest.evaluate(traces[0])
```

## 3. Wrap a Function

Use `agentest.run()` to trace any function in one call:

```python
import agentest

def my_agent(prompt):
    # ... calls LLM, uses tools, etc.
    return "result"

result, trace = agentest.run(my_agent, "Summarize README.md", task="Summarize")
results = agentest.evaluate(trace)
```

Or use the `@agentest.trace` decorator:

```python
@agentest.trace(task="Summarize document")
def my_agent(prompt):
    return client.messages.create(...)

result, trace = my_agent("Summarize README.md")
```

## 4. From Existing Messages

If you already have conversation logs in OpenAI format:

```python
from agentest import Recorder

trace = Recorder.from_messages(
    messages=[
        {"role": "user", "content": "Summarize this document"},
        {"role": "assistant", "content": "Here is the summary..."},
    ],
    task="Summarize",
    model="claude-sonnet-4-6",
    success=True,
)
```

## 5. Write Tests

```bash
agentest init  # generates test scaffolding
pytest tests/agent_tests/
```

Or write tests directly using pytest fixtures:

```python
import pytest
import agentest

@pytest.mark.agent_task("Summarize document")
def test_agent_summarizes(agent_recorder, agent_eval_suite):
    agent_recorder.record_message("user", "Summarize README.md")
    agent_recorder.record_llm_response(
        model="claude-sonnet-4-6",
        content="Summary here.",
        input_tokens=100,
        output_tokens=20,
    )
    trace = agent_recorder.finalize(success=True)
    results = agent_eval_suite.evaluate_all(trace)
    assert all(r.passed for r in results)
```

## 6. Check Your Setup

```bash
agentest doctor
```

Shows which SDKs are installed, whether the pytest plugin is registered, and what traces you have saved.

## Next Steps

- [Framework Integrations](./integrations.md) — LangChain, CrewAI, AutoGen, LlamaIndex adapters
- [OpenTelemetry Export](./otel.md) — Export traces to Datadog, Grafana, Honeycomb
- [Evaluators](./evaluators.md) — Safety, cost, latency, custom LLM judges
