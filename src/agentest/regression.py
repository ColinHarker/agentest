"""Regression detection — compare traces across runs and flag regressions."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from agentest.core import AgentTrace, diff_traces
from agentest.evaluators.base import EvalResult, Evaluator
from agentest.recorder.recorder import Recorder


class RegressionThresholds(BaseModel):
    """Thresholds for regression detection.

    Values are relative changes (0.1 = 10% increase triggers regression).
    error_rate_increase is absolute (0.05 = 5 percentage points).
    """

    cost_increase: float = 0.1
    token_increase: float = 0.1
    latency_increase: float = 0.2
    error_rate_increase: float = 0.05
    tool_call_increase: float = 0.25


class Regression(BaseModel):
    """A detected regression or improvement."""

    metric: str
    baseline_value: float
    current_value: float
    change_pct: float
    threshold_pct: float
    severity: str = "warning"  # "warning" or "critical" (2x threshold)


class RegressionResult(BaseModel):
    """Result of regression detection for a single trace."""

    task: str
    regressions: list[Regression] = Field(default_factory=list)
    improvements: list[Regression] = Field(default_factory=list)
    passed: bool = True

    @property
    def has_regressions(self) -> bool:
        return len(self.regressions) > 0


def _safe_task_filename(task: str) -> str:
    """Convert a task description to a safe filename."""
    safe = re.sub(r"[^\w\s-]", "", task.lower())
    safe = re.sub(r"[\s]+", "_", safe.strip())
    return safe[:100] or "unnamed"


class RegressionDetector:
    """Detect regressions by comparing current traces against baselines.

    Usage:
        detector = RegressionDetector(baseline_dir="baselines/")
        result = detector.check(current_trace)
        if not result.passed:
            for r in result.regressions:
                print(f"Regression: {r.metric} increased {r.change_pct:.1%}")
    """

    def __init__(
        self,
        baseline_dir: str | Path,
        thresholds: RegressionThresholds | None = None,
    ) -> None:
        self.baseline_dir = Path(baseline_dir)
        self.thresholds = thresholds or RegressionThresholds()

    def _find_baseline(self, task: str) -> AgentTrace | None:
        """Find a baseline trace matching the given task name."""
        if not self.baseline_dir.exists():
            return None

        safe_name = _safe_task_filename(task)
        # Try exact filename match first
        for suffix in (".yaml", ".yml", ".json"):
            candidate = self.baseline_dir / f"{safe_name}{suffix}"
            if candidate.exists():
                return Recorder.load(candidate)

        # Scan all files for matching task
        for f in sorted(self.baseline_dir.iterdir()):
            if f.suffix in (".yaml", ".yml", ".json"):
                try:
                    trace = Recorder.load(f)
                    if trace.task == task:
                        return trace
                except Exception:
                    continue
        return None

    def check(self, trace: AgentTrace) -> RegressionResult:
        """Compare a trace against its baseline and detect regressions."""
        baseline = self._find_baseline(trace.task)
        if baseline is None:
            return RegressionResult(task=trace.task, passed=True)

        diff = diff_traces(baseline, trace)
        regressions: list[Regression] = []
        improvements: list[Regression] = []

        checks: list[tuple[str, str, float]] = [
            ("total_cost", "cost_increase", self.thresholds.cost_increase),
            ("total_tokens", "token_increase", self.thresholds.token_increase),
            ("tool_call_count", "tool_call_increase", self.thresholds.tool_call_increase),
        ]

        for metric_key, threshold_key, threshold in checks:
            if metric_key not in diff["summary"]:
                continue
            info = diff["summary"][metric_key]
            baseline_val = info["a"]
            current_val = info["b"]

            if baseline_val == 0:
                if current_val > 0:
                    change_pct = 1.0
                else:
                    continue
            else:
                change_pct = (current_val - baseline_val) / abs(baseline_val)

            if change_pct > threshold:
                severity = "critical" if change_pct > threshold * 2 else "warning"
                regressions.append(
                    Regression(
                        metric=metric_key,
                        baseline_value=baseline_val,
                        current_value=current_val,
                        change_pct=change_pct,
                        threshold_pct=threshold,
                        severity=severity,
                    )
                )
            elif change_pct < -threshold:
                improvements.append(
                    Regression(
                        metric=metric_key,
                        baseline_value=baseline_val,
                        current_value=current_val,
                        change_pct=change_pct,
                        threshold_pct=threshold,
                        severity="improvement",
                    )
                )

        # Latency check
        if "duration_ms" in diff["summary"]:
            d = diff["summary"]["duration_ms"]
            b_val = d["a"]
            c_val = d["b"]
            if b_val > 0:
                change = (c_val - b_val) / b_val
                if change > self.thresholds.latency_increase:
                    threshold_2x = self.thresholds.latency_increase * 2
                    severity = "critical" if change > threshold_2x else "warning"
                    regressions.append(
                        Regression(
                            metric="latency_ms",
                            baseline_value=b_val,
                            current_value=c_val,
                            change_pct=change,
                            threshold_pct=self.thresholds.latency_increase,
                            severity=severity,
                        )
                    )

        # Error rate check (absolute)
        b_errors = len([tc for tc in baseline.tool_calls if tc.error])
        c_errors = len([tc for tc in trace.tool_calls if tc.error])
        b_rate = b_errors / max(len(baseline.tool_calls), 1)
        c_rate = c_errors / max(len(trace.tool_calls), 1)
        rate_delta = c_rate - b_rate

        if rate_delta > self.thresholds.error_rate_increase:
            err_threshold_2x = self.thresholds.error_rate_increase * 2
            severity = "critical" if rate_delta > err_threshold_2x else "warning"
            regressions.append(
                Regression(
                    metric="error_rate",
                    baseline_value=b_rate,
                    current_value=c_rate,
                    change_pct=rate_delta,
                    threshold_pct=self.thresholds.error_rate_increase,
                    severity=severity,
                )
            )

        # Success regression
        if baseline.success and not trace.success:
            regressions.append(
                Regression(
                    metric="success",
                    baseline_value=1.0,
                    current_value=0.0,
                    change_pct=-1.0,
                    threshold_pct=0.0,
                    severity="critical",
                )
            )

        return RegressionResult(
            task=trace.task,
            regressions=regressions,
            improvements=improvements,
            passed=len(regressions) == 0,
        )

    def check_all(self, traces_dir: str | Path) -> list[RegressionResult]:
        """Check all traces in a directory against baselines."""
        traces_path = Path(traces_dir)
        results: list[RegressionResult] = []

        for f in sorted(traces_path.iterdir()):
            if f.suffix in (".yaml", ".yml", ".json"):
                try:
                    trace = Recorder.load(f)
                    results.append(self.check(trace))
                except Exception:
                    continue

        return results

    def update_baseline(self, trace: AgentTrace) -> Path:
        """Save a trace as the new baseline for its task."""
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_task_filename(trace.task)
        path = self.baseline_dir / f"{safe_name}.yaml"
        recorder = Recorder(task=trace.task)
        recorder.trace = trace
        recorder.save(path)
        return path


class RegressionEvaluator(Evaluator):
    """Evaluator wrapper for regression detection."""

    name = "regression"
    description = "Detects performance/cost/behavior regressions against baselines"

    def __init__(
        self,
        baseline_dir: str | Path,
        thresholds: RegressionThresholds | None = None,
    ) -> None:
        self.detector = RegressionDetector(baseline_dir, thresholds)

    def evaluate(self, trace: AgentTrace) -> EvalResult:
        result = self.detector.check(trace)

        if result.passed:
            score = 1.0
            message = "No regressions detected"
            if result.improvements:
                metrics = ", ".join(i.metric for i in result.improvements)
                message += f" (improvements: {metrics})"
        else:
            critical = [r for r in result.regressions if r.severity == "critical"]
            warnings = [r for r in result.regressions if r.severity == "warning"]
            score = max(0.0, 1.0 - 0.3 * len(critical) - 0.15 * len(warnings))
            parts = []
            for r in result.regressions:
                parts.append(f"{r.metric}: {r.change_pct:+.1%} (threshold: {r.threshold_pct:.1%})")
            message = "Regressions: " + "; ".join(parts)

        return EvalResult(
            evaluator=self.name,
            score=score,
            passed=result.passed,
            details={
                "regressions": [r.model_dump() for r in result.regressions],
                "improvements": [r.model_dump() for r in result.improvements],
            },
            message=message,
        )
