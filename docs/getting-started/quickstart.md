---
sidebar_position: 2
title: Quick Start
---

# Quick Start

This guide walks you through the core features of Agentest in 5 minutes.

## 1. Record an Agent Interaction

```python
from agentest import Recorder

recorder = Recorder(task="Summarize README.md")
recorder.record_message("user", "Please summarize README.md")
recorder.record_tool_call(
    name="read_file",
    arguments={"path": "README.md"},
    result="# My Project\nA sample project.",
)
recorder.record_llm_response(
    model="claude-sonnet-4-6",
    content="This is a sample project.",
    input_tokens=100,
    output_tokens=20,
)
trace = recorder.finalize(success=True)

# Save for later
recorder.save("traces/summarize.yaml")
```

## 2. Evaluate the Trace

```python
from agentest import TaskCompletionEvaluator, SafetyEvaluator, CostEvaluator

for evaluator in [
    TaskCompletionEvaluator(),
    SafetyEvaluator(),
    CostEvaluator(max_cost=0.10),
]:
    result = evaluator.evaluate(trace)
    print(f"{result.evaluator}: {'PASS' if result.passed else 'FAIL'} ({result.score:.2f})")
```

## 3. Mock Tools

```python
from agentest import MockToolkit

toolkit = MockToolkit()
toolkit.mock("read_file").returns("file contents")
toolkit.mock("search").when(query="python").returns(["result"])

result = toolkit.execute("read_file", path="test.txt")  # "file contents"
toolkit.mock("read_file").assert_called()
```

## 4. Use with pytest

```python
# tests/test_my_agent.py
def test_agent(agent_recorder, agent_eval_suite):
    agent_recorder.record_llm_response("claude-sonnet-4-6", "Done.", 50, 10)
    trace = agent_recorder.finalize(success=True)
    results = agent_eval_suite.evaluate_all(trace)
    assert all(r.passed for r in results)
```

```bash
pytest tests/ --agentest-max-cost=0.50
```

## 5. CLI

```bash
# Initialize project
agentest init

# Evaluate a trace
agentest evaluate traces/summarize.yaml --check-safety

# Summarize all traces
agentest summary traces/
```

## Next Steps

- [Recording Traces](../guide/recording.md) — detailed recording guide
- [Evaluators](../guide/evaluators.md) — all 7 built-in evaluators
- [API Reference](../api/core.md) — full API docs
