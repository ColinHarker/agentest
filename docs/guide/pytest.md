---
sidebar_position: 8
title: pytest Integration
---

# pytest Integration

Agentest provides a pytest plugin that auto-registers fixtures and test collectors.

## Fixtures

Available automatically (no `conftest.py` needed):

| Fixture | Type | Description |
|---------|------|-------------|
| `agent_recorder` | `Recorder` | Fresh recorder per test |
| `agent_toolkit` | `MockToolkit` | Fresh mock toolkit per test |
| `agent_eval_suite` | `CompositeEvaluator` | Standard evaluator suite (respects CLI options) |
| `agent_trace_dir` | `Path \| None` | Path to traces directory |

## CLI Options

```bash
pytest tests/ \
    --agentest-traces=traces/ \
    --agentest-max-cost=0.50 \
    --agentest-max-tokens=100000
```

## Custom Markers

```python
import pytest

@pytest.mark.agent_eval
def test_evaluation():
    ...

@pytest.mark.agent_safety
def test_safety():
    ...

@pytest.mark.agent_benchmark
def test_benchmark():
    ...
```

## Trace File Tests

Place `.agent.yaml` or `.agent.json` files in your test directories. The plugin auto-discovers and evaluates them:

```
tests/
├── traces/
│   ├── summarize.agent.yaml   # auto-collected
│   └── search.agent.json      # auto-collected
└── test_my_agent.py
```

Each trace file is automatically replayed and evaluated with `TaskCompletionEvaluator`, `SafetyEvaluator`, and `ToolUsageEvaluator`.

## Example Test

```python
def test_agent_completes_task(agent_recorder, agent_eval_suite):
    agent_recorder.trace.task = "Summarize a document"
    agent_recorder.record_tool_call("read_file", {"path": "doc.txt"}, "contents")
    agent_recorder.record_llm_response("claude-sonnet-4-6", "Summary.", 100, 20)
    trace = agent_recorder.finalize(success=True)

    results = agent_eval_suite.evaluate_all(trace)
    assert all(r.passed for r in results)
```
