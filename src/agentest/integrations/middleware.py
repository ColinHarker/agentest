"""ASGI/WSGI middleware for auto-recording agent endpoint traces.

Usage with FastAPI:
    from agentest.integrations.middleware import instrument_fastapi

    app = FastAPI()
    instrument_fastapi(app, paths=["/api/agent", "/chat"], save_dir="traces/")

Usage with Flask:
    from agentest.integrations.middleware import instrument_flask

    app = Flask(__name__)
    instrument_flask(app, paths=["/api/agent"], save_dir="traces/")
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder


def _matches_path(
    request_path: str, paths: list[str] | None, exclude_paths: list[str] | None
) -> bool:
    """Check if a request path should be instrumented."""
    if exclude_paths:
        for ep in exclude_paths:
            if request_path.startswith(ep):
                return False
    if paths is None:
        return True
    return any(request_path.startswith(p) for p in paths)


class AgentestMiddleware:
    """ASGI middleware for FastAPI/Starlette that records agent endpoint traces.

    Wraps matching requests in a Recorder context. The trace captures request
    metadata and timing. Any LLM calls made during the request (via
    auto-instrumentation or manual recording) are captured in the trace.

    Usage:
        from fastapi import FastAPI
        from agentest.integrations.middleware import AgentestMiddleware

        app = FastAPI()
        app.add_middleware(
            AgentestMiddleware,
            paths=["/api/agent"],
            save_dir="traces/",
        )
    """

    def __init__(
        self,
        app: Any,
        paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        on_trace: Callable[[AgentTrace], None] | None = None,
        save_dir: str | Path | None = None,
    ) -> None:
        self.app = app
        self.paths = paths
        self.exclude_paths = exclude_paths
        self.on_trace = on_trace
        self.save_dir = Path(save_dir) if save_dir else None

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_path = scope.get("path", "")
        if not _matches_path(request_path, self.paths, self.exclude_paths):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        recorder = Recorder(
            task=f"{method} {request_path}",
            metadata={
                "method": method,
                "path": request_path,
                "query_string": scope.get("query_string", b"").decode("utf-8", errors="replace"),
            },
        )

        status_code = 200
        original_send = send

        async def capture_send(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await original_send(message)

        start = time.time()
        error_msg = None
        try:
            await self.app(scope, receive, capture_send)
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            latency_ms = (time.time() - start) * 1000
            success = error_msg is None and status_code < 500
            recorder.trace.metadata["status_code"] = status_code
            recorder.trace.metadata["latency_ms"] = latency_ms
            trace = recorder.finalize(success=success, error=error_msg)

            if self.on_trace:
                self.on_trace(trace)

            if self.save_dir:
                self.save_dir.mkdir(parents=True, exist_ok=True)
                trace_id = str(uuid.uuid4())[:8]
                recorder.save(self.save_dir / f"{trace_id}.yaml")


class FlaskAgentestMiddleware:
    """WSGI middleware for Flask that records agent endpoint traces.

    Usage:
        from flask import Flask
        from agentest.integrations.middleware import FlaskAgentestMiddleware

        app = Flask(__name__)
        app.wsgi_app = FlaskAgentestMiddleware(
            app.wsgi_app,
            paths=["/api/agent"],
            save_dir="traces/",
        )
    """

    def __init__(
        self,
        app: Any,
        paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        on_trace: Callable[[AgentTrace], None] | None = None,
        save_dir: str | Path | None = None,
    ) -> None:
        self.app = app
        self.paths = paths
        self.exclude_paths = exclude_paths
        self.on_trace = on_trace
        self.save_dir = Path(save_dir) if save_dir else None

    def __call__(self, environ: dict, start_response: Any) -> Iterable[bytes]:
        request_path = environ.get("PATH_INFO", "")
        if not _matches_path(request_path, self.paths, self.exclude_paths):
            return self.app(environ, start_response)

        method = environ.get("REQUEST_METHOD", "GET")
        recorder = Recorder(
            task=f"{method} {request_path}",
            metadata={
                "method": method,
                "path": request_path,
                "query_string": environ.get("QUERY_STRING", ""),
            },
        )

        status_code = 200
        captured_status = [None]

        def wrapped_start_response(status: str, headers: list, exc_info: Any = None) -> Any:
            nonlocal status_code
            try:
                status_code = int(status.split(" ", 1)[0])
            except (ValueError, IndexError):
                pass
            captured_status[0] = status
            return start_response(status, headers, exc_info)

        start = time.time()
        error_msg = None
        try:
            result = self.app(environ, wrapped_start_response)
            # Consume the iterable to ensure the response is complete
            body_parts = list(result)
            if hasattr(result, "close"):
                result.close()
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            latency_ms = (time.time() - start) * 1000
            success = error_msg is None and status_code < 500
            recorder.trace.metadata["status_code"] = status_code
            recorder.trace.metadata["latency_ms"] = latency_ms
            trace = recorder.finalize(success=success, error=error_msg)

            if self.on_trace:
                self.on_trace(trace)

            if self.save_dir:
                self.save_dir.mkdir(parents=True, exist_ok=True)
                trace_id = str(uuid.uuid4())[:8]
                recorder.save(self.save_dir / f"{trace_id}.yaml")

        return body_parts


def instrument_fastapi(app: Any, **kwargs: Any) -> None:
    """Add AgentestMiddleware to a FastAPI/Starlette app.

    Args:
        app: A FastAPI or Starlette application instance.
        **kwargs: Arguments passed to AgentestMiddleware (paths, exclude_paths,
            on_trace, save_dir).
    """
    app.add_middleware(AgentestMiddleware, **kwargs)


def instrument_flask(app: Any, **kwargs: Any) -> None:
    """Add FlaskAgentestMiddleware to a Flask app.

    Args:
        app: A Flask application instance.
        **kwargs: Arguments passed to FlaskAgentestMiddleware (paths, exclude_paths,
            on_trace, save_dir).
    """
    app.wsgi_app = FlaskAgentestMiddleware(app.wsgi_app, **kwargs)
