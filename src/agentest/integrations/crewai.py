"""CrewAI integration for Agentest.

Provides a wrapper that records CrewAI crew executions as AgentTrace objects.

Usage:
    from agentest.integrations.crewai import record_crew

    trace = record_crew(crew, inputs={"topic": "AI testing"})
    # trace is a full AgentTrace ready for evaluation

Requires: pip install agentest[crewai]
"""

from __future__ import annotations

import time
from typing import Any

from agentest.core import AgentTrace
from agentest.recorder.recorder import Recorder


def record_crew(
    crew: Any,
    inputs: dict[str, Any] | None = None,
    task: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[Any, AgentTrace]:
    """Execute a CrewAI crew and record its execution as an AgentTrace.

    Args:
        crew: A CrewAI Crew instance.
        inputs: Input dict to pass to crew.kickoff().
        task: Task description for the trace. Defaults to crew description.
        metadata: Optional metadata to attach.

    Returns:
        Tuple of (crew_result, AgentTrace).

    Example:
        >>> from crewai import Crew, Agent, Task
        >>> crew = Crew(agents=[...], tasks=[...])
        >>> result, trace = record_crew(crew, inputs={"topic": "testing"})
    """
    try:
        from crewai import Crew
    except ImportError:
        raise ImportError(
            "CrewAI integration requires crewai. Install with: pip install agentest[crewai]"
        )

    if not isinstance(crew, Crew):
        raise TypeError(f"Expected a CrewAI Crew instance, got {type(crew).__name__}")

    task_desc = task or getattr(crew, "name", None) or "crewai-execution"
    meta = {"framework": "crewai", **(metadata or {})}

    recorder = Recorder(task=task_desc, metadata=meta)

    # Record crew configuration
    agents = getattr(crew, "agents", [])
    tasks = getattr(crew, "tasks", [])
    for agent in agents:
        agent_name = getattr(agent, "role", "agent")
        recorder.record_message("system", f"Agent: {agent_name}")

    for crew_task in tasks:
        desc = getattr(crew_task, "description", str(crew_task))
        recorder.record_message("user", f"Task: {desc}")

    start = time.time()
    error_msg = None
    result = None

    try:
        result = crew.kickoff(inputs=inputs or {})
    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration_ms = (time.time() - start) * 1000

        # Try to extract output from result
        if result is not None:
            output = str(result)
            recorder.record_llm_response(
                model="crewai",
                content=output,
                input_tokens=0,
                output_tokens=0,
                latency_ms=duration_ms,
            )

        # Extract task results if available
        if result is not None and hasattr(result, "tasks_output"):
            tasks_output = result.tasks_output
            for task_output in tasks_output:
                task_name = getattr(task_output, "description", "task")[:50]
                task_result = getattr(task_output, "raw", str(task_output))
                recorder.record_tool_call(
                    name=f"crew_task:{task_name}",
                    arguments={},
                    result=task_result,
                    duration_ms=duration_ms / max(len(tasks_output), 1),
                )

        trace = recorder.finalize(
            success=error_msg is None,
            error=error_msg,
        )

    return result, trace


class CrewAIAdapter:
    """Persistent adapter for recording multiple CrewAI runs.

    Args:
        default_metadata: Default metadata to attach to all traces.
    """

    def __init__(self, default_metadata: dict[str, Any] | None = None):
        self._metadata = default_metadata or {}
        self._traces: list[AgentTrace] = []

    def record(
        self,
        crew: Any,
        inputs: dict[str, Any] | None = None,
        task: str | None = None,
    ) -> tuple[Any, AgentTrace]:
        """Record a crew execution.

        Args:
            crew: CrewAI Crew instance.
            inputs: Input dict for crew.kickoff().
            task: Task description.

        Returns:
            Tuple of (crew_result, AgentTrace).
        """
        result, trace = record_crew(crew, inputs=inputs, task=task, metadata=self._metadata)
        self._traces.append(trace)
        return result, trace

    @property
    def traces(self) -> list[AgentTrace]:
        """All recorded traces."""
        return list(self._traces)

    def clear(self) -> None:
        """Clear all recorded traces."""
        self._traces.clear()
