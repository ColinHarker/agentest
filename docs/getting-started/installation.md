---
sidebar_position: 1
title: Installation
---

# Installation

## Requirements

- Python 3.10 or later

## Basic Install

```bash
pip install agentest
```

This gives you the core library: recording, replay, mocking, evaluators, benchmarking, MCP testing, CLI, and pytest plugin.

## Optional Extras

### Web UI Dashboard

```bash
pip install "agentest[web]"
```

Adds FastAPI and uvicorn for the web dashboard (`agentest serve`).

### Framework Integrations

```bash
# LangChain adapter
pip install "agentest[langchain]"

# CrewAI adapter
pip install "agentest[crewai]"

# AutoGen adapter
pip install "agentest[autogen]"

# LlamaIndex adapter
pip install "agentest[llamaindex]"
```

### LLM Provider Support

For the `LLMJudgeEvaluator` (LLM-graded evaluation):

```bash
# Anthropic (Claude)
pip install "agentest[anthropic]"

# OpenAI (GPT)
pip install "agentest[openai]"
```

### Everything

```bash
pip install "agentest[all]"
```

This installs all optional dependencies: web UI, all framework adapters, and all LLM providers.

## Development Install

```bash
git clone https://github.com/ColinHarker/agentest.git
cd agentest
pip install -e ".[dev,all]"
```

This installs all dependencies including testing tools (pytest, ruff, mypy).

## Verify Installation

```bash
agentest --version
```

Or in Python:

```python
import agentest
print(agentest.__version__)
```
