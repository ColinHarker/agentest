"""FastAPI application for the Agentest web UI."""

import json
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agentest.core import AgentTrace, diff_traces
from agentest.evaluators.base import CompositeEvaluator, EvalResult
from agentest.evaluators.builtin import (
    CostEvaluator,
    LatencyEvaluator,
    SafetyEvaluator,
    TaskCompletionEvaluator,
    ToolUsageEvaluator,
)
from agentest.recorder.recorder import Recorder

STATIC_DIR = Path(__file__).parent / "static"


def create_app(traces_dir: str = "traces") -> FastAPI:
    """Create and configure the FastAPI application with all API routes.

    Args:
        traces_dir: Directory path for storing and loading trace files.
    """
    app = FastAPI(title="Agentest", version="0.1.0")

    traces_path = Path(traces_dir)
    traces_path.mkdir(parents=True, exist_ok=True)

    # Serve static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ---- Trace Store ----

    def _load_traces() -> list[dict[str, Any]]:
        """Load all traces from the traces directory."""
        traces = []
        for f in sorted(traces_path.iterdir()):
            if f.suffix in (".yaml", ".yml", ".json"):
                try:
                    trace = Recorder.load(f)
                    data = trace.model_dump(mode="json")
                    data["_file"] = f.name
                    traces.append(data)
                except Exception:
                    continue
        return traces

    def _load_trace(trace_id: str) -> Optional[AgentTrace]:
        """Load a specific trace by ID."""
        for f in traces_path.iterdir():
            if f.suffix in (".yaml", ".yml", ".json"):
                try:
                    trace = Recorder.load(f)
                    if trace.id == trace_id:
                        return trace
                except Exception:
                    continue
        return None

    # ---- API Routes ----

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve the main UI."""
        html_path = STATIC_DIR / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text())
        return HTMLResponse("<h1>Agentest UI</h1><p>Static files not found.</p>")

    @app.get("/api/traces")
    async def list_traces():
        """List all traces with summary data."""
        traces = _load_traces()
        summaries = []
        for t in traces:
            llm_responses = t.get("llm_responses", [])
            tool_calls = t.get("tool_calls", [])
            total_tokens = sum(r.get("total_tokens", 0) for r in llm_responses)

            # Calculate cost
            trace_obj = AgentTrace.model_validate(t)
            total_cost = trace_obj.total_cost

            summaries.append({
                "id": t["id"],
                "task": t.get("task", ""),
                "success": t.get("success"),
                "start_time": t.get("start_time"),
                "end_time": t.get("end_time"),
                "duration_ms": trace_obj.duration_ms,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
                "llm_calls": len(llm_responses),
                "tool_calls": len(tool_calls),
                "failed_tools": sum(1 for tc in tool_calls if tc.get("error")),
                "models": list({r.get("model", "") for r in llm_responses}),
                "file": t.get("_file", ""),
            })

        return {"traces": summaries, "total": len(summaries)}

    @app.get("/api/traces/{trace_id}")
    async def get_trace(trace_id: str):
        """Get a full trace by ID."""
        trace = _load_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")
        data = trace.model_dump(mode="json")
        data["computed"] = {
            "duration_ms": trace.duration_ms,
            "total_tokens": trace.total_tokens,
            "total_cost": trace.total_cost,
            "total_tool_calls": trace.total_tool_calls,
            "failed_tool_calls": len(trace.failed_tool_calls),
        }
        return data

    class EvaluateRequest(BaseModel):
        trace_id: str
        evaluators: list[str] = ["task_completion", "safety", "cost", "tool_usage", "latency"]
        max_cost: Optional[float] = None
        max_tokens: Optional[int] = None
        max_time_ms: Optional[float] = None

    @app.post("/api/evaluate")
    async def evaluate_trace(req: EvaluateRequest):
        """Run evaluations on a trace."""
        trace = _load_trace(req.trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        evaluator_map: dict[str, Any] = {
            "task_completion": TaskCompletionEvaluator(min_messages=0),
            "safety": SafetyEvaluator(),
            "cost": CostEvaluator(
                max_cost=req.max_cost,
                max_tokens=req.max_tokens,
            ),
            "latency": LatencyEvaluator(max_total_ms=req.max_time_ms),
            "tool_usage": ToolUsageEvaluator(),
        }

        evaluators = [evaluator_map[name] for name in req.evaluators if name in evaluator_map]
        results = [e.evaluate(trace) for e in evaluators]

        return {
            "trace_id": req.trace_id,
            "results": [r.model_dump() for r in results],
            "all_passed": all(r.passed for r in results),
            "avg_score": sum(r.score for r in results) / len(results) if results else 0,
        }

    @app.get("/api/dashboard")
    async def dashboard_stats():
        """Get dashboard overview statistics."""
        traces = _load_traces()
        if not traces:
            return {
                "total_traces": 0,
                "success_rate": 0,
                "total_cost": 0,
                "total_tokens": 0,
                "avg_duration_ms": 0,
                "models_used": [],
                "tool_usage": {},
                "cost_by_model": {},
                "recent_traces": [],
                "traces_over_time": [],
            }

        trace_objects = [AgentTrace.model_validate(t) for t in traces]
        total = len(trace_objects)
        succeeded = sum(1 for t in trace_objects if t.success is True)
        total_cost = sum(t.total_cost for t in trace_objects)
        total_tokens = sum(t.total_tokens for t in trace_objects)

        durations = [t.duration_ms for t in trace_objects if t.duration_ms is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Models used
        models: set[str] = set()
        cost_by_model: dict[str, float] = {}
        for t in trace_objects:
            for r in t.llm_responses:
                models.add(r.model)
                cost_by_model[r.model] = cost_by_model.get(r.model, 0) + r.cost_estimate

        # Tool usage frequency
        tool_counts: dict[str, int] = {}
        tool_errors: dict[str, int] = {}
        for t in trace_objects:
            for tc in t.tool_calls:
                tool_counts[tc.name] = tool_counts.get(tc.name, 0) + 1
                if tc.error:
                    tool_errors[tc.name] = tool_errors.get(tc.name, 0) + 1

        # Recent traces
        recent = sorted(traces, key=lambda t: t.get("start_time", 0), reverse=True)[:10]
        recent_summaries = []
        for t in recent:
            trace_obj = AgentTrace.model_validate(t)
            recent_summaries.append({
                "id": t["id"],
                "task": t.get("task", "")[:80],
                "success": t.get("success"),
                "total_cost": trace_obj.total_cost,
                "total_tokens": trace_obj.total_tokens,
                "duration_ms": trace_obj.duration_ms,
                "start_time": t.get("start_time"),
            })

        return {
            "total_traces": total,
            "success_rate": succeeded / total if total else 0,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "avg_duration_ms": avg_duration,
            "models_used": sorted(models),
            "tool_usage": {
                name: {"calls": count, "errors": tool_errors.get(name, 0)}
                for name, count in sorted(tool_counts.items(), key=lambda x: -x[1])
            },
            "cost_by_model": cost_by_model,
            "recent_traces": recent_summaries,
        }

    class SaveTraceRequest(BaseModel):
        task: str = ""
        messages: list[dict[str, Any]] = []
        llm_responses: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        success: Optional[bool] = None
        error: Optional[str] = None

    @app.post("/api/traces")
    async def save_trace(req: SaveTraceRequest):
        """Save a new trace."""
        recorder = Recorder(task=req.task, metadata=req.metadata)

        for msg in req.messages:
            recorder.record_message(msg.get("role", "user"), msg.get("content", ""))

        for resp in req.llm_responses:
            recorder.record_llm_response(
                model=resp.get("model", "unknown"),
                content=resp.get("content", ""),
                input_tokens=resp.get("input_tokens", 0),
                output_tokens=resp.get("output_tokens", 0),
                latency_ms=resp.get("latency_ms", 0),
            )

        for tc in req.tool_calls:
            recorder.record_tool_call(
                name=tc.get("name", "unknown"),
                arguments=tc.get("arguments", {}),
                result=tc.get("result"),
                error=tc.get("error"),
                duration_ms=tc.get("duration_ms"),
            )

        trace = recorder.finalize(
            success=req.success if req.success is not None else True,
            error=req.error,
        )

        filename = f"trace_{trace.id[:8]}.yaml"
        recorder.save(traces_path / filename)

        return {"id": trace.id, "file": filename}

    @app.delete("/api/traces/{trace_id}")
    async def delete_trace(trace_id: str):
        """Delete a trace."""
        for f in traces_path.iterdir():
            if f.suffix in (".yaml", ".yml", ".json"):
                try:
                    trace = Recorder.load(f)
                    if trace.id == trace_id:
                        f.unlink()
                        return {"deleted": True, "file": f.name}
                except Exception:
                    continue
        raise HTTPException(status_code=404, detail="Trace not found")

    @app.post("/api/evaluate/batch")
    async def evaluate_batch(evaluators: list[str] = ["task_completion", "safety", "cost", "tool_usage"]):
        """Evaluate all traces with the given evaluators."""
        traces = _load_traces()
        results = []

        evaluator_map: dict[str, Any] = {
            "task_completion": TaskCompletionEvaluator(min_messages=0),
            "safety": SafetyEvaluator(),
            "cost": CostEvaluator(),
            "latency": LatencyEvaluator(),
            "tool_usage": ToolUsageEvaluator(),
        }

        active_evaluators = [evaluator_map[name] for name in evaluators if name in evaluator_map]

        for t in traces:
            trace = AgentTrace.model_validate(t)
            eval_results = [e.evaluate(trace) for e in active_evaluators]
            results.append({
                "trace_id": t["id"],
                "task": t.get("task", ""),
                "results": [r.model_dump() for r in eval_results],
                "all_passed": all(r.passed for r in eval_results),
                "avg_score": sum(r.score for r in eval_results) / len(eval_results) if eval_results else 0,
            })

        return {
            "total": len(results),
            "passed": sum(1 for r in results if r["all_passed"]),
            "results": results,
        }

    class DiffRequest(BaseModel):
        trace_id_a: str
        trace_id_b: str

    @app.post("/api/diff")
    async def diff_traces_api(req: DiffRequest):
        """Compare two traces and return a structured diff."""
        trace_a = _load_trace(req.trace_id_a)
        trace_b = _load_trace(req.trace_id_b)
        if not trace_a:
            raise HTTPException(status_code=404, detail=f"Trace A not found: {req.trace_id_a}")
        if not trace_b:
            raise HTTPException(status_code=404, detail=f"Trace B not found: {req.trace_id_b}")

        result = diff_traces(trace_a, trace_b)
        return result

    return app
