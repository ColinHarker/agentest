---
sidebar_position: 11
title: Contributing
---

# Contributing to Agentest

Thanks for your interest in contributing to Agentest! This guide covers everything you need to get started.

## Development Setup

### Prerequisites

- Python 3.10+
- [pip](https://pip.pypa.io/en/stable/) or [uv](https://github.com/astral-sh/uv)

### Installation

```bash
# Clone the repository
git clone https://github.com/ColinHarker/agentest.git
cd agentest

# Install in development mode with all extras
pip install -e ".[dev,all]"
```

This installs:
- **Core dependencies** — click, pydantic, rich, pyyaml, fastapi, uvicorn, httpx, jinja2
- **Dev tools** — pytest, pytest-asyncio, ruff, mypy
- **Optional providers** — anthropic, openai (for LLMJudgeEvaluator and examples)

### Project Structure

```
agentest/
├── src/agentest/         # Source code
│   ├── core.py            # Data models (AgentTrace, ToolCall, LLMResponse)
│   ├── recorder/          # Record & replay
│   ├── mocking/           # Tool mocking
│   ├── evaluators/        # Evaluation system (base + 5 built-in)
│   ├── benchmark/         # Benchmarking & model comparison
│   ├── mcp_testing/       # MCP server testing
│   ├── reporters/         # Console & JSON output
│   ├── server/            # FastAPI web UI
│   ├── pytest_plugin.py   # pytest integration
│   └── cli.py             # Click CLI
├── tests/                 # Test suite
├── examples/              # Example scripts
├── docs/                  # Documentation site (Docusaurus)
└── pyproject.toml         # Build config, linting, typing
```

## Running Tests

```bash
# Run the full test suite
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_core.py

# Run a specific test
pytest tests/test_evaluators.py::test_safety_clean

# Run with coverage (if installed)
pytest --cov=agentest
```

## Code Quality

### Linting

We use [Ruff](https://docs.astral.sh/ruff/) for linting and import sorting:

```bash
# Check for lint errors
ruff check src/ tests/

# Auto-fix lint errors
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/
```

### Type Checking

We use [mypy](https://mypy.readthedocs.io/) in strict mode:

```bash
mypy src/agentest/
```

### Style Guide

- **Python 3.10+** — use `X | Y` union syntax, not `Union[X, Y]`
- **Line length** — 100 characters max
- **Docstrings** — Google-style for all public classes and methods
- **Type annotations** — required on all public functions and methods
- **Pydantic** — use `BaseModel` for data classes that need serialization
- **Dataclasses** — use `@dataclass` for internal data structures

## Making Changes

### Workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes** — follow the style guide above

3. **Add tests** — all new features and bug fixes should have tests

4. **Run checks** before committing:
   ```bash
   ruff check src/ tests/
   mypy src/agentest/
   pytest
   ```

5. **Commit** with a clear message:
   ```bash
   git commit -m "Add support for custom evaluator scoring"
   ```

6. **Open a pull request** against `main`

### Adding a New Evaluator

1. Create a class that extends `Evaluator` in `src/agentest/evaluators/`:
   ```python
   from agentest.evaluators.base import Evaluator, EvalResult
   from agentest.core import AgentTrace

   class MyEvaluator(Evaluator):
       name = "my_evaluator"
       description = "Checks something specific about the trace"

       def evaluate(self, trace: AgentTrace) -> EvalResult:
           # Your logic here
           return EvalResult(
               evaluator=self.name,
               score=1.0,
               passed=True,
               message="All good",
           )
   ```

2. Add tests in `tests/test_evaluators.py`

3. Export from `src/agentest/__init__.py` if it's a public evaluator

### Adding a CLI Command

1. Add a new function in `src/agentest/cli.py` decorated with `@main.command()`
2. Follow the Click patterns used by existing commands
3. Use `ConsoleReporter` for rich output

## Running Examples

```bash
# Basic usage (no API key needed)
python examples/basic_usage.py

# Benchmark models (no API key needed — uses simulated agents)
python examples/benchmark_models.py

# Coding agent (requires Anthropic API key)
export ANTHROPIC_API_KEY=sk-ant-...
python examples/coding_agent.py
```

## Documentation

We use [Docusaurus](https://docusaurus.io/) for the documentation site:

```bash
# Install docs dependencies
npm install

# Serve docs locally
npm start

# Build docs
npm run build
```

## Questions?

Open an issue on GitHub if you have questions or need help with your contribution.
