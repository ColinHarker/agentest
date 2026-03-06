"""Record agent sessions for replay and evaluation."""

from __future__ import annotations

import inspect
import json
import time
from pathlib import Path
from typing import Any

import yaml

from agentest.core import AgentTrace, LLMResponse, Message, Role, ToolCall


class Recorder:
    """Records agent interactions into reproducible traces.

    Usage:
        recorder = Recorder(task="Summarize this document")

        # Record LLM calls
        recorder.record_llm_response(model="claude-sonnet-4-6", content="...", ...)

        # Record tool calls
        recorder.record_tool_call(name="read_file", arguments={"path": "doc.txt"}, result="...")

        # Save the trace
        recorder.save("traces/my_trace.yaml")
    """

    def __init__(self, task: str = "", metadata: dict[str, Any] | None = None) -> None:
        self.trace = AgentTrace(task=task, metadata=metadata or {})
        self._active = True
        self._pending_tool_calls: dict[str, int] = {}  # tool_use_id -> index in tool_calls

    def record_message(self, role: str | Role, content: str) -> Message:
        """Record a conversation message."""
        if isinstance(role, str):
            role = Role(role)
        msg = Message(role=role, content=content)
        self.trace.messages.append(msg)
        return msg

    def record_llm_response(
        self,
        model: str,
        content: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0,
        raw: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Record an LLM response."""
        response = LLMResponse(
            model=model,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            raw=raw or {},
        )
        self.trace.llm_responses.append(response)
        return response

    def record_tool_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        result: Any = None,
        error: str | None = None,
        duration_ms: float | None = None,
    ) -> ToolCall:
        """Record a tool call and its result."""
        tool_call = ToolCall(
            name=name,
            arguments=arguments or {},
            result=result,
            error=error,
            duration_ms=duration_ms,
        )
        self.trace.tool_calls.append(tool_call)
        return tool_call

    def __enter__(self) -> Recorder:
        """Start recording as a context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Finalize recording on context exit."""
        if self._active:
            if exc_type is not None:
                self.finalize(success=False, error=str(exc_val))
            else:
                self.finalize(success=True)

    async def __aenter__(self) -> Recorder:
        """Start recording as an async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Finalize recording on async context exit."""
        self.__exit__(exc_type, exc_val, exc_tb)

    def wrap_tool(self, name: str, func: Any) -> Any:
        """Wrap a tool function to automatically record its calls.

        Usage:
            def read_file(path: str) -> str:
                return open(path).read()

            read_file = recorder.wrap_tool("read_file", read_file)
            result = read_file(path="doc.txt")  # automatically recorded
        """

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            # Normalize positional args to named kwargs for recording
            try:
                sig = inspect.signature(func)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                recorded_args = dict(bound.arguments)
            except (ValueError, TypeError):
                recorded_args = {**{f"arg{i}": v for i, v in enumerate(args)}, **kwargs}
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                self.record_tool_call(
                    name=name, arguments=recorded_args, result=result, duration_ms=duration
                )
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                self.record_tool_call(
                    name=name, arguments=recorded_args, error=str(e), duration_ms=duration
                )
                raise

        return wrapper

    def record_tool_result(self, tool_use_id: str, result: Any) -> None:
        """Backfill the result for a previously recorded tool call by its tool_use_id."""
        if tool_use_id in self._pending_tool_calls:
            idx = self._pending_tool_calls.pop(tool_use_id)
            if 0 <= idx < len(self.trace.tool_calls):
                self.trace.tool_calls[idx].result = result

    def finalize(self, success: bool = True, error: str | None = None) -> AgentTrace:
        """Finalize the recording and return the trace."""
        self.trace.finalize(success=success, error=error)
        self._active = False
        return self.trace

    def save(self, path: str | Path, format: str = "yaml") -> Path:
        """Save the trace to a file.

        Args:
            path: File path to save to.
            format: 'yaml' or 'json'.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = self.trace.model_dump(mode="json")

        if format == "yaml":
            path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
        elif format == "json":
            path.write_text(json.dumps(data, indent=2))
        else:
            raise ValueError(f"Unknown format: {format}. Use 'yaml' or 'json'.")

        return path

    @staticmethod
    def load(path: str | Path) -> AgentTrace:
        """Load a trace from a file."""
        path = Path(path)
        text = path.read_text()

        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(text)
        elif path.suffix == ".json":
            data = json.loads(text)
        else:
            # Try YAML first, then JSON
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError:
                data = json.loads(text)

        return AgentTrace.model_validate(data)
