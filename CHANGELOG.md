# Changelog

All notable changes to Agentest will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-03-05

### Added

- **Persistent MCP connections** — `MCPServerTester` now uses persistent `subprocess.Popen` with stdin/stdout pipes for session continuity and stateful testing. Supports context manager protocol (`with MCPServerTester(...) as tester:`)
- **`test_all_tools()`** — New convenience method to smoke-test every listed MCP tool with auto-generated minimal arguments from `inputSchema`
- **PII whitelist** — `SafetyEvaluator` now accepts `pii_whitelist` parameter to suppress false positives from known-safe PII patterns (e.g., test email addresses)
- **Enhanced schema validation** — `test_tool_schema_validation()` now validates property types, checks `required` fields exist in `properties`, and verifies `inputSchema` structure
- **Auto-instrumentation** — `agentest.instrument()` monkey-patches `anthropic` and `openai` clients to auto-record traces with zero code changes
- **LangChain adapter** — `AgentestCallbackHandler` converts LangChain chain/agent runs to AgentTrace (`pip install agentest[langchain]`)
- **CrewAI adapter** — `record_crew()` and `CrewAIAdapter` record CrewAI crew executions (`pip install agentest[crewai]`)
- **AutoGen adapter** — `record_autogen_chat()` and `AutoGenAdapter` record AutoGen conversations (`pip install agentest[autogen]`)
- **LlamaIndex adapter** — `AgentestHandler` callback records LlamaIndex query pipelines (`pip install agentest[llamaindex]`)
- **Claude Agent SDK integration** — `AgentestTracer` with `record()`, `record_async()`, and context manager for Claude Agent SDK apps
- **OpenAI Agents SDK integration** — `AgentestTracer` with `record()`, `record_async()`, and context manager for OpenAI Agents SDK apps
- **GitHub Action** — `ColinHarker/agentest` composite action with configurable evaluators, cost/token limits, safety checks, and JSON reports
- New top-level API: `agentest.instrument()`, `agentest.uninstrument()`, `agentest.get_traces()`, `agentest.clear_traces()`, `agentest.flush_trace()`

### Changed

- **FastAPI/uvicorn are now optional** — install with `pip install agentest[web]` for web UI support
- Core package reduced from 8 to 6 runtime dependencies
- CLI `serve` and `ui` commands now show helpful error message when web extras are missing
- Added `[langchain]`, `[crewai]`, `[autogen]`, `[llamaindex]`, `[web]`, and `[all]` optional dependency groups

## [0.1.0] - 2025-01-01

### Added

- **Core data models** — `AgentTrace`, `ToolCall`, `LLMResponse`, `Message`, `TraceSession`
- **Recorder** — capture agent interactions to YAML/JSON traces with `Recorder`
- **Replayer** — deterministic replay of recorded sessions with `Replayer`
- **Tool mocking** — fluent `ToolMock` and `MockToolkit` API with conditional returns, sequences, regex matching, and assertions
- **Evaluators** — 7 built-in evaluators:
  - `TaskCompletionEvaluator` — success status, errors, output checks
  - `SafetyEvaluator` — unsafe commands, PII detection, blocked tools, custom patterns
  - `CostEvaluator` — token/cost/call budgets
  - `LatencyEvaluator` — total and per-call latency limits
  - `ToolUsageEvaluator` — required/forbidden tools, retry limits, error rates
  - `LLMJudgeEvaluator` — LLM-graded evaluation (Anthropic & OpenAI)
  - `CompositeEvaluator` — combine evaluators with AND/OR logic
- **Benchmarking** — `BenchmarkRunner` with sync, async, and N-run modes
- **Model comparison** — `ModelComparison` with CSV/Markdown export
- **MCP server testing** — `MCPServerTester` for protocol compliance and tool schema validation
- **MCP assertions** — fluent `MCPAssertions` helper for test results
- **Console reporter** — Rich-based pretty output with `ConsoleReporter`
- **JSON reporter** — machine-readable output with `JSONReporter`
- **pytest plugin** — auto-registered fixtures (`agent_recorder`, `agent_toolkit`, `agent_eval_suite`), custom markers, and `.agent.yaml`/`.agent.json` test collectors
- **CLI** — 8 commands: `init`, `evaluate`, `replay`, `summary`, `diff`, `watch`, `serve`, `ui`
- **Web UI** — FastAPI dashboard for trace exploration and evaluation
- **Trace diffing** — `diff_traces()` for structured comparison between runs
- **Cost estimation** — built-in pricing for Claude, GPT-4o, O3, O4-mini models
