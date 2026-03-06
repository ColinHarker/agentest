---
sidebar_position: 7
title: Framework Integrations
---

# Framework Integrations

Agentest provides native adapters for popular AI agent frameworks. Each adapter converts framework-specific execution data into an `AgentTrace` for evaluation.

## Auto-Instrumentation

The simplest way to start — zero code changes required. `instrument()` monkey-patches the `anthropic` and `openai` client libraries so every API call is automatically recorded.

```python
import agentest

agentest.instrument()

# All subsequent API calls are recorded
import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=100,
)

# Retrieve recorded traces
traces = agentest.get_traces()
print(f"Recorded {len(traces)} traces")

# Flush current recording and start fresh
trace = agentest.flush_trace(task="next task")

# Remove patches when done
agentest.uninstrument()
```

### API

| Function | Description |
|---|---|
| `agentest.instrument()` | Patch anthropic/openai clients |
| `agentest.uninstrument()` | Remove patches, finalize active recording |
| `agentest.get_traces()` | Get all recorded traces |
| `agentest.clear_traces()` | Clear recorded traces |
| `agentest.flush_trace()` | Finalize current trace, optionally start new one |
| `agentest.get_current_recorder()` | Get the active Recorder for manual additions |

### Selective Instrumentation

```python
# Only instrument Anthropic
agentest.instrument(anthropic=True, openai=False)

# Only instrument OpenAI
agentest.instrument(anthropic=False, openai=True)
```

---

## LangChain

Install: `pip install agentest[langchain]`

The `AgentestCallbackHandler` plugs into LangChain's callback system to capture LLM calls, tool invocations, and chain events.

```python
from agentest.integrations.langchain import AgentestCallbackHandler

handler = AgentestCallbackHandler(task="Summarize document")

# Use with any LangChain chain or agent
result = chain.invoke(
    {"input": "Summarize this document"},
    config={"callbacks": [handler]},
)

# Get the trace
trace = handler.get_trace()

# Save for later evaluation
handler.save("traces/langchain_run.yaml")
```

### What Gets Recorded

- Chat model and LLM calls (with token usage)
- Tool start/end events
- Input messages
- Errors and exceptions

---

## CrewAI

Install: `pip install agentest[crewai]`

Record CrewAI crew executions with a single function call.

```python
from crewai import Crew, Agent, Task
from agentest.integrations.crewai import record_crew

crew = Crew(agents=[...], tasks=[...])

# Record the execution
result, trace = record_crew(
    crew,
    inputs={"topic": "AI testing"},
    task="Research AI testing tools",
)

# Evaluate the trace
from agentest import SafetyEvaluator
eval_result = SafetyEvaluator().evaluate(trace)
```

### Persistent Adapter

For recording multiple runs:

```python
from agentest.integrations.crewai import CrewAIAdapter

adapter = CrewAIAdapter(default_metadata={"env": "staging"})

result1, trace1 = adapter.record(crew1, inputs={...})
result2, trace2 = adapter.record(crew2, inputs={...})

all_traces = adapter.traces  # [trace1, trace2]
```

---

## AutoGen

Install: `pip install agentest[autogen]`

Record AutoGen multi-agent conversations.

```python
from agentest.integrations.autogen import record_autogen_chat

result, trace = record_autogen_chat(
    initiator=user_proxy,
    recipient=assistant,
    message="Write a hello world program in Python",
    task="Code generation",
)

# trace contains all messages, tool calls, and the final summary
print(f"Messages: {len(trace.messages)}")
print(f"Success: {trace.success}")
```

### Persistent Adapter

```python
from agentest.integrations.autogen import AutoGenAdapter

adapter = AutoGenAdapter()
result, trace = adapter.record_chat(user_proxy, assistant, "Hello")
all_traces = adapter.traces
```

---

## LlamaIndex

Install: `pip install agentest[llamaindex]`

The `AgentestHandler` hooks into LlamaIndex's callback system to capture queries, retrieval events, LLM calls, and function calls.

```python
from llama_index.core import Settings
from agentest.integrations.llamaindex import AgentestHandler

handler = AgentestHandler(task="RAG query")

# Set as global callback or pass to query engine
Settings.callback_manager.add_handler(handler)

response = query_engine.query("What is Agentest?")
trace = handler.get_trace()
```

### What Gets Recorded

- Query text
- LLM calls with token usage and model info
- Retrieval events (number of nodes retrieved)
- Function/tool calls
- Errors

---

## Claude Agent SDK

No extra install needed — works with the standard `anthropic` package.

```python
from agentest.integrations.claude_agent_sdk import AgentestTracer

tracer = AgentestTracer(task="Math problem solver")

# Wrap any function call
result, trace = tracer.record(agent.run, "What is 2+2?")

# Or use async
result, trace = await tracer.record_async(agent.run_async, "What is 2+2?")
```

### Context Manager

For fine-grained control over what gets recorded:

```python
tracer = AgentestTracer(task="Custom recording")

with tracer.recording() as recorder:
    recorder.record_message("user", "Hello")
    result = agent.run("Hello")
    recorder.record_llm_response(
        model="claude-sonnet-4-6",
        content=str(result),
        input_tokens=100,
        output_tokens=50,
    )

trace = tracer.get_trace()
```

---

## OpenAI Agents SDK

No extra install needed — works with the standard `openai` package.

```python
from agentest.integrations.openai_agents import AgentestTracer

tracer = AgentestTracer(task="Customer support agent")

# Wrap Runner.run_sync or Runner.run
result, trace = tracer.record(Runner.run_sync, agent, "Help me with my order")

# Async
result, trace = await tracer.record_async(Runner.run, agent, "Help me")
```

### What Gets Recorded

- Input messages
- Agent message outputs
- Tool calls and results
- Handoffs between agents
- Final output

---

## GitHub Action

Run Agentest evaluations in your CI/CD pipeline:

```yaml
# .github/workflows/agent-eval.yml
name: Agent Evaluation

on: [push, pull_request]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: ColinHarker/agentest@v1
        with:
          traces-dir: traces/
          evaluators: task_completion,safety,tool_usage
          max-cost: "1.00"
          check-safety: "true"
          fail-on-error: "true"
```

### Inputs

| Input | Default | Description |
|---|---|---|
| `traces-dir` | `traces` | Directory containing trace files |
| `evaluators` | `task_completion,safety,tool_usage` | Comma-separated evaluator list |
| `max-cost` | — | Maximum allowed cost in USD |
| `max-tokens` | — | Maximum allowed tokens |
| `check-safety` | `true` | Run safety evaluations |
| `output-file` | `agentest-report.json` | Path to save JSON report |
| `fail-on-error` | `true` | Fail workflow on evaluation failure |

### Outputs

| Output | Description |
|---|---|
| `total-traces` | Number of traces evaluated |
| `passed` | Number that passed |
| `failed` | Number that failed |
| `avg-score` | Average score across all traces |
| `report-path` | Path to the JSON report |
