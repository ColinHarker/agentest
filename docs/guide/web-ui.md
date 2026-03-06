---
sidebar_position: 10
title: Web UI
---

# Web UI

Agentest includes a FastAPI-based web dashboard for exploring traces and running evaluations.

## Starting the UI

```bash
# Start the server
agentest serve --traces-dir traces/ --port 8000

# Or use the shortcut (also opens a browser)
agentest ui traces/
```

## API Endpoints

The web UI is backed by a REST API:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Main UI page |
| `GET` | `/api/traces` | List all traces with summaries |
| `GET` | `/api/traces/{id}` | Full trace details |
| `POST` | `/api/traces` | Save a new trace |
| `DELETE` | `/api/traces/{id}` | Delete a trace |
| `POST` | `/api/evaluate` | Run evaluators on a trace |
| `POST` | `/api/evaluate/batch` | Evaluate all traces |
| `GET` | `/api/dashboard` | Dashboard overview statistics |
| `POST` | `/api/diff` | Compare two traces |

## Programmatic Usage

```python
from agentest.server.app import create_app

app = create_app(traces_dir="my_traces/")
# Use with uvicorn or any ASGI server
```
