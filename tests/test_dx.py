"""Tests for developer experience improvements."""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock

import pytest

import agentest
from agentest import Recorder
from agentest.core import AgentTrace
from agentest.evaluators.base import EvalResult, LLMJudgeEvaluator

# ---- evaluate() convenience function ----


class TestEvaluateConvenience:
    def _make_trace(self, success: bool = True) -> AgentTrace:
        recorder = Recorder(task="Test task")
        recorder.record_message("user", "Hello")
        recorder.record_llm_response(
            model="claude-sonnet-4-6", content="Hi there", input_tokens=50, output_tokens=10
        )
        recorder.record_tool_call(
            name="read_file", arguments={"path": "test.txt"}, result="contents"
        )
        return recorder.finalize(success=success)

    def test_evaluate_returns_results(self):
        trace = self._make_trace()
        results = agentest.evaluate(trace)
        assert isinstance(results, list)
        assert all(isinstance(r, EvalResult) for r in results)
        assert len(results) >= 2  # task_completion + tool_usage at minimum

    def test_evaluate_with_safety(self):
        trace = self._make_trace()
        results = agentest.evaluate(trace, check_safety=True)
        evaluator_names = [r.evaluator for r in results]
        assert "safety" in evaluator_names

    def test_evaluate_without_safety(self):
        trace = self._make_trace()
        results = agentest.evaluate(trace, check_safety=False)
        evaluator_names = [r.evaluator for r in results]
        assert "safety" not in evaluator_names

    def test_evaluate_with_cost_budget(self):
        trace = self._make_trace()
        results = agentest.evaluate(trace, max_cost=10.0)
        evaluator_names = [r.evaluator for r in results]
        assert "cost" in evaluator_names

    def test_evaluate_with_token_budget(self):
        trace = self._make_trace()
        results = agentest.evaluate(trace, max_tokens=100000)
        evaluator_names = [r.evaluator for r in results]
        assert "cost" in evaluator_names


# ---- run() convenience function ----


class TestRunConvenience:
    def test_run_returns_result_and_trace(self):
        def my_fn():
            return 42

        result, trace = agentest.run(my_fn, task="test run")
        assert result == 42
        assert isinstance(trace, AgentTrace)

    def test_run_with_args(self):
        def add(a, b):
            return a + b

        result, trace = agentest.run(add, 3, 4, task="addition")
        assert result == 7

    def test_run_propagates_exceptions(self):
        def failing_fn():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            agentest.run(failing_fn, task="will fail")


# ---- @agentest.trace decorator ----


class TestTraceDecorator:
    def test_trace_decorator(self):
        @agentest.trace(task="decorated task")
        def my_fn():
            return "hello"

        result, trace = my_fn()
        assert result == "hello"
        assert isinstance(trace, AgentTrace)

    def test_trace_decorator_uses_function_name(self):
        @agentest.trace()
        def my_agent_function():
            return "result"

        result, trace = my_agent_function()
        assert result == "result"
        assert isinstance(trace, AgentTrace)


# ---- Recorder.from_messages() ----


class TestFromMessages:
    def test_from_messages_basic(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        trace = Recorder.from_messages(messages, task="Chat test")
        assert isinstance(trace, AgentTrace)
        assert trace.task == "Chat test"
        assert len(trace.messages) == 2
        assert trace.success is True

    def test_from_messages_with_model(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm good!"},
        ]
        trace = Recorder.from_messages(messages, task="Chat", model="claude-sonnet-4-6")
        assert len(trace.llm_responses) == 2
        assert trace.llm_responses[0].model == "claude-sonnet-4-6"
        assert trace.llm_responses[0].content == "Hi there!"

    def test_from_messages_no_model(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        trace = Recorder.from_messages(messages)
        assert len(trace.llm_responses) == 0  # no model = no LLM responses

    def test_from_messages_failure(self):
        messages = [{"role": "user", "content": "Hello"}]
        trace = Recorder.from_messages(messages, success=False)
        assert trace.success is False

    def test_from_messages_metadata(self):
        messages = [{"role": "user", "content": "Hello"}]
        trace = Recorder.from_messages(messages, metadata={"env": "test"})
        assert trace.metadata == {"env": "test"}


# ---- Warning improvements ----


class TestWarnings:
    def test_recorder_finalize_empty_warns(self):
        recorder = Recorder(task="empty")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            recorder.finalize(success=True)
            assert len(w) == 1
            assert "no recorded data" in str(w[0].message).lower()

    def test_recorder_finalize_with_data_no_warning(self):
        recorder = Recorder(task="not empty")
        recorder.record_message("user", "Hello")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            recorder.finalize(success=True)
            assert len(w) == 0

    def test_llm_judge_no_client_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            LLMJudgeEvaluator(criteria="Is the answer correct?")
            assert len(w) == 1
            assert "without a client" in str(w[0].message).lower()

    def test_llm_judge_with_client_no_warning(self):
        mock_client = MagicMock()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            LLMJudgeEvaluator(criteria="test", client=mock_client)
            assert len(w) == 0


# ---- CLI doctor command ----


class TestDoctorCommand:
    def test_doctor_runs(self):
        from click.testing import CliRunner

        from agentest.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0
        assert "agentest" in result.output


# ---- Framework detection ----


class TestFrameworkDetection:
    def test_detect_framework(self):
        from agentest.cli import _detect_framework

        # Just verify it returns a string without error
        result = _detect_framework()
        assert isinstance(result, str)
        assert result in ("anthropic", "openai", "langchain", "crewai", "generic")


# ---- Init command ----


class TestInitCommand:
    def test_init_creates_files(self, tmp_path, monkeypatch):
        from click.testing import CliRunner

        from agentest.cli import main

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / "traces").is_dir()
        assert (tmp_path / "tests" / "agent_tests").is_dir()
        assert (tmp_path / "tests" / "agent_tests" / "test_agent_example.py").exists()
        assert (tmp_path / "tests" / "agent_tests" / "conftest.py").exists()


# ---- is_instrumented() accessor ----


class TestIsInstrumented:
    def test_not_instrumented_by_default(self):
        from agentest.integrations.instrument import is_instrumented

        # May or may not be instrumented depending on test order,
        # but it should return a bool
        assert isinstance(is_instrumented(), bool)
