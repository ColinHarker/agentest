"""Jest-like trace snapshot system for CI regression testing."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from agentest.core import AgentTrace


class SnapshotConfig(BaseModel):
    """Thresholds and settings for snapshot comparison."""

    cost_threshold_pct: float = 10.0
    latency_threshold_pct: float = 20.0
    token_threshold_pct: float = 15.0
    tool_sequence_must_match: bool = True
    allow_new_tools: bool = False


class SnapshotResult(BaseModel):
    """Result of comparing a trace against a saved snapshot."""

    task: str
    passed: bool
    structural_match: bool
    metric_diffs: dict[str, dict[str, float]] = Field(default_factory=dict)
    added_tools: list[str] = Field(default_factory=list)
    removed_tools: list[str] = Field(default_factory=list)
    message: str = ""


def _sanitize_task_name(task: str) -> str:
    """Replace non-alphanumeric characters with underscores for filenames."""
    return re.sub(r"[^a-zA-Z0-9]", "_", task)


def _pct_change(baseline: float, current: float) -> float:
    """Compute percentage change from baseline to current."""
    if baseline == 0:
        return 0.0
    return (current - baseline) / baseline * 100


class SnapshotManager:
    """Manages golden snapshots for regression testing agent traces."""

    def __init__(self, snapshot_dir: Path, config: SnapshotConfig | None = None) -> None:
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or SnapshotConfig()

    def _snapshot_path(self, task: str) -> Path:
        """Return the file path for a given task's snapshot."""
        return self.snapshot_dir / f"{_sanitize_task_name(task)}.yaml"

    def save_snapshot(self, trace: AgentTrace) -> Path:
        """Save a trace as the golden snapshot for its task."""
        path = self._snapshot_path(trace.task)
        data = trace.model_dump(mode="json")
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
        return path

    def update(self, trace: AgentTrace) -> Path:
        """Overwrite the existing snapshot for a task (or create if missing)."""
        return self.save_snapshot(trace)

    def check(self, trace: AgentTrace) -> SnapshotResult:
        """Compare a trace against its saved snapshot.

        Returns a SnapshotResult indicating whether the trace passes
        all configured thresholds and structural checks.
        """
        path = self._snapshot_path(trace.task)

        if not path.exists():
            return SnapshotResult(
                task=trace.task,
                passed=False,
                structural_match=False,
                message="No snapshot found",
            )

        baseline = AgentTrace.model_validate(yaml.safe_load(path.read_text()))

        # --- Structural comparison (tool call name sequences) ---
        baseline_tool_names = [tc.name for tc in baseline.tool_calls]
        current_tool_names = [tc.name for tc in trace.tool_calls]
        structural_match = baseline_tool_names == current_tool_names

        # Frequency-aware tool diff using Counter
        baseline_counts = Counter(baseline_tool_names)
        current_counts = Counter(current_tool_names)
        added_tools = list((current_counts - baseline_counts).elements())
        removed_tools = list((baseline_counts - current_counts).elements())

        # --- Metric diffs ---
        metric_diffs: dict[str, dict[str, float]] = {}

        baseline_cost = baseline.total_cost
        current_cost = trace.total_cost
        metric_diffs["cost"] = {
            "baseline": baseline_cost,
            "current": current_cost,
            "change_pct": _pct_change(baseline_cost, current_cost),
        }

        baseline_duration = baseline.duration_ms or 0.0
        current_duration = trace.duration_ms or 0.0
        metric_diffs["latency"] = {
            "baseline": baseline_duration,
            "current": current_duration,
            "change_pct": _pct_change(baseline_duration, current_duration),
        }

        baseline_tokens = float(baseline.total_tokens)
        current_tokens = float(trace.total_tokens)
        metric_diffs["tokens"] = {
            "baseline": baseline_tokens,
            "current": current_tokens,
            "change_pct": _pct_change(baseline_tokens, current_tokens),
        }

        # --- Pass / fail logic ---
        cost_ok = abs(metric_diffs["cost"]["change_pct"]) <= self.config.cost_threshold_pct
        latency_ok = abs(metric_diffs["latency"]["change_pct"]) <= self.config.latency_threshold_pct
        tokens_ok = abs(metric_diffs["tokens"]["change_pct"]) <= self.config.token_threshold_pct

        structure_ok = True
        if self.config.tool_sequence_must_match and not structural_match:
            structure_ok = False
        if not self.config.allow_new_tools and len(added_tools) > 0:
            structure_ok = False

        passed = structure_ok and cost_ok and latency_ok and tokens_ok

        # Build human-readable message
        failures: list[str] = []
        if not structure_ok:
            failures.append("tool sequence mismatch")
        if not cost_ok:
            cost_pct = metric_diffs["cost"]["change_pct"]
            failures.append(
                f"cost change {cost_pct:+.1f}% exceeds {self.config.cost_threshold_pct}%"
            )
        if not latency_ok:
            lat_pct = metric_diffs["latency"]["change_pct"]
            failures.append(
                f"latency change {lat_pct:+.1f}% exceeds {self.config.latency_threshold_pct}%"
            )
        if not tokens_ok:
            tok_pct = metric_diffs["tokens"]["change_pct"]
            failures.append(
                f"token change {tok_pct:+.1f}% exceeds {self.config.token_threshold_pct}%"
            )

        message = "OK" if passed else "; ".join(failures)

        return SnapshotResult(
            task=trace.task,
            passed=passed,
            structural_match=structural_match,
            metric_diffs=metric_diffs,
            added_tools=added_tools,
            removed_tools=removed_tools,
            message=message,
        )

    def check_all(self, traces_dir: Path) -> list[SnapshotResult]:
        """Load all traces from a directory and check each against its snapshot."""
        traces_dir = Path(traces_dir)
        results: list[SnapshotResult] = []

        for trace_path in sorted(traces_dir.iterdir()):
            if trace_path.suffix not in (".yaml", ".yml", ".json"):
                continue
            text = trace_path.read_text()
            if trace_path.suffix == ".json":
                data = json.loads(text)
            else:
                data = yaml.safe_load(text)
            trace = AgentTrace.model_validate(data)
            results.append(self.check(trace))

        return results

    def list_snapshots(self) -> list[str]:
        """List task names for all saved snapshots."""
        tasks: list[str] = []
        for path in sorted(self.snapshot_dir.iterdir()):
            if path.suffix not in (".yaml", ".yml"):
                continue
            data = yaml.safe_load(path.read_text())
            trace = AgentTrace.model_validate(data)
            tasks.append(trace.task)
        return tasks
