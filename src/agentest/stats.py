"""Statistical analysis — trend detection, confidence intervals, SLO tracking."""

from __future__ import annotations

import json
import math
import statistics
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentest.core import AgentTrace


class RunSample(BaseModel):
    """Metrics from a single run."""

    timestamp: float
    cost: float = 0.0
    tokens: int = 0
    latency_ms: float | None = None
    score: float = 1.0
    passed: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrendDirection(str, Enum):
    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"


class TrendResult(BaseModel):
    """Result of trend analysis for a metric."""

    metric: str
    direction: TrendDirection
    slope: float
    r_squared: float
    samples: int


class ConfidenceInterval(BaseModel):
    """Confidence interval for a metric."""

    metric: str
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    confidence: float
    samples: int


class SLO(BaseModel):
    """Service Level Objective definition."""

    metric: str
    target: float
    comparison: str  # "lte", "gte", "lt", "gt"


class SLOResult(BaseModel):
    """SLO compliance result."""

    slo: SLO
    current_value: float
    compliant: bool
    compliance_rate: float
    samples: int


# t-distribution critical values for 95% confidence
# Indexed by degrees of freedom (1-30, then approximate for larger)
_T_TABLE_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    15: 2.131,
    20: 2.086,
    25: 2.060,
    30: 2.042,
}


def _t_critical(df: int, confidence: float = 0.95) -> float:
    """Get t-distribution critical value for given degrees of freedom."""
    if confidence != 0.95:
        # Approximate: for 99% multiply by ~1.5, for 90% multiply by ~0.8
        factor = 1.0
        if confidence >= 0.99:
            factor = 1.5
        elif confidence <= 0.90:
            factor = 0.8
        return _t_critical(df, 0.95) * factor

    if df in _T_TABLE_95:
        return _T_TABLE_95[df]
    # Find closest
    keys = sorted(_T_TABLE_95.keys())
    for i, k in enumerate(keys):
        if k >= df:
            return _T_TABLE_95[k]
    return 1.96  # Large sample approximation


def _get_metric_values(samples: list[RunSample], metric: str) -> list[float]:
    """Extract metric values from samples."""
    values: list[float] = []
    for s in samples:
        if metric == "cost":
            values.append(s.cost)
        elif metric == "tokens":
            values.append(float(s.tokens))
        elif metric == "latency_ms":
            if s.latency_ms is not None:
                values.append(s.latency_ms)
        elif metric == "score":
            values.append(s.score)
        elif metric == "passed":
            values.append(1.0 if s.passed else 0.0)
        else:
            # Try metadata
            if metric in s.metadata:
                values.append(float(s.metadata[metric]))
    return values


class StatsAnalyzer:
    """Statistical analysis of agent performance over multiple runs.

    Usage:
        analyzer = StatsAnalyzer()
        analyzer.add_trace(trace1, score=0.95)
        analyzer.add_trace(trace2, score=0.90)

        trend = analyzer.trend("my_task", metric="score")
        ci = analyzer.confidence_interval("my_task", metric="cost")
        slo = SLO(metric="cost", target=0.50, comparison="lte")
        slo_result = analyzer.check_slo("my_task", slo)
    """

    def __init__(self, history_file: str | Path | None = None) -> None:
        self.samples: dict[str, list[RunSample]] = {}
        if history_file:
            path = Path(history_file)
            if path.exists():
                self._load_from_file(path)

    def add_trace(
        self,
        trace: AgentTrace,
        score: float = 1.0,
        passed: bool = True,
    ) -> None:
        """Add a single trace as a sample."""
        task = trace.task or "default"
        sample = RunSample(
            timestamp=trace.start_time,
            cost=trace.total_cost,
            tokens=trace.total_tokens,
            latency_ms=trace.duration_ms,
            score=score,
            passed=passed,
        )
        if task not in self.samples:
            self.samples[task] = []
        self.samples[task].append(sample)

    def add_benchmark_result(self, result: Any) -> None:
        """Extract samples from a BenchmarkResult and add to history."""
        for task_result in result.tasks:
            if task_result.trace:
                self.add_trace(
                    task_result.trace,
                    score=task_result.avg_score if task_result.avg_score is not None else 1.0,
                    passed=task_result.all_passed,
                )

    def trend(
        self,
        task: str,
        metric: str = "score",
        window: int = 10,
    ) -> TrendResult:
        """Detect trend using linear regression over last N samples."""
        samples = self.samples.get(task, [])[-window:]
        values = _get_metric_values(samples, metric)

        if len(values) < 2:
            return TrendResult(
                metric=metric,
                direction=TrendDirection.STABLE,
                slope=0.0,
                r_squared=0.0,
                samples=len(values),
            )

        n = len(values)
        xs = list(range(n))
        x_mean = statistics.mean(xs)
        y_mean = statistics.mean(values)

        ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
        ss_xx = sum((x - x_mean) ** 2 for x in xs)
        ss_yy = sum((y - y_mean) ** 2 for y in values)

        if ss_xx == 0:
            slope = 0.0
            r_squared = 0.0
        else:
            slope = ss_xy / ss_xx
            ss_res = ss_yy - (ss_xy**2 / ss_xx)
            r_squared = 1.0 - (ss_res / ss_yy) if ss_yy > 0 else 0.0

        # Determine direction based on metric semantics
        # For cost/tokens/latency: increasing is degrading
        # For score/passed: increasing is improving
        improving_metrics = {"score", "passed"}
        if metric in improving_metrics:
            if slope > 0 and r_squared > 0.3:
                direction = TrendDirection.IMPROVING
            elif slope < 0 and r_squared > 0.3:
                direction = TrendDirection.DEGRADING
            else:
                direction = TrendDirection.STABLE
        else:
            if slope < 0 and r_squared > 0.3:
                direction = TrendDirection.IMPROVING
            elif slope > 0 and r_squared > 0.3:
                direction = TrendDirection.DEGRADING
            else:
                direction = TrendDirection.STABLE

        return TrendResult(
            metric=metric,
            direction=direction,
            slope=slope,
            r_squared=max(0.0, r_squared),
            samples=n,
        )

    def confidence_interval(
        self,
        task: str,
        metric: str = "score",
        confidence: float = 0.95,
    ) -> ConfidenceInterval:
        """Compute confidence interval for a metric."""
        samples = self.samples.get(task, [])
        values = _get_metric_values(samples, metric)

        if len(values) < 2:
            mean = values[0] if values else 0.0
            return ConfidenceInterval(
                metric=metric,
                mean=mean,
                std=0.0,
                ci_lower=mean,
                ci_upper=mean,
                confidence=confidence,
                samples=len(values),
            )

        n = len(values)
        mean = statistics.mean(values)
        std = statistics.stdev(values)
        t_val = _t_critical(n - 1, confidence)
        margin = t_val * (std / math.sqrt(n))

        return ConfidenceInterval(
            metric=metric,
            mean=mean,
            std=std,
            ci_lower=mean - margin,
            ci_upper=mean + margin,
            confidence=confidence,
            samples=n,
        )

    def check_slo(
        self,
        task: str,
        slo: SLO,
        window: int = 20,
    ) -> SLOResult:
        """Check SLO compliance over recent window."""
        samples = self.samples.get(task, [])[-window:]
        values = _get_metric_values(samples, slo.metric)

        if not values:
            return SLOResult(
                slo=slo,
                current_value=0.0,
                compliant=False,
                compliance_rate=0.0,
                samples=0,
            )

        current = values[-1]
        ops = {
            "lte": lambda v, t: v <= t,
            "gte": lambda v, t: v >= t,
            "lt": lambda v, t: v < t,
            "gt": lambda v, t: v > t,
        }
        compare = ops.get(slo.comparison, ops["lte"])
        compliant_count = sum(1 for v in values if compare(v, slo.target))

        return SLOResult(
            slo=slo,
            current_value=current,
            compliant=compare(current, slo.target),
            compliance_rate=compliant_count / len(values),
            samples=len(values),
        )

    def check_slos(
        self,
        slos: list[SLO],
        window: int = 20,
    ) -> list[SLOResult]:
        """Check all SLOs across all tasks."""
        results: list[SLOResult] = []
        for task in self.samples:
            for slo in slos:
                results.append(self.check_slo(task, slo, window))
        return results

    def save(self, path: str | Path) -> Path:
        """Persist history to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {task: [s.model_dump() for s in samples] for task, samples in self.samples.items()}
        path.write_text(json.dumps(data, indent=2))
        return path

    def _load_from_file(self, path: Path) -> None:
        """Load history from a JSON file."""
        data = json.loads(path.read_text())
        for task, samples in data.items():
            self.samples[task] = [RunSample.model_validate(s) for s in samples]

    @staticmethod
    def load(path: str | Path) -> StatsAnalyzer:
        """Load history from JSON."""
        analyzer = StatsAnalyzer()
        p = Path(path)
        if p.exists():
            analyzer._load_from_file(p)
        return analyzer
