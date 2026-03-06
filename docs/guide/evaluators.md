---
sidebar_position: 4
title: Evaluators
---

# Evaluators

Evaluators inspect an `AgentTrace` and produce a score (0.0–1.0) and pass/fail result.

## Built-in Evaluators

### TaskCompletionEvaluator

Checks whether the agent completed its task.

```python
from agentest import TaskCompletionEvaluator

evaluator = TaskCompletionEvaluator(
    require_tool_calls=False,  # require at least one tool call
    min_messages=1,            # minimum messages in trace
)
result = evaluator.evaluate(trace)
```

**Scoring:** -0.25 per issue (success status, errors, message count, failed tools). Min 0.0.

### SafetyEvaluator

Scans for dangerous patterns in agent output.

```python
from agentest import SafetyEvaluator

evaluator = SafetyEvaluator(
    check_commands=True,           # rm -rf, DROP TABLE, etc.
    check_pii=True,                # SSN, credit cards, emails, API keys
    custom_patterns=[r"password="], # your own regex patterns
    blocked_tools=["exec"],        # tools that should never be called
    pii_whitelist=[r".*@example\.com"],  # PII patterns to ignore (fullmatch)
)
```

Use `pii_whitelist` to suppress false positives from legitimate test data. Each pattern is matched with `re.fullmatch` against the detected PII string.

**Scoring:** -0.2 per violation. Min 0.0.

### CostEvaluator

Enforces cost and token budgets.

```python
from agentest import CostEvaluator

evaluator = CostEvaluator(
    max_cost=0.50,        # max USD
    max_tokens=100000,    # max total tokens
    max_llm_calls=10,     # max LLM API calls
)
```

**Scoring:** Binary — 1.0 if all pass, 0.0 if any exceeded.

### LatencyEvaluator

Checks execution time.

```python
from agentest.evaluators.builtin import LatencyEvaluator

evaluator = LatencyEvaluator(
    max_total_ms=30000,     # max total duration
    max_per_call_ms=5000,   # max per tool call
)
```

**Scoring:** 1.0 if pass, 0.5 if fail.

### ToolUsageEvaluator

Evaluates tool usage patterns.

```python
from agentest import ToolUsageEvaluator

evaluator = ToolUsageEvaluator(
    required_tools=["read_file"],  # must be called
    forbidden_tools=["exec"],      # must not be called
    max_tool_calls=20,             # total call limit
    max_retries_per_tool=3,        # same tool+args retry limit
)
```

**Scoring:** -0.2 per issue. Min 0.0.

### LLMJudgeEvaluator

Uses an LLM to grade agent output against custom criteria.

```python
from agentest.evaluators.base import LLMJudgeEvaluator
import anthropic

evaluator = LLMJudgeEvaluator(
    criteria="Was the response helpful and accurate?",
    model="claude-sonnet-4-6",
    client=anthropic.Anthropic(),
)
```

Supports both Anthropic and OpenAI clients.

### CompositeEvaluator

Combine multiple evaluators.

```python
from agentest.evaluators.base import CompositeEvaluator

suite = CompositeEvaluator(
    evaluators=[TaskCompletionEvaluator(), SafetyEvaluator()],
    require_all=True,  # AND logic (False = OR)
)

# Aggregated result
result = suite.evaluate(trace)

# Individual results
results = suite.evaluate_all(trace)
```

## Custom Evaluators

```python
from agentest.evaluators.base import Evaluator, EvalResult
from agentest.core import AgentTrace

class MyEvaluator(Evaluator):
    name = "my_evaluator"
    description = "Checks something specific"

    def evaluate(self, trace: AgentTrace) -> EvalResult:
        passed = trace.total_tool_calls < 10
        return EvalResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            message="OK" if passed else "Too many tool calls",
        )
```
