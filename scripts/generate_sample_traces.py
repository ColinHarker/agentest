"""Generate sample traces for testing the UI."""

import random
import time
from pathlib import Path

from agentest.recorder.recorder import Recorder


def generate_traces(output_dir: str = "traces", count: int = 12) -> None:
    """Generate diverse sample traces."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    tasks = [
        ("Summarize README.md", "claude-sonnet-4-6", True),
        ("Refactor authentication module", "claude-opus-4-6", True),
        ("Fix bug in payment processing", "gpt-4o", True),
        ("Write unit tests for user service", "claude-sonnet-4-6", True),
        ("Analyze code quality metrics", "gpt-4o-mini", True),
        ("Deploy staging environment", "claude-sonnet-4-6", False),
        ("Migrate database schema", "claude-opus-4-6", True),
        ("Review pull request #42", "gpt-4o", True),
        ("Debug memory leak in worker", "claude-sonnet-4-6", False),
        ("Generate API documentation", "claude-haiku-4-5", True),
        ("Optimize SQL queries", "gpt-4o", True),
        ("Set up CI/CD pipeline", "claude-sonnet-4-6", True),
    ]

    tools_pool = [
        ("read_file", {"path": "src/main.py"}, "def main():\n    pass", None),
        ("write_file", {"path": "src/test.py", "content": "import pytest"}, True, None),
        ("search", {"query": "authentication flow"}, ["auth.py:15", "login.py:42"], None),
        ("bash", {"command": "npm test"}, "42 tests passed", None),
        ("bash", {"command": "python -m pytest"}, "12 passed, 2 failed", None),
        ("read_file", {"path": "config.yaml"}, "database:\n  host: localhost", None),
        ("git_diff", {"ref": "HEAD~1"}, "+10 -3 lines changed", None),
        ("http_request", {"url": "https://api.example.com/status"}, '{"status": "ok"}', None),
        ("search", {"query": "SQL injection vulnerability"}, [], None),
        ("bash", {"command": "docker build ."}, None, "Build failed: missing Dockerfile"),
    ]

    for i, (task, model, success) in enumerate(tasks[:count]):
        rec = Recorder(task=task, metadata={"run_id": i + 1, "environment": "test"})

        # Set start time spread over the last few hours
        rec.trace.start_time = time.time() - random.randint(60, 7200)

        rec.record_message("user", f"Please {task.lower()}")

        # Add 2-5 tool calls
        num_tools = random.randint(2, 5)
        for _ in range(num_tools):
            name, args, result, error = random.choice(tools_pool)
            if not success and random.random() < 0.3:
                error = f"Error: operation failed for {name}"
                result = None
            rec.record_tool_call(
                name=name,
                arguments=args,
                result=result,
                error=error,
                duration_ms=random.uniform(5, 500),
            )

        # Add 1-3 LLM responses
        num_responses = random.randint(1, 3)
        for _ in range(num_responses):
            in_tok = random.randint(100, 2000)
            out_tok = random.randint(50, 1000)
            rec.record_llm_response(
                model=model,
                content=f"I've completed the analysis for: {task}. Here are the results...",
                input_tokens=in_tok,
                output_tokens=out_tok,
                latency_ms=random.uniform(200, 3000),
            )

        error_msg = f"Task failed: {task}" if not success else None
        rec.finalize(success=success, error=error_msg)

        filename = f"trace_{i+1:03d}_{task.lower().replace(' ', '_')[:30]}.yaml"
        rec.save(Path(output_dir) / filename)

    print(f"Generated {count} sample traces in {output_dir}/")


if __name__ == "__main__":
    generate_traces()
