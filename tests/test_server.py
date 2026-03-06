"""Tests for the FastAPI server application."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentest.recorder.recorder import Recorder
from agentest.server.app import create_app


# ---- Fixtures ----

@pytest.fixture
def traces_dir(tmp_path):
    """Create a temporary traces directory."""
    d = tmp_path / "traces"
    d.mkdir()
    return d


@pytest.fixture
def client(traces_dir):
    """Create a test client with an empty traces directory."""
    app = create_app(traces_dir=str(traces_dir))
    return TestClient(app)


@pytest.fixture
def populated_client(traces_dir):
    """Create a test client with a pre-populated trace."""
    recorder = Recorder(task="Test task")
    recorder.record_message("user", "Hello")
    recorder.record_llm_response(
        model="claude-sonnet-4-6",
        content="Hi there",
        input_tokens=100,
        output_tokens=20,
    )
    recorder.record_tool_call(
        name="read_file",
        arguments={"path": "test.txt"},
        result="file contents",
    )
    trace = recorder.finalize(success=True)
    recorder.save(traces_dir / "test_trace.yaml")

    app = create_app(traces_dir=str(traces_dir))
    client = TestClient(app)
    return client, trace


# ---- GET /api/traces (empty) ----

def test_list_traces_empty(client):
    response = client.get("/api/traces")
    assert response.status_code == 200
    data = response.json()
    assert data["traces"] == []
    assert data["total"] == 0


# ---- POST /api/traces (save) ----

def test_save_trace(client):
    response = client.post("/api/traces", json={
        "task": "My test task",
        "messages": [{"role": "user", "content": "Hello"}],
        "llm_responses": [{
            "model": "claude-sonnet-4-6",
            "content": "Hi",
            "input_tokens": 50,
            "output_tokens": 10,
        }],
        "tool_calls": [{
            "name": "read_file",
            "arguments": {"path": "test.txt"},
            "result": "contents",
        }],
        "success": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "file" in data
    assert data["file"].endswith(".yaml")


def test_save_and_list_trace(client):
    """Save a trace then verify it appears in the list."""
    client.post("/api/traces", json={
        "task": "Listed task",
        "success": True,
    })
    response = client.get("/api/traces")
    data = response.json()
    assert data["total"] == 1
    assert data["traces"][0]["task"] == "Listed task"


# ---- GET /api/traces/{id} ----

def test_get_trace_by_id(populated_client):
    client, trace = populated_client
    response = client.get(f"/api/traces/{trace.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == trace.id
    assert data["task"] == "Test task"
    assert "computed" in data
    assert data["computed"]["total_tool_calls"] == 1


def test_get_trace_not_found(client):
    response = client.get("/api/traces/nonexistent-id")
    assert response.status_code == 404


# ---- POST /api/evaluate ----

def test_evaluate_trace(populated_client):
    client, trace = populated_client
    response = client.post("/api/evaluate", json={
        "trace_id": trace.id,
        "evaluators": ["task_completion", "safety", "tool_usage"],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["trace_id"] == trace.id
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) == 3
    assert "all_passed" in data
    assert "avg_score" in data


def test_evaluate_trace_not_found(client):
    response = client.post("/api/evaluate", json={
        "trace_id": "nonexistent",
        "evaluators": ["task_completion"],
    })
    assert response.status_code == 404


# ---- GET /api/dashboard ----

def test_dashboard_empty(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["total_traces"] == 0
    assert data["success_rate"] == 0
    assert data["total_cost"] == 0


def test_dashboard_with_traces(populated_client):
    client, trace = populated_client
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["total_traces"] == 1
    assert data["success_rate"] == 1.0
    assert data["total_tokens"] > 0
    assert len(data["models_used"]) > 0
    assert "read_file" in data["tool_usage"]
    assert len(data["recent_traces"]) == 1


# ---- DELETE /api/traces/{id} ----

def test_delete_trace(populated_client):
    client, trace = populated_client
    response = client.delete(f"/api/traces/{trace.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True

    # Verify it's gone
    response = client.get(f"/api/traces/{trace.id}")
    assert response.status_code == 404


def test_delete_trace_not_found(client):
    response = client.delete("/api/traces/nonexistent-id")
    assert response.status_code == 404


# ---- GET / (index) ----

def test_index_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    # Should return some HTML (even if static files aren't present)
    assert "Agentest" in response.text


# ---- POST /api/evaluate/batch ----

def test_evaluate_batch_empty(client):
    response = client.post("/api/evaluate/batch")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["passed"] == 0


def test_evaluate_batch_with_traces(populated_client):
    client, trace = populated_client
    response = client.post("/api/evaluate/batch")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "results" in data
    assert len(data["results"]) == 1
