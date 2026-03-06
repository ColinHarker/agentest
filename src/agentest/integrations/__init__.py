"""Framework integrations for Agentest.

Auto-instrumentation and adapters for popular AI/agent frameworks:
- instrument(): Zero-code monkey-patching for anthropic/openai clients
- instrument_fastapi(): ASGI middleware for FastAPI/Starlette endpoints
- instrument_flask(): WSGI middleware for Flask endpoints
- LangChainAdapter: LangChain callback handler -> AgentTrace
- CrewAIAdapter: CrewAI crew execution -> AgentTrace
- AutoGenAdapter: AutoGen conversation -> AgentTrace
- LlamaIndexAdapter: LlamaIndex query pipeline -> AgentTrace
- ClaudeAgentSDKAdapter: Claude Agent SDK -> AgentTrace
- OpenAIAgentsAdapter: OpenAI Agents SDK -> AgentTrace
"""

from agentest.integrations.instrument import instrument, uninstrument
from agentest.integrations.middleware import (
    AgentestMiddleware,
    FlaskAgentestMiddleware,
    instrument_fastapi,
    instrument_flask,
)

__all__ = [
    "instrument",
    "uninstrument",
    "AgentestMiddleware",
    "FlaskAgentestMiddleware",
    "instrument_fastapi",
    "instrument_flask",
]
