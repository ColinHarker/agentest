<p align="center">
  <img src="assets/logo.svg" alt="Agentest" width="480"/>
</p>

<p align="center">
  <strong>Universal testing and evaluation toolkit for AI agents.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/agentest/"><img src="https://img.shields.io/pypi/v/agentest?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/agentest/"><img src="https://img.shields.io/pypi/pyversions/agentest" alt="Python versions"></a>
  <a href="https://github.com/ColinHarker/agentest/actions/workflows/ci.yml"><img src="https://github.com/ColinHarker/agentest/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/ColinHarker/agentest/blob/main/LICENSE"><img src="https://img.shields.io/github/license/ColinHarker/agentest" alt="License"></a>
  <a href="https://pypi.org/project/agentest/"><img src="https://img.shields.io/pypi/dm/agentest?color=green" alt="Downloads"></a>
</p>

---

```
pip install agentest
```

## Get Started

```python
import agentest

# Auto-record all LLM calls (works with Anthropic and OpenAI SDKs)
agentest.instrument()

# Run your agent and capture a trace
result, trace = agentest.run(my_agent, "Summarize README.md", task="Summarize")

# Evaluate it
for r in agentest.evaluate(trace):
    print(f"{r.evaluator}: {'PASS' if r.passed else 'FAIL'}")
```

That's it. Three lines to instrument, trace, and evaluate any agent — no matter what framework or LLM provider you use.

## What You Get

- **[Record & Replay](docs/guide/recording.md)** — Capture real agent sessions, replay them deterministically without LLM calls
- **[Tool Mocking](docs/guide/mocking.md)** — Mock any tool with a fluent API: `.when(...).returns(...)`
- **[10 Built-in Evaluators](docs/guide/evaluators.md)** — Task completion, safety, cost, latency, tool usage, LLM judges, and more
- **[Auto-Instrumentation](docs/guide/integrations.md)** — `agentest.instrument()` patches Anthropic/OpenAI clients with zero code changes
- **[Framework Adapters](docs/guide/integrations.md)** — LangChain, CrewAI, AutoGen, LlamaIndex, Claude Agent SDK, OpenAI Agents SDK
- **[MCP Server Testing](docs/guide/mcp-testing.md)** — Protocol compliance, schema validation, and security testing
- **[pytest Plugin](docs/guide/pytest.md)** — Auto-registered fixtures, markers, and CLI flags
- **[Benchmarking](docs/guide/benchmarking.md)** — Compare pass rates, cost, and latency across models
- **[CLI](docs/guide/cli.md)** — `agentest evaluate`, `agentest replay`, `agentest summary`, and more
- **[Web Dashboard](docs/guide/web-ui.md)** — Browse and explore traces in your browser

## Learn More

- **[Quick Start Guide](docs/guide/quickstart.md)** — install to first passing test in under a minute
- **[Full Documentation](docs/index.md)** — guides, API reference, and best practices
- **[Examples](examples/)** — working code you can run
- **[Best Practices](docs/guide/best-practices.md)** — rollout order, project structure, CI/CD setup

## License

MIT
