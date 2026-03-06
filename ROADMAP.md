# Agentest Roadmap

## Vision

Become the go-to agent testing library — the "pytest for AI agents." Open-source, framework-agnostic, developer-first.

## Phase 1: Ship Quality (Complete)

- [x] Comprehensive README with logo, examples, comparison table
- [x] Full documentation site (Docusaurus)
- [x] CONTRIBUTING.md, CHANGELOG.md
- [x] Docstrings on all public APIs
- [x] GitHub Actions CI/CD (test, lint, type check, publish)
- [x] py.typed marker for mypy/pyright support
- [x] README badges (PyPI, tests, coverage, Python version, license)
- [x] Fix missing exports in `__init__.py`
- [x] Web UI frontend (functional dashboard)
- [x] Test coverage for all modules
- [x] Fix example bugs

## Phase 2: Framework Integrations (Complete)

- [x] **Auto-instrumentation**: `agentest.instrument()` that monkey-patches `anthropic` and `openai` clients to auto-record traces — zero code changes needed
- [x] **LangChain adapter**: `AgentestCallbackHandler` converts LangChain chain/agent runs to AgentTrace via callbacks (`pip install agentest[langchain]`)
- [x] **CrewAI adapter**: `record_crew()` and `CrewAIAdapter` record CrewAI crew executions (`pip install agentest[crewai]`)
- [x] **AutoGen adapter**: `record_autogen_chat()` and `AutoGenAdapter` record AutoGen conversations (`pip install agentest[autogen]`)
- [x] **LlamaIndex adapter**: `AgentestHandler` callback records LlamaIndex query pipelines (`pip install agentest[llamaindex]`)
- [x] **Claude Agent SDK integration**: `AgentestTracer` with `record()`, `record_async()`, and context manager
- [x] **OpenAI Agents SDK integration**: `AgentestTracer` with `record()`, `record_async()`, and context manager
- [x] **GitHub Action**: Composite action with configurable evaluators, cost/token limits, and JSON reports
- [x] Make FastAPI/uvicorn optional deps (`pip install agentest[web]`)

## Phase 3: Community & Content (Weeks 9-12)

### Community Channels
- [ ] Discord server (#getting-started, #showcase, #integrations)
- [ ] GitHub Discussions (Show & Tell, Q&A, Feature Requests)
- [ ] Twitter/X @agentest account
- [ ] Monthly newsletter "Agentest Digest"

### Content
- [ ] Blog: "Why Your AI Agent Needs Tests (And How to Write Them)"
- [ ] Blog: "Agentest: The Missing Testing Framework for AI Agents"
- [ ] Blog: "Testing LangChain Agents with Agentest"
- [ ] Blog: "Record, Replay, Mock: Deterministic AI Agent Testing"
- [ ] Blog: "Benchmarking Claude vs GPT-4o for Your Agent Tasks"
- [ ] 5 Stack Overflow Q&A posts (agent testing, tool mocking, MCP testing)
- [ ] Submit to awesome-python, awesome-llm, awesome-mcp, awesome-pytest lists
- [ ] YouTube: "Testing AI Agents in 5 Minutes" tutorial

### SEO & Discoverability
- [ ] Deploy docs to agentest.github.io
- [ ] GitHub repo topics: agent-testing, ai-agents, llm-evaluation, pytest-plugin, mcp
- [ ] Expand PyPI keywords and classifiers
- [ ] Create comparison pages (vs LangSmith, vs LangFuse, vs DeepEval)

## Phase 4: Growth & Advanced Features (Months 4-6)

### Advanced Features
- [ ] **Regression detection**: Compare traces across runs, flag performance/cost/behavior regressions
- [ ] **Dataset management**: Version-controlled test datasets with A/B testing support
- [ ] **Auto-instrumentation v2**: Middleware for FastAPI, Flask agent endpoints
- [ ] **Streaming trace recording**: Record traces incrementally during long-running agents
- [ ] **Custom metrics framework**: Plugin system for user-defined evaluation metrics
- [ ] **Statistical analysis**: Trend detection, confidence intervals, SLO tracking

### Developer Tools
- [ ] **VS Code extension**: View traces, run evaluations, explore results in the editor
- [ ] **Jupyter integration**: `%agentest` magic commands for notebook workflows
- [ ] **Pre-commit hook**: Auto-evaluate traces on commit

### Partnerships
- [ ] Partner with 2-3 agent framework maintainers for official integration
- [ ] Conference talks: PyCon, AI Engineer Summit
- [ ] Sponsor or co-host agent testing workshops

## Metrics to Track

| Metric | 6-Month Target | 12-Month Target |
|--------|---------------|-----------------|
| GitHub stars | 1,000 | 5,000 |
| PyPI weekly downloads | 5,000 | 25,000 |
| Dependent packages | 10 | 50 |
| Discord members | 200 | 1,000 |
| Integration packages | 5 | 10 |
| Blog post total views | 10,000 | 50,000 |

## Competitive Position

**Agentest is NOT**: a cloud observability platform (LangSmith/LangFuse), a dataset manager (Braintrust), or a monitoring tool (Arize Phoenix).

**Agentest IS**: the open-source, offline-first, developer-friendly testing toolkit for AI agents. Complementary to cloud platforms — use Agentest for local dev/CI, cloud tools for production monitoring.

Key differentiators:
1. Record & replay (unique)
2. Fluent tool mocking API (unique)
3. Built-in safety evaluation (unique)
4. MCP server testing (unique)
5. Native pytest integration (unique)
6. Framework-agnostic (vs LangChain-centric tools)
7. Free and open source (vs closed-source cloud platforms)
