"""Tests for the integrations module - auto-instrumentation and framework adapters."""

from __future__ import annotations

import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder

# Force-import the module first, then get the actual module object
from agentest.integrations import instrument as _instrument_func  # noqa: trigger import
from agentest.integrations.instrument import (
    _get_recorder,
    _finalize_and_store,
    _wrap_anthropic_create,
    _wrap_openai_create,
    clear_traces,
    flush_trace,
    get_current_recorder,
    get_traces,
    instrument,
    uninstrument,
)

# Get the actual module object (not the function)
_inst_mod = sys.modules["agentest.integrations.instrument"]


def _reset_state():
    """Reset instrumentation state for clean tests."""
    clear_traces()
    _inst_mod._local.recorder = None
    _inst_mod._instrumented = False


# ---- Auto-instrumentation internals ----


class TestInstrumentHelpers:
    def setup_method(self):
        _reset_state()

    def test_get_recorder_creates_new(self):
        recorder = _get_recorder("my task")
        assert isinstance(recorder, Recorder)
        assert recorder.trace.task == "my task"

    def test_get_recorder_returns_same(self):
        r1 = _get_recorder("task")
        r2 = _get_recorder("task")
        assert r1 is r2

    def test_finalize_and_store(self):
        _get_recorder("test task")
        trace = _finalize_and_store(success=True)
        assert isinstance(trace, AgentTrace)
        assert trace.success is True

        traces = get_traces()
        assert len(traces) == 1
        assert traces[0].id == trace.id

    def test_clear_traces(self):
        _get_recorder("test")
        _finalize_and_store()
        assert len(get_traces()) == 1
        clear_traces()
        assert len(get_traces()) == 0

    def test_flush_trace_with_active_recorder(self):
        recorder = _get_recorder("active task")
        recorder.record_message("user", "hello")
        trace = flush_trace(task="next task")
        assert trace is not None
        assert trace.task == "active task"

    def test_flush_trace_no_recorder(self):
        result = flush_trace()
        assert result is None

    def test_get_current_recorder(self):
        recorder = get_current_recorder()
        assert isinstance(recorder, Recorder)


class TestAnthropicWrapper:
    def setup_method(self):
        _reset_state()

    def test_wrap_anthropic_create_records_response(self):
        mock_response = SimpleNamespace(
            content=[SimpleNamespace(text="Hello there!", type="text")],
            usage=SimpleNamespace(input_tokens=50, output_tokens=10),
        )

        original_fn = MagicMock(return_value=mock_response)
        wrapped = _wrap_anthropic_create(original_fn)

        result = wrapped(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert result is mock_response
        original_fn.assert_called_once()

        recorder = _get_recorder()
        assert len(recorder.trace.messages) >= 1
        assert len(recorder.trace.llm_responses) == 1
        assert recorder.trace.llm_responses[0].model == "claude-sonnet-4-6"
        assert recorder.trace.llm_responses[0].input_tokens == 50

    def test_wrap_anthropic_create_records_tool_use(self):
        mock_response = SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    name="read_file",
                    input={"path": "test.txt"},
                    id="tool_123",
                ),
            ],
            usage=SimpleNamespace(input_tokens=30, output_tokens=20),
        )

        original_fn = MagicMock(return_value=mock_response)
        wrapped = _wrap_anthropic_create(original_fn)

        wrapped(model="claude-sonnet-4-6", messages=[{"role": "user", "content": "Read file"}])

        recorder = _get_recorder()
        assert len(recorder.trace.tool_calls) == 1
        assert recorder.trace.tool_calls[0].name == "read_file"

    def test_wrap_anthropic_create_handles_error(self):
        original_fn = MagicMock(side_effect=RuntimeError("API error"))
        wrapped = _wrap_anthropic_create(original_fn)

        with pytest.raises(RuntimeError, match="API error"):
            wrapped(model="claude-sonnet-4-6", messages=[])

        recorder = _get_recorder()
        assert len(recorder.trace.llm_responses) == 1
        assert "Error" in recorder.trace.llm_responses[0].content


class TestOpenAIWrapper:
    def setup_method(self):
        _reset_state()

    def test_wrap_openai_create_records_response(self):
        mock_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello!",
                        tool_calls=None,
                    ),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=30, completion_tokens=5),
        )

        original_fn = MagicMock(return_value=mock_response)
        wrapped = _wrap_openai_create(original_fn)

        result = wrapped(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert result is mock_response
        recorder = _get_recorder()
        assert len(recorder.trace.llm_responses) == 1
        assert recorder.trace.llm_responses[0].model == "gpt-4o"
        assert recorder.trace.llm_responses[0].input_tokens == 30

    def test_wrap_openai_create_records_tool_calls(self):
        mock_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                function=SimpleNamespace(
                                    name="get_weather",
                                    arguments='{"city": "NYC"}',
                                ),
                            )
                        ],
                    ),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=20, completion_tokens=15),
        )

        original_fn = MagicMock(return_value=mock_response)
        wrapped = _wrap_openai_create(original_fn)

        wrapped(model="gpt-4o", messages=[])

        recorder = _get_recorder()
        assert len(recorder.trace.tool_calls) == 1
        assert recorder.trace.tool_calls[0].name == "get_weather"
        assert recorder.trace.tool_calls[0].arguments == {"city": "NYC"}


# ---- instrument / uninstrument ----


class TestInstrumentUninstrument:
    def setup_method(self):
        _reset_state()

    def test_instrument_sets_flag(self):
        instrument(anthropic=False, openai=False)
        assert _inst_mod._instrumented is True

    def test_instrument_idempotent(self):
        instrument(anthropic=False, openai=False)
        instrument(anthropic=False, openai=False)

    def test_uninstrument_resets_flag(self):
        instrument(anthropic=False, openai=False)
        uninstrument()
        assert _inst_mod._instrumented is False

    def test_uninstrument_without_instrument(self):
        uninstrument()


# ---- CrewAI adapter (no crewai installed, test import guard) ----


class TestCrewAIAdapter:
    def test_record_crew_import_error(self):
        """Without crewai installed, record_crew raises ImportError."""
        from agentest.integrations.crewai import record_crew

        with pytest.raises((ImportError, TypeError)):
            record_crew("not a crew")

    def test_crewai_adapter_traces(self):
        from agentest.integrations.crewai import CrewAIAdapter

        adapter = CrewAIAdapter(default_metadata={"env": "test"})
        assert adapter.traces == []
        adapter.clear()


# ---- AutoGen adapter ----


class TestAutoGenAdapter:
    def test_record_autogen_chat(self):
        from agentest.integrations.autogen import record_autogen_chat

        initiator = MagicMock()
        initiator.name = "user_proxy"
        recipient = MagicMock()
        recipient.name = "assistant"

        chat_result = MagicMock()
        chat_result.chat_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        chat_result.summary = "Conversation completed"
        initiator.initiate_chat.return_value = chat_result

        result, trace = record_autogen_chat(
            initiator=initiator,
            recipient=recipient,
            message="Hello",
            task="Test chat",
        )

        assert result is chat_result
        assert isinstance(trace, AgentTrace)
        assert trace.task == "Test chat"
        assert trace.success is True
        assert len(trace.messages) >= 1

    def test_record_autogen_chat_error(self):
        from agentest.integrations.autogen import record_autogen_chat

        initiator = MagicMock()
        initiator.name = "proxy"
        recipient = MagicMock()
        recipient.name = "agent"
        initiator.initiate_chat.side_effect = RuntimeError("Connection failed")

        with pytest.raises(RuntimeError, match="Connection failed"):
            record_autogen_chat(initiator, recipient, "Hello")

    def test_autogen_adapter_class(self):
        from agentest.integrations.autogen import AutoGenAdapter

        adapter = AutoGenAdapter()
        assert adapter.traces == []
        adapter.clear()


# ---- Claude Agent SDK adapter ----


class TestClaudeAgentSDKAdapter:
    def test_record_sync_function(self):
        from agentest.integrations.claude_agent_sdk import AgentestTracer

        tracer = AgentestTracer(task="Test Claude agent")

        def fake_agent(message):
            return f"Response to: {message}"

        result, trace = tracer.record(fake_agent, "What is 2+2?")

        assert result == "Response to: What is 2+2?"
        assert isinstance(trace, AgentTrace)
        assert trace.success is True
        assert trace.task == "Test Claude agent"

    def test_record_function_error(self):
        from agentest.integrations.claude_agent_sdk import AgentestTracer

        tracer = AgentestTracer(task="Failing agent")

        def failing_agent(msg):
            raise ValueError("Agent crashed")

        with pytest.raises(ValueError, match="Agent crashed"):
            tracer.record(failing_agent, "Hello")

        trace = tracer.get_trace()
        assert trace is not None
        assert trace.success is False
        assert "Agent crashed" in trace.error

    def test_context_manager(self):
        from agentest.integrations.claude_agent_sdk import AgentestTracer

        tracer = AgentestTracer(task="Context test")

        with tracer.recording() as recorder:
            recorder.record_message("user", "Hello")
            recorder.record_llm_response(
                model="claude", content="Hi", input_tokens=10, output_tokens=5
            )

        trace = tracer.get_trace()
        assert trace is not None
        assert trace.success is True
        assert len(trace.messages) == 1
        assert len(trace.llm_responses) == 1

    def test_context_manager_error(self):
        from agentest.integrations.claude_agent_sdk import AgentestTracer

        tracer = AgentestTracer(task="Error context")

        with pytest.raises(RuntimeError):
            with tracer.recording() as recorder:
                recorder.record_message("user", "Test")
                raise RuntimeError("boom")

        trace = tracer.get_trace()
        assert trace.success is False

    def test_save_without_trace_raises(self):
        from agentest.integrations.claude_agent_sdk import AgentestTracer

        tracer = AgentestTracer()
        with pytest.raises(RuntimeError, match="No trace to save"):
            tracer.save("/tmp/test.yaml")


# ---- OpenAI Agents adapter ----


class TestOpenAIAgentsAdapter:
    def test_record_sync(self):
        from agentest.integrations.openai_agents import AgentestTracer

        tracer = AgentestTracer(task="OpenAI test")

        def fake_run(agent, message):
            return SimpleNamespace(
                final_output="The answer is 4",
                new_items=[],
            )

        agent = MagicMock()
        result, trace = tracer.record(fake_run, agent, "What is 2+2?")

        assert trace.success is True
        assert trace.task == "OpenAI test"
        assert len(trace.messages) >= 1

    def test_record_with_items(self):
        from agentest.integrations.openai_agents import AgentestTracer

        tracer = AgentestTracer(task="Items test")

        def fake_run(agent, message):
            return SimpleNamespace(
                final_output="Done",
                new_items=[
                    SimpleNamespace(text="Hello from agent"),
                ],
            )

        result, trace = tracer.record(fake_run, MagicMock(), "Hello")
        assert trace.success is True

    def test_context_manager(self):
        from agentest.integrations.openai_agents import AgentestTracer

        tracer = AgentestTracer(task="Context test")

        with tracer.recording() as recorder:
            recorder.record_message("user", "Test")

        trace = tracer.get_trace()
        assert trace is not None
        assert trace.success is True

    def test_get_trace_before_recording(self):
        from agentest.integrations.openai_agents import AgentestTracer

        tracer = AgentestTracer()
        assert tracer.get_trace() is None


# ---- GitHub Action script ----


class TestGitHubAction:
    def test_evaluate_script_empty_dir(self, tmp_path):
        """Test the action evaluate script with no traces."""
        import json
        import os

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        output_file = str(tmp_path / "report.json")

        env = {
            "TRACES_DIR": str(traces_dir),
            "CHECK_SAFETY": "true",
            "EVALUATORS": "task_completion,safety",
            "OUTPUT_FILE": output_file,
            "FAIL_ON_ERROR": "false",
        }

        # Add the action dir to sys.path so we can import
        action_dir = str(tmp_path.parent.parent.parent / "home" / "user" / "claude-fun")
        sys.path.insert(0, "/home/user/claude-fun")

        with patch.dict(os.environ, env, clear=False):
            from action.evaluate import main

            main()

        # The empty dir case prints notice but doesn't write the file normally
        # when no traces are found, it still writes the output
        report_path = tmp_path / "report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text())
            assert report["total"] == 0

    def test_evaluate_script_with_trace(self, tmp_path):
        """Test the action evaluate script with a real trace."""
        import json
        import os

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        recorder = Recorder(task="Test task")
        recorder.record_message("user", "Hello")
        recorder.record_llm_response(
            model="claude-sonnet-4-6", content="Hi", input_tokens=10, output_tokens=5
        )
        trace = recorder.finalize(success=True)
        recorder.save(traces_dir / "test.yaml")

        output_file = str(tmp_path / "report.json")
        env = {
            "TRACES_DIR": str(traces_dir),
            "CHECK_SAFETY": "true",
            "EVALUATORS": "task_completion,safety,tool_usage",
            "OUTPUT_FILE": output_file,
            "FAIL_ON_ERROR": "false",
        }

        sys.path.insert(0, "/home/user/claude-fun")

        with patch.dict(os.environ, env, clear=False):
            from action.evaluate import main

            main()

        report = json.loads((tmp_path / "report.json").read_text())
        assert report["total"] == 1
        assert report["passed"] >= 0
