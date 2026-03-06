"""Base evaluator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from agentest.core import AgentTrace


class EvalResult(BaseModel):
    """Result of an evaluation."""

    evaluator: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)
    message: str = ""

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"EvalResult({self.evaluator}: {status} score={self.score:.2f} {self.message})"


class Evaluator(ABC):
    """Base class for agent evaluators.

    Evaluators inspect an AgentTrace and produce a score and pass/fail result.

    To create a custom evaluator:
        class MyEval(Evaluator):
            name = "my_eval"

            def evaluate(self, trace: AgentTrace) -> EvalResult:
                # Your logic here
                return EvalResult(
                    evaluator=self.name,
                    score=0.95,
                    passed=True,
                    message="Looks good!",
                )
    """

    name: str = "base"
    description: str = ""

    @abstractmethod
    def evaluate(self, trace: AgentTrace) -> EvalResult:
        """Evaluate an agent trace and return a result."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


class CompositeEvaluator(Evaluator):
    """Runs multiple evaluators and aggregates results."""

    name = "composite"

    def __init__(
        self,
        evaluators: list[Evaluator],
        require_all: bool = True,
    ) -> None:
        """Initialize with a list of evaluators.

        Args:
            evaluators: Evaluators to run.
            require_all: If True, all must pass; if False, any passing suffices.
        """
        self.evaluators = evaluators
        self.require_all = require_all

    def evaluate(self, trace: AgentTrace) -> EvalResult:
        """Run all evaluators and return an aggregated result."""
        results = [e.evaluate(trace) for e in self.evaluators]

        if self.require_all:
            passed = all(r.passed for r in results)
        else:
            passed = any(r.passed for r in results)

        avg_score = sum(r.score for r in results) / len(results) if results else 0.0

        return EvalResult(
            evaluator=self.name,
            score=avg_score,
            passed=passed,
            details={
                "results": [r.model_dump() for r in results],
                "individual_pass_rate": sum(r.passed for r in results) / len(results)
                if results
                else 0.0,
            },
            message=f"{sum(r.passed for r in results)}/{len(results)} evaluators passed",
        )

    def evaluate_all(self, trace: AgentTrace) -> list[EvalResult]:
        """Run all evaluators and return individual results."""
        return [e.evaluate(trace) for e in self.evaluators]


class LLMJudgeEvaluator(Evaluator):
    """Evaluator that uses an LLM to judge agent output.

    Requires an LLM client to be configured.
    """

    name = "llm_judge"

    def __init__(
        self,
        criteria: str,
        model: str = "claude-sonnet-4-6",
        client: Any = None,
    ) -> None:
        """Initialize the LLM judge.

        Args:
            criteria: Natural-language description of what to evaluate.
            model: Model identifier for the LLM.
            client: Anthropic or OpenAI client instance.
        """
        self.criteria = criteria
        self.model = model
        self.client = client

    def evaluate(self, trace: AgentTrace) -> EvalResult:
        if self.client is None:
            return EvalResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                message="No LLM client configured. Install anthropic or openai.",
            )

        prompt = self._build_prompt(trace)

        try:
            response = self._call_llm(prompt)
            score, reasoning = self._parse_response(response)
            return EvalResult(
                evaluator=self.name,
                score=score,
                passed=score >= 0.7,
                message=reasoning,
                details={"criteria": self.criteria, "model": self.model},
            )
        except Exception as e:
            return EvalResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                message=f"LLM judge error: {e}",
            )

    def _build_prompt(self, trace: AgentTrace) -> str:
        """Build the evaluation prompt from an agent trace."""
        tool_summary = "\n".join(
            f"  - {tc.name}({tc.arguments}) -> {tc.result}"
            for tc in trace.tool_calls[:20]  # Limit to first 20
        )
        messages_summary = "\n".join(
            f"  [{m.role.value}]: {m.content[:200]}" for m in trace.messages[:20]
        )

        return f"""You are evaluating an AI agent's performance. Score from 0.0 to 1.0.

TASK: {trace.task}

CRITERIA: {self.criteria}

AGENT MESSAGES:
{messages_summary}

TOOL CALLS:
{tool_summary}

RESULT: {"Success" if trace.success else "Failed"}{f" - {trace.error}" if trace.error else ""}

Respond with ONLY a JSON object (no other text):
{{"score": <number between 0.0 and 1.0>, "reasoning": "<one sentence explanation>"}}"""

    def _call_llm(self, prompt: str) -> str:
        """Send the prompt to the configured LLM and return the response text."""
        # Support both Anthropic and OpenAI clients
        if hasattr(self.client, "messages"):
            # Anthropic
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            result: str = response.content[0].text
            return result
        elif hasattr(self.client, "chat"):
            # OpenAI — use JSON response format for structured output
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=200,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""
        else:
            raise TypeError(f"Unsupported client type: {type(self.client)}")

    @staticmethod
    def _parse_response(response: str) -> tuple[float, str]:
        """Parse score and reasoning from the LLM response.

        Tries JSON first, falls back to line-based parsing for backward compat.
        """
        import json as _json

        # Try JSON first
        text = response.strip()
        try:
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = _json.loads(text)
            score = max(0.0, min(1.0, float(data.get("score", 0.5))))
            reasoning = str(data.get("reasoning", ""))
            return score, reasoning
        except (_json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass

        # Fall back to line-based parsing
        score = 0.5
        reasoning = response.strip()

        for line in response.strip().split("\n"):
            if line.startswith("SCORE:"):
                try:
                    score = float(line.split(":", 1)[1].strip())
                    score = max(0.0, min(1.0, score))
                except ValueError:
                    pass
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()

        return score, reasoning


class RubricEvaluator(Evaluator):
    """Evaluator that scores an agent trace against a weighted rubric.

    Each criterion in the rubric is scored independently by an LLM, then
    a weighted average produces the final score.
    """

    name = "rubric"

    def __init__(
        self,
        rubric: dict[str, float],
        model: str = "claude-sonnet-4-6",
        client: Any = None,
    ) -> None:
        """Initialize the rubric evaluator.

        Args:
            rubric: Mapping of criterion descriptions to their weights.
                    Weights are normalized so they sum to 1.0.
            model: Model identifier for the LLM.
            client: Anthropic or OpenAI client instance.
        """
        total = sum(rubric.values())
        if total > 0:
            self.rubric = {k: v / total for k, v in rubric.items()}
        else:
            self.rubric = {k: 1.0 / len(rubric) for k in rubric} if rubric else {}
        self.model = model
        self.client = client

    def evaluate(self, trace: AgentTrace) -> EvalResult:
        """Score the trace against every criterion and return a weighted result."""
        if self.client is None:
            return EvalResult(
                evaluator=self.name,
                score=0.0,
                passed=False,
                message="No LLM client configured. Install anthropic or openai.",
            )

        criterion_scores: list[dict[str, Any]] = []
        weighted_total = 0.0

        for criterion, weight in self.rubric.items():
            score, reasoning = self._score_criterion(trace, criterion)
            criterion_scores.append(
                {
                    "criterion": criterion,
                    "weight": weight,
                    "score": score,
                    "reasoning": reasoning,
                }
            )
            weighted_total += score * weight

        final_score = max(0.0, min(1.0, weighted_total))
        passed = final_score >= 0.7

        return EvalResult(
            evaluator=self.name,
            score=final_score,
            passed=passed,
            details={"criterion_scores": criterion_scores},
            message=f"Rubric score: {final_score:.2f} ({len(criterion_scores)} criteria)",
        )

    def _score_criterion(self, trace: AgentTrace, criterion: str) -> tuple[float, str]:
        """Ask the LLM to score a single criterion and return (score, reasoning)."""
        import json as _json

        tool_summary = "\n".join(
            f"  - {tc.name}({tc.arguments}) -> {tc.result}" for tc in trace.tool_calls[:20]
        )
        messages_summary = "\n".join(
            f"  [{m.role.value}]: {m.content[:200]}" for m in trace.messages[:20]
        )

        prompt = f"""You are evaluating an AI agent's performance on a specific criterion.
Score from 0.0 to 1.0.

TASK: {trace.task}

CRITERION: {criterion}

AGENT MESSAGES:
{messages_summary}

TOOL CALLS:
{tool_summary}

RESULT: {"Success" if trace.success else "Failed"}{f" - {trace.error}" if trace.error else ""}

Respond with ONLY a JSON object (no other text):
{{"score": <number between 0.0 and 1.0>, "reasoning": "<one sentence explanation>"}}"""

        try:
            if hasattr(self.client, "messages"):
                # Anthropic
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=200,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                text: str = response.content[0].text
            elif hasattr(self.client, "chat"):
                # OpenAI
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=200,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.choices[0].message.content or ""
            else:
                raise TypeError(f"Unsupported client type: {type(self.client)}")

            # Parse JSON response
            raw = text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = _json.loads(raw)
            score = max(0.0, min(1.0, float(data.get("score", 0.5))))
            reasoning = str(data.get("reasoning", ""))
            return score, reasoning
        except (_json.JSONDecodeError, ValueError, KeyError, TypeError):
            return 0.5, "Failed to parse LLM response"
        except Exception as e:
            return 0.5, f"Error scoring criterion: {e}"
