---
sidebar_position: 16
title: Middleware
---

# Middleware

ASGI/WSGI middleware for auto-recording agent endpoint traces.

## `AgentestMiddleware`

`agentest.integrations.middleware.AgentestMiddleware`

ASGI middleware for FastAPI/Starlette that records agent endpoint traces. Wraps matching requests in a Recorder context, capturing request metadata, timing, and status codes.

**Constructor:**

- `AgentestMiddleware(app: Any, paths: list[str] | None = None, exclude_paths: list[str] | None = None, on_trace: Callable[[AgentTrace], None] | None = None, save_dir: str | Path | None = None)`

| Parameter | Description |
|---|---|
| `app` | The ASGI application. |
| `paths` | URL path prefixes to instrument. `None` instruments all paths. |
| `exclude_paths` | URL path prefixes to exclude from instrumentation. |
| `on_trace` | Callback invoked with the completed `AgentTrace` after each request. |
| `save_dir` | Directory to save trace YAML files automatically. |

**Example:**

```python
from fastapi import FastAPI
from agentest.integrations.middleware import AgentestMiddleware

app = FastAPI()
app.add_middleware(
    AgentestMiddleware,
    paths=["/api/agent"],
    save_dir="traces/",
)
```

## `FlaskAgentestMiddleware`

`agentest.integrations.middleware.FlaskAgentestMiddleware`

WSGI middleware for Flask that records agent endpoint traces. Same parameter signature as `AgentestMiddleware`.

**Constructor:**

- `FlaskAgentestMiddleware(app: Any, paths: list[str] | None = None, exclude_paths: list[str] | None = None, on_trace: Callable[[AgentTrace], None] | None = None, save_dir: str | Path | None = None)`

**Example:**

```python
from flask import Flask
from agentest.integrations.middleware import FlaskAgentestMiddleware

app = Flask(__name__)
app.wsgi_app = FlaskAgentestMiddleware(
    app.wsgi_app,
    paths=["/api/agent"],
    save_dir="traces/",
)
```

## `instrument_fastapi`

`agentest.integrations.middleware.instrument_fastapi(app, **kwargs) -> None`

Convenience function that adds `AgentestMiddleware` to a FastAPI/Starlette app. Accepts the same keyword arguments as the middleware constructor (`paths`, `exclude_paths`, `on_trace`, `save_dir`).

```python
from agentest.integrations.middleware import instrument_fastapi

instrument_fastapi(app, paths=["/api/agent", "/chat"], save_dir="traces/")
```

## `instrument_flask`

`agentest.integrations.middleware.instrument_flask(app, **kwargs) -> None`

Convenience function that adds `FlaskAgentestMiddleware` to a Flask app. Accepts the same keyword arguments as the middleware constructor (`paths`, `exclude_paths`, `on_trace`, `save_dir`).

```python
from agentest.integrations.middleware import instrument_flask

instrument_flask(app, paths=["/api/agent"], save_dir="traces/")
```
