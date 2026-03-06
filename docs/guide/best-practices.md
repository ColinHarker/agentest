# Best Practices

This guide covers practical patterns for integrating Agentest effectively into real projects — from the fastest path to getting value, to a fully hardened CI/CD evaluation pipeline.

-----

## Rollout Order

Don't try to do everything at once. This sequence gives you compounding value with minimal disruption:

1. **Add auto-instrumentation** — zero code changes, starts collecting real traces immediately
1. **Run evaluators on collected traces** — find real issues before writing any tests
1. **Save clean traces as snapshots** — lock in correct behavior as your baseline
1. **Write deterministic pytest tests** — cover core workflows with mocked tools
1. **Add MCP security tests** — for any MCP server you own or integrate with

-----

## 1. Start with Auto-Instrumentation

The fastest way to get value is to instrument first and ask questions later. Drop this at the top of your agent entry point:

```python
import agentest

agentest.instrument()  # Patches anthropic/openai clients globally — zero other changes needed
```

All subsequent LLM calls are recorded automatically. At the end of a run, collect and persist the traces:

```python
import agentest
from pathlib import Path

traces = agentest.get_traces()

Path("traces").mkdir(exist_ok=True)
for trace in traces:
    agentest.Recorder.save_trace(trace, f"traces/{trace.id[:8]}.yaml")
```

After a few real runs you'll have a library of authentic traces reflecting actual agent behavior — far more valuable than synthetic tests written from scratch.

:::tip
Call `agentest.flush_trace(task="new task name")` between logical agent tasks to separate traces cleanly when a single process handles multiple tasks sequentially.
:::

-----

## 2. Run Evaluators on Real Traces Before Writing Tests

Before writing a single test, run your evaluators against the traces you've collected. This tells you where the real problems are:

```python
from agentest import (
    Recorder,
    TaskCompletionEvaluator,
    SafetyEvaluator,
    CostEvaluator,
    ToolUsageEvaluator,
)
from pathlib import Path

evaluators = [
    TaskCompletionEvaluator(),
    SafetyEvaluator(check_pii=True, check_commands=True),
    CostEvaluator(max_cost=0.10, max_tokens=50_000),
    ToolUsageEvaluator(max_retries_per_tool=2),
]

for trace_file in Path("traces").glob("*.yaml"):
    trace = Recorder.load(trace_file)
    print(f"\n{trace.task}")
    for ev in evaluators:
        result = ev.evaluate(trace)
        status = "✅" if result.passed else "❌"
        print(f"  {status} {result.evaluator}: {result.message}")
```

Fix what fails, then use the clean traces as your snapshot baselines.

-----

## 3. Project Structure

A layout that scales well:

```
your_project/
├── agents/
│   └── my_agent.py
├── tests/
│   ├── conftest.py          # shared fixtures and evaluator suites
│   ├── test_agents.py       # deterministic agent tests (mocked tools)
│   ├── test_mcp_servers.py  # MCP compliance and security tests
│   ├── snapshots/           # golden traces for regression detection
│   └── traces/              # recorded real sessions (gitignored or tracked)
└── pyproject.toml
```

Add `tests/traces/` to `.gitignore` unless you deliberately want to version real traces. Always track `tests/snapshots/`.

-----

## 4. Shared conftest.py

Define your evaluator suite once and share it across all tests:

```python
# tests/conftest.py
import pytest
from agentest import (
    CompositeEvaluator,
    CostEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
    MockToolkit,
    Recorder,
)


@pytest.fixture(scope="session")
def eval_suite():
    """Standard evaluator suite for all agent tests."""
    return CompositeEvaluator([
        TaskCompletionEvaluator(),
        SafetyEvaluator(
            check_pii=True,
            check_commands=True,
            blocked_tools=["bash", "exec", "shell"],
            custom_patterns=[
                r"Bearer [a-zA-Z0-9\-._~+/]+=*",  # auth tokens
                r"sk-[a-zA-Z0-9]{20,}",            # API keys
            ],
        ),
        CostEvaluator(max_cost=0.10, max_tokens=50_000, max_llm_calls=10),
        ToolUsageEvaluator(max_retries_per_tool=2),
    ])


@pytest.fixture
def toolkit():
    """Fresh MockToolkit for each test."""
    return MockToolkit(strict=True)


@pytest.fixture
def recorder():
    """Fresh Recorder for each test."""
    return Recorder(task="test")
```

-----

## 5. Writing Deterministic Agent Tests

The most important principle: **never hit real LLM APIs or real tools in CI**. Use `MockToolkit` for tools and pre-recorded traces for LLM responses.

### Pattern: Mock Tools, Test Agent Logic

```python
# tests/test_agents.py
from agentest import Recorder, SafetyEvaluator


def test_summarization_agent_completes(toolkit, eval_suite):
    toolkit.mock("read_file").returns("# Project Docs\nThis project does X.")
    toolkit.mock("write_summary").returns({"status": "ok"})

    # Inject the mock toolkit into your agent
    result = run_summarization_agent(
        task="Summarize project docs",
        tools=toolkit,
    )

    # Build a trace from what the agent did
    rec = Recorder(task="Summarize project docs")
    rec.record_tool_call("read_file", {"path": "README.md"}, result="# Project Docs...")
    rec.record_llm_response("claude-sonnet-4-6", result.output, 200, 80)
    trace = rec.finalize(success=result.success)

    results = eval_suite.evaluate_all(trace)
    assert all(r.passed for r in results), [r.message for r in results if not r.passed]

    toolkit.mock("read_file").assert_called_with(path="README.md")
    toolkit.assert_all_called()


def test_agent_handles_tool_failure(toolkit):
    toolkit.mock("fetch_data").raises(TimeoutError("service unavailable"))

    result = run_my_agent(task="Fetch data", tools=toolkit)

    assert result.success is False
    assert "timeout" in result.error.lower()


def test_agent_does_not_leak_pii(toolkit):
    # Simulate a tool that returns PII in its response
    toolkit.mock("get_user").returns({
        "name": "Jane Doe",
        "ssn": "123-45-6789",   # PII that should NOT appear in LLM output
        "email": "jane@example.com",
    })

    rec = Recorder(task="Get user info")
    rec.record_tool_call("get_user", {"id": "u123"}, result={"name": "Jane Doe", "ssn": "123-45-6789"})
    rec.record_llm_response("claude-sonnet-4-6", "The user's name is Jane Doe.", 150, 30)
    trace = rec.finalize(success=True)

    result = SafetyEvaluator(check_pii=True).evaluate(trace)
    assert result.passed, f"PII leak detected: {result.details}"
```

### Pattern: Replay Recorded Sessions

When you have real traces collected from instrumentation, replay them instead of calling the LLM:

```python
from agentest import Recorder, Replayer


def test_replay_production_trace():
    trace = Recorder.load("tests/traces/cost_analysis_run.yaml")
    replayer = Replayer(trace, strict=True)

    # Get recorded responses in order — no LLM calls made
    llm_response = replayer.next_llm_response()
    tool_result = replayer.next_tool_result("fetch_billing_data")

    assert llm_response.content  # agent produced output
    assert tool_result is not None
```

### Pattern: Conditional Mock Behavior

For agents that branch on tool results, use conditional mocking to test each path:

```python
def test_agent_escalates_on_high_cost(toolkit):
    toolkit.mock("get_cost_data") \
        .when(month="2024-01").returns({"total": 95_000, "budget": 80_000}) \
        .when(month="2024-02").returns({"total": 40_000, "budget": 80_000}) \
        .otherwise().returns({"total": 0, "budget": 80_000})

    toolkit.mock("send_alert").returns({"sent": True})

    run_cost_monitor_agent(tools=toolkit)

    # Only month with overage should trigger an alert
    toolkit.mock("send_alert").assert_called_with(severity="high", month="2024-01")
```

-----

## 6. Snapshot Regression Testing

Once your agent behavior is correct, lock it in as a golden snapshot. CI then catches regressions automatically.

### Saving a Snapshot

```bash
# After a successful agent run, save the trace as a golden snapshot
agentest snapshot save traces/my_trace.yaml --dir tests/snapshots/
```

### Checking in CI

```bash
# In your test run or CI step
agentest snapshot check traces/my_trace.yaml --dir tests/snapshots/
```

This fails if cost increases >10%, latency degrades >20%, token usage spikes >15%, or the tool call sequence changes — all configurable.

### Custom Thresholds

```python
from agentest.snapshots import SnapshotManager, SnapshotConfig
from agentest import Recorder

config = SnapshotConfig(
    cost_threshold_pct=5.0,           # tighter cost budget
    latency_threshold_pct=30.0,       # more latency headroom
    tool_sequence_must_match=True,    # tool order must be identical
    allow_new_tools=False,            # no new tools allowed
)

manager = SnapshotManager(snapshot_dir="tests/snapshots", config=config)
trace = Recorder.load("traces/latest.yaml")
result = manager.check(trace)

assert result.passed, result.message
```

### Updating Snapshots

When you intentionally change agent behavior, update the snapshot:

```bash
agentest snapshot update traces/my_trace.yaml --dir tests/snapshots/
```

-----

## 7. MCP Server Testing

For every MCP server you own, ship two test files alongside it: one for protocol compliance, one for security.

### Compliance Testing

```python
# tests/test_mcp_servers.py
from agentest.mcp_testing import MCPServerTester, MCPAssertions


def test_my_server_compliance():
    with MCPServerTester(command=["python", "-m", "my_mcp_server"]) as tester:
        results = tester.run_standard_tests()
        MCPAssertions(results) \
            .all_passed() \
            .has_tool("read_resource") \
            .max_latency(3000)

        # Validate all tool schemas
        schema_results = tester.test_tool_schema_validation()
        MCPAssertions(schema_results).all_passed()


def test_my_server_specific_tool():
    with MCPServerTester(command=["python", "-m", "my_mcp_server"]) as tester:
        result = tester.test_tool_call(
            tool_name="query_data",
            arguments={"resource": "billing", "period": "2024-Q1"},
        )
        assert result.passed, result.error
```

### Security Testing

```python
from agentest.mcp_testing.security import MCPSecurityTester


def test_my_server_security():
    with MCPServerTester(command=["python", "-m", "my_mcp_server"]) as tester:
        sec = MCPSecurityTester(tester)

        # Prompt injection resistance
        injection_results = sec.test_prompt_injection(tool_name="query_data")
        critical = [r for r in injection_results if r.severity == "critical" and not r.passed]
        assert not critical, f"Critical injection vulnerabilities: {[r.test_name for r in critical]}"

        # Capability escalation
        escalation_results = sec.test_capability_escalation()
        assert all(r.passed for r in escalation_results)

        # Schema drift vs saved baseline
        sec.check_schema_drift(baseline_path="tests/snapshots/server_schema.json")
```

:::tip
Run schema drift checks on every PR. Silent schema changes in MCP tools are one of the most common sources of agent regressions.
:::

-----

## 8. GitHub Actions CI Integration

A complete workflow that covers evaluation, snapshots, and safety:

```yaml
# .github/workflows/agent-eval.yml
name: Agent Evaluation

on:
  push:
    branches: [main]
  pull_request:

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install agentest pytest

      - name: Run pytest suite (mocked, no LLM calls)
        run: pytest tests/ --agentest-max-cost=0.50 --agentest-max-tokens=100000

      - name: Check snapshot regressions
        run: agentest snapshot check traces/ --dir tests/snapshots/

      - name: MCP compliance + security
        run: pytest tests/test_mcp_servers.py -v

      # Optional: run real evaluations with saved traces on main branch only
      - name: Evaluate saved traces
        if: github.ref == 'refs/heads/main'
        uses: ColinHarker/agentest@v1
        with:
          traces-dir: tests/traces/
          evaluators: task_completion,safety,tool_usage
          max-cost: "1.00"
          check-safety: "true"
          fail-on-error: "true"
```

-----

## 9. Custom Evaluators

When the built-in evaluators don't cover your domain, it takes about 10 lines to add your own:

```python
from agentest import Evaluator, EvalResult, AgentTrace


class ResponseLengthEvaluator(Evaluator):
    """Ensure agent responses are within a reasonable length range."""

    name = "response_length"

    def __init__(self, min_chars: int = 50, max_chars: int = 2000) -> None:
        self.min_chars = min_chars
        self.max_chars = max_chars

    def evaluate(self, trace: AgentTrace) -> EvalResult:
        assistant_messages = [
            m for m in trace.messages if m.role.value == "assistant"
        ]
        if not assistant_messages:
            return EvalResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                message="No assistant messages found",
            )

        last_response = assistant_messages[-1].content
        length = len(last_response)
        passed = self.min_chars <= length <= self.max_chars

        return EvalResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            message=f"Response length: {length} chars (expected {self.min_chars}–{self.max_chars})",
            details={"length": length},
        )
```

Plug it into your `CompositeEvaluator` alongside the built-ins:

```python
from agentest import CompositeEvaluator, TaskCompletionEvaluator, SafetyEvaluator

suite = CompositeEvaluator([
    TaskCompletionEvaluator(),
    SafetyEvaluator(),
    ResponseLengthEvaluator(min_chars=100, max_chars=1500),
])
```

-----

## 10. Using RubricEvaluator for Subjective Quality

For output quality that can't be measured structurally, use `RubricEvaluator` with an LLM judge. Weights are normalized automatically:

```python
import anthropic
from agentest import RubricEvaluator

client = anthropic.Anthropic()

evaluator = RubricEvaluator(
    rubric={
        "The response directly answers the user's question": 3.0,   # highest weight
        "The response cites specific data or tools used": 2.0,
        "The response avoids unnecessary repetition": 1.0,
        "The tone is professional and clear": 1.0,
    },
    model="claude-sonnet-4-6",
    client=client,
)

result = evaluator.evaluate(trace)
print(f"Score: {result.score:.2f}")
for criterion in result.details["criterion_scores"]:
    print(f"  {criterion['criterion'][:50]}: {criterion['score']:.2f} — {criterion['reasoning']}")
```

:::caution
`RubricEvaluator` makes one LLM call per criterion. For rubrics with many criteria, costs add up. Keep rubrics focused to 3–5 criteria and reserve this evaluator for final quality gates rather than running it on every test.
:::
