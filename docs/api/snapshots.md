---
sidebar_position: 14
title: Snapshots
---

# Snapshots

Jest-like trace snapshot system for CI regression testing.

## `SnapshotConfig`

`agentest.snapshots.SnapshotConfig`

Thresholds and settings for snapshot comparison. Pydantic model with fields:

- `cost_threshold_pct` (float, default `10.0`) — Maximum allowed cost change percentage.
- `latency_threshold_pct` (float, default `20.0`) — Maximum allowed latency change percentage.
- `token_threshold_pct` (float, default `15.0`) — Maximum allowed token change percentage.
- `tool_sequence_must_match` (bool, default `True`) — Whether tool call sequences must match exactly.
- `allow_new_tools` (bool, default `False`) — Whether new tool calls are permitted.

## `SnapshotResult`

`agentest.snapshots.SnapshotResult`

Result of comparing a trace against a saved snapshot. Pydantic model with fields: `task` (str), `passed` (bool), `structural_match` (bool), `metric_diffs` (dict with `cost`, `latency`, `tokens` sub-dicts containing `baseline`, `current`, `change_pct`), `added_tools` (list of str), `removed_tools` (list of str), `message` (str).

## `SnapshotManager`

`agentest.snapshots.SnapshotManager`

Manages golden snapshots for regression testing agent traces.

**Constructor:**

- `SnapshotManager(snapshot_dir: Path, config: SnapshotConfig | None = None)` — Creates the snapshot directory if it does not exist.

**Methods:**

- `save_snapshot(trace: AgentTrace) -> Path` — Save a trace as the golden snapshot for its task.
- `update(trace: AgentTrace) -> Path` — Overwrite the existing snapshot for a task (or create if missing). Alias for `save_snapshot`.
- `check(trace: AgentTrace) -> SnapshotResult` — Compare a trace against its saved snapshot. Checks tool sequence structure, cost, latency, and token thresholds.
- `check_all(traces_dir: Path) -> list[SnapshotResult]` — Load all traces from a directory and check each against its snapshot.
- `list_snapshots() -> list[str]` — List task names for all saved snapshots.

**Example:**

```python
from pathlib import Path
from agentest.snapshots import SnapshotManager, SnapshotConfig

manager = SnapshotManager(
    snapshot_dir=Path("snapshots/"),
    config=SnapshotConfig(cost_threshold_pct=15.0),
)

# Save a golden snapshot
manager.save_snapshot(trace)

# Later, check a new trace against the snapshot
result = manager.check(new_trace)
if not result.passed:
    print(result.message)  # e.g. "cost change +18.2% exceeds 15.0%"
```
