---
sidebar_position: 9
title: CLI Reference
---

# CLI Reference

All commands are available via the `agentest` CLI.

## `agentest evaluate`

Evaluate a recorded trace file.

```bash
agentest evaluate traces/my_trace.yaml \
    --max-cost 0.50 \
    --max-tokens 100000 \
    --max-time-ms 30000 \
    --check-safety \
    -o report.json
```

Exits with code 1 if any evaluator fails.

## `agentest replay`

Replay a trace and display its interactions.

```bash
agentest replay traces/my_trace.yaml --strict
```

## `agentest summary`

Summarize all traces in a directory.

```bash
agentest summary traces/ --format table
agentest summary traces/ --format json
```

## `agentest diff`

Compare two traces side by side.

```bash
agentest diff traces/v1.yaml traces/v2.yaml --format table
```

Shows deltas for tokens, cost, duration, tool call sequence, and errors.

## `agentest watch`

Continuously monitor a traces directory and re-evaluate on changes.

```bash
agentest watch traces/ \
    --interval 2.0 \
    --max-cost 0.50 \
    --check-safety
```

Press `Ctrl+C` to stop.

## `agentest serve`

Start the web UI dashboard.

```bash
agentest serve \
    --host 127.0.0.1 \
    --port 8000 \
    --traces-dir traces/ \
    --reload
```

## `agentest ui`

Convenience alias -- starts the server and opens a browser.

```bash
agentest ui traces/ --port 8000
```

## `agentest doctor`

Check your Agentest setup and report issues. Verifies:

- **SDK availability** -- checks whether `anthropic` and `openai` are installed and reports versions
- **Optional extras** -- checks for `opentelemetry`, `flask`, and `fastapi`
- **Traces directory** -- reports whether `traces/` exists and how many trace files it contains
- **Pytest plugin** -- checks if the Agentest pytest plugin is registered
- **Snapshots** -- checks for `.agentest/snapshots/` and reports count

```bash
agentest doctor
```

## `agentest init`

Initialize Agentest in the current project. Creates `traces/` and `tests/agent_tests/` directories with a sample test file and conftest.

Framework detection is automatic: the command checks for installed packages in the following order -- `langchain_core`, `crewai`, `anthropic`, `openai` -- and generates tailored test templates for the first match. If none are found, a generic template is used.

```bash
agentest init
```

## `agentest regression`

Detect regressions by comparing traces against baselines. Exits with code 1 if any task fails its regression checks.

```bash
agentest regression traces/ \
    --baseline baselines/ \
    --cost-threshold 0.1 \
    --token-threshold 0.1 \
    --latency-threshold 0.2 \
    --format table
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--baseline` | `PATH` | *(required)* | Baseline directory to compare against. |
| `--update-baseline` | flag | `false` | Update baselines with current traces after comparison. |
| `--cost-threshold` | `FLOAT` | `0.1` | Cost regression threshold (0.1 = 10%). |
| `--token-threshold` | `FLOAT` | `0.1` | Token regression threshold. |
| `--latency-threshold` | `FLOAT` | `0.2` | Latency regression threshold (0.2 = 20%). |
| `--format` | `table\|json` | `table` | Output format. |

## `agentest stats`

Analyze performance statistics from run history. Supports trend analysis, confidence intervals, and SLO compliance checks.

```bash
agentest stats history.json \
    --task "Summarize document" \
    --trend \
    --ci \
    --slo cost:0.5:lte \
    --format table
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--task` | `TEXT` | *(all tasks)* | Filter to a specific task. |
| `--trend` | flag | `false` | Show trend analysis (direction, slope, R-squared) for score, cost, tokens, and latency. |
| `--ci` | flag | `false` | Show 95% confidence intervals for score, cost, and tokens. |
| `--slo` | `TEXT` (multiple) | -- | SLO definition in `metric:target:comparison` format (e.g., `cost:0.5:lte`). Can be specified multiple times. |
| `--format` | `table\|json` | `table` | Output format. |

## `agentest dataset`

Manage test datasets. Has three subcommands: `create`, `list`, and `split`.

### `agentest dataset create`

Create a new empty dataset.

```bash
agentest dataset create my_dataset \
    --output datasets/my_dataset.yaml \
    --description "End-to-end test cases"
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output`, `-o` | `PATH` | `datasets/<name>.yaml` | Output file path. |
| `--description`, `-d` | `TEXT` | `""` | Dataset description. |

### `agentest dataset list`

List test cases in a dataset.

```bash
agentest dataset list datasets/my_dataset.yaml
```

Takes a single `PATH` argument pointing to the dataset file.

### `agentest dataset split`

Split a dataset into two groups for A/B testing.

```bash
agentest dataset split datasets/my_dataset.yaml \
    --ratio 0.5 \
    --seed 42 \
    --output-dir datasets/
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--ratio` | `FLOAT` | `0.5` | Split ratio for group A. |
| `--seed` | `INT` | `42` | Random seed for reproducibility. |
| `--output-dir`, `-o` | `PATH` | *(same dir as input)* | Output directory for the split files. |

## `agentest snapshot`

Manage trace snapshots for CI regression testing. Has three subcommands: `save`, `check`, and `check-dir`.

### `agentest snapshot save`

Save a trace as a golden snapshot.

```bash
agentest snapshot save traces/my_trace.yaml \
    --snapshot-dir snapshots
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--snapshot-dir` | `PATH` | `snapshots` | Directory to store snapshots in. |

### `agentest snapshot check`

Check a trace against its saved snapshot. Exits with code 1 if the check fails.

```bash
agentest snapshot check traces/my_trace.yaml \
    --snapshot-dir snapshots \
    --cost-threshold 10.0 \
    --latency-threshold 20.0 \
    --token-threshold 15.0 \
    --update
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--snapshot-dir` | `PATH` | `snapshots` | Snapshot directory. |
| `--update` | flag | `false` | Update the snapshot if the check fails. |
| `--cost-threshold` | `FLOAT` | `10.0` | Cost threshold in percent. |
| `--latency-threshold` | `FLOAT` | `20.0` | Latency threshold in percent. |
| `--token-threshold` | `FLOAT` | `15.0` | Token threshold in percent. |

### `agentest snapshot check-dir`

Check all traces in a directory against saved snapshots. Exits with code 1 if any check fails.

```bash
agentest snapshot check-dir traces/ \
    --snapshot-dir snapshots \
    --format table
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--snapshot-dir` | `PATH` | `snapshots` | Snapshot directory. |
| `--format` | `table\|json` | `table` | Output format. |
