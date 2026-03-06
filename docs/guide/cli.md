---
sidebar_position: 9
title: CLI Reference
---

# CLI Reference

All commands are available via the `agentest` CLI.

## `agentest init`

Initialize Agentest in the current project. Creates `traces/` and `tests/agent_tests/` directories with sample test files.

```bash
agentest init
```

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

Convenience alias — starts the server and opens a browser.

```bash
agentest ui traces/ --port 8000
```
