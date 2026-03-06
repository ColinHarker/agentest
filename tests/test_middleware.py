"""Tests for ASGI/WSGI middleware."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from agentest.core import AgentTrace
from agentest.integrations.middleware import (
    AgentestMiddleware,
    FlaskAgentestMiddleware,
    _matches_path,
)


class TestMatchesPath:
    def test_no_filters(self):
        assert _matches_path("/api/agent", None, None) is True

    def test_paths_match(self):
        assert _matches_path("/api/agent/run", ["/api/agent"], None) is True

    def test_paths_no_match(self):
        assert _matches_path("/api/other", ["/api/agent"], None) is False

    def test_exclude_paths(self):
        assert _matches_path("/api/health", None, ["/api/health"]) is False

    def test_exclude_takes_precedence(self):
        assert _matches_path("/api/agent", ["/api"], ["/api/agent"]) is False


class TestAgentestMiddleware:
    def test_non_http_passthrough(self):
        """Non-HTTP scopes are passed through."""
        calls = []

        async def app(scope, receive, send):
            calls.append(scope["type"])

        middleware = AgentestMiddleware(app)
        asyncio.get_event_loop().run_until_complete(middleware({"type": "websocket"}, None, None))
        assert calls == ["websocket"]

    def test_non_matching_path_passthrough(self):
        """Non-matching paths are passed through without recording."""
        calls = []

        async def app(scope, receive, send):
            calls.append(scope["path"])

        middleware = AgentestMiddleware(app, paths=["/api/agent"])
        asyncio.get_event_loop().run_until_complete(
            middleware({"type": "http", "path": "/health", "method": "GET"}, None, None)
        )
        assert calls == ["/health"]

    def test_records_trace(self):
        """Matching paths record a trace."""
        traces: list[AgentTrace] = []

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = AgentestMiddleware(
            app,
            paths=["/api/agent"],
            on_trace=traces.append,
        )

        async def receive():
            return {"type": "http.request", "body": b""}

        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        asyncio.get_event_loop().run_until_complete(
            middleware(
                {"type": "http", "path": "/api/agent/run", "method": "POST", "query_string": b""},
                receive,
                send,
            )
        )

        assert len(traces) == 1
        assert traces[0].task == "POST /api/agent/run"
        assert traces[0].success is True
        assert traces[0].metadata["status_code"] == 200

    def test_records_error(self):
        """Errors are captured in the trace."""
        traces: list[AgentTrace] = []

        async def app(scope, receive, send):
            raise ValueError("boom")

        middleware = AgentestMiddleware(app, paths=["/api"], on_trace=traces.append)

        try:
            asyncio.get_event_loop().run_until_complete(
                middleware(
                    {"type": "http", "path": "/api/run", "method": "GET", "query_string": b""},
                    None,
                    None,
                )
            )
        except ValueError:
            pass

        assert len(traces) == 1
        assert traces[0].success is False
        assert traces[0].error == "boom"

    def test_saves_to_dir(self):
        """Traces can be saved to a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:

            async def app(scope, receive, send):
                await send({"type": "http.response.start", "status": 200})
                await send({"type": "http.response.body", "body": b"ok"})

            middleware = AgentestMiddleware(app, save_dir=tmpdir)

            async def receive():
                return {"type": "http.request", "body": b""}

            async def send(msg):
                pass

            asyncio.get_event_loop().run_until_complete(
                middleware(
                    {"type": "http", "path": "/test", "method": "GET", "query_string": b""},
                    receive,
                    send,
                )
            )

            files = list(Path(tmpdir).glob("*.yaml"))
            assert len(files) == 1


class TestFlaskAgentestMiddleware:
    def test_non_matching_path_passthrough(self):
        """Non-matching paths pass through."""

        def app(environ, start_response):
            start_response("200 OK", [])
            return [b"ok"]

        middleware = FlaskAgentestMiddleware(app, paths=["/api/agent"])
        result = middleware({"PATH_INFO": "/health", "REQUEST_METHOD": "GET"}, MagicMock())
        assert result == [b"ok"]

    def test_records_trace(self):
        """Matching paths record a trace."""
        traces: list[AgentTrace] = []

        def app(environ, start_response):
            start_response("200 OK", [])
            return [b"response"]

        middleware = FlaskAgentestMiddleware(app, paths=["/api"], on_trace=traces.append)
        result = middleware(
            {"PATH_INFO": "/api/run", "REQUEST_METHOD": "POST", "QUERY_STRING": ""},
            MagicMock(),
        )
        assert result == [b"response"]
        assert len(traces) == 1
        assert traces[0].task == "POST /api/run"
        assert traces[0].success is True

    def test_records_error(self):
        """Errors are captured."""
        traces: list[AgentTrace] = []

        def app(environ, start_response):
            raise RuntimeError("fail")

        middleware = FlaskAgentestMiddleware(app, paths=["/api"], on_trace=traces.append)

        try:
            middleware(
                {"PATH_INFO": "/api/run", "REQUEST_METHOD": "GET", "QUERY_STRING": ""},
                MagicMock(),
            )
        except RuntimeError:
            pass

        assert len(traces) == 1
        assert traces[0].success is False

    def test_500_status_recorded(self):
        """500 status codes mark trace as failed."""
        traces: list[AgentTrace] = []

        def app(environ, start_response):
            start_response("500 Internal Server Error", [])
            return [b"error"]

        middleware = FlaskAgentestMiddleware(app, paths=["/api"], on_trace=traces.append)
        middleware(
            {"PATH_INFO": "/api/run", "REQUEST_METHOD": "GET", "QUERY_STRING": ""},
            MagicMock(),
        )
        assert len(traces) == 1
        assert traces[0].success is False
        assert traces[0].metadata["status_code"] == 500

    def test_saves_to_dir(self):
        """Traces can be saved to a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:

            def app(environ, start_response):
                start_response("200 OK", [])
                return [b"ok"]

            middleware = FlaskAgentestMiddleware(app, save_dir=tmpdir)
            middleware(
                {"PATH_INFO": "/test", "REQUEST_METHOD": "GET", "QUERY_STRING": ""},
                MagicMock(),
            )

            files = list(Path(tmpdir).glob("*.yaml"))
            assert len(files) == 1
