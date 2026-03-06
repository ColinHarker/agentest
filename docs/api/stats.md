---
sidebar_position: 13
title: Stats
---

# Stats

Statistical analysis -- trend detection, confidence intervals, and SLO tracking.

## `TrendResult`

`agentest.stats.TrendResult`

Result of trend analysis for a metric. Pydantic model with fields: `metric` (str), `direction` (TrendDirection: `"improving"`, `"degrading"`, or `"stable"`), `slope` (float), `r_squared` (float), `samples` (int).

## `ConfidenceInterval`

`agentest.stats.ConfidenceInterval`

Confidence interval for a metric. Pydantic model with fields: `metric` (str), `mean` (float), `std` (float), `ci_lower` (float), `ci_upper` (float), `confidence` (float), `samples` (int).

## `SLO`

`agentest.stats.SLO`

Service Level Objective definition. Pydantic model with fields: `metric` (str), `target` (float), `comparison` (str: `"lte"`, `"gte"`, `"lt"`, or `"gt"`).

## `SLOResult`

`agentest.stats.SLOResult`

SLO compliance result. Pydantic model with fields: `slo` (SLO), `current_value` (float), `compliant` (bool), `compliance_rate` (float), `samples` (int).

## `StatsAnalyzer`

`agentest.stats.StatsAnalyzer`

Statistical analysis of agent performance over multiple runs.

**Constructor:**

- `StatsAnalyzer(history_file: str | Path | None = None)` — Optionally load persisted history from a JSON file.

**Methods:**

- `add_trace(trace: AgentTrace, score: float = 1.0, passed: bool = True) -> None` — Add a single trace as a sample, keyed by `trace.task`.
- `add_benchmark_result(result: BenchmarkResult) -> None` — Extract samples from a BenchmarkResult and add to history.
- `trend(task: str, metric: str = "score", window: int = 10) -> TrendResult` — Detect trend using linear regression over last N samples. Direction accounts for metric semantics (for cost/tokens/latency, increasing is degrading; for score/passed, increasing is improving). A trend is only flagged when `r_squared > 0.3`.
- `confidence_interval(task: str, metric: str = "score", confidence: float = 0.95) -> ConfidenceInterval` — Compute confidence interval using t-distribution.
- `check_slo(task: str, slo: SLO, window: int = 20) -> SLOResult` — Check SLO compliance over recent window.
- `check_slos(slos: list[SLO], window: int = 20) -> list[SLOResult]` — Check all SLOs across all tasks.
- `save(path: str | Path) -> Path` — Persist history to JSON.
- `load(path: str | Path) -> StatsAnalyzer` — Static method. Load history from JSON.

**Example:**

```python
from agentest.stats import StatsAnalyzer, SLO

analyzer = StatsAnalyzer()
analyzer.add_trace(trace1, score=0.95)
analyzer.add_trace(trace2, score=0.90)

trend = analyzer.trend("my_task", metric="score")
ci = analyzer.confidence_interval("my_task", metric="cost")

slo = SLO(metric="cost", target=0.50, comparison="lte")
slo_result = analyzer.check_slo("my_task", slo)
print(slo_result.compliant, slo_result.compliance_rate)
```
