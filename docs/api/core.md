---
sidebar_position: 1
title: Core Models
---

# Core Models

Core data models for representing agent traces, tool calls, and LLM responses.

### `Role`

`agentest.core.Role`

Enum for message roles: `"user"`, `"assistant"`, `"system"`, `"tool"`.

### `ToolCall`

`agentest.core.ToolCall`

Represents a single tool invocation with name, arguments, result, duration, and error status.

### `LLMResponse`

`agentest.core.LLMResponse`

Represents an LLM API call with model, content, token counts, latency, and cost.

### `Message`

`agentest.core.Message`

A message in the agent conversation with role, content, and timestamp.

### `AgentTrace`

`agentest.core.AgentTrace`

The core trace object containing messages, tool calls, LLM responses, metadata, timing, and success status. Provides computed properties for total tokens, cost, and duration.

### `TraceSession`

`agentest.core.TraceSession`

A collection of related traces for multi-session workflows.

## Cost Estimation

Agentest includes built-in cost estimation for LLM API calls based on per-model token pricing.

### `DEFAULT_MODEL_PRICING`

`agentest.core.DEFAULT_MODEL_PRICING`

A dict mapping model names to `(input_price_per_1M, output_price_per_1M)` tuples. Built-in models and their rates (USD per 1M tokens):

| Model | Input | Output |
|-------|-------|--------|
| `claude-opus-4-6` | 15.00 | 75.00 |
| `claude-sonnet-4-6` | 3.00 | 15.00 |
| `claude-haiku-4-5` | 0.80 | 4.00 |
| `gpt-4o` | 2.50 | 10.00 |
| `gpt-4o-mini` | 0.15 | 0.60 |
| `gpt-4.1` | 2.00 | 8.00 |
| `gpt-4.1-mini` | 0.40 | 1.60 |
| `gpt-4.1-nano` | 0.10 | 0.40 |
| `o3` | 2.00 | 8.00 |
| `o4-mini` | 1.10 | 4.40 |
| `gemini-2.5-pro` | 1.25 | 10.00 |
| `gemini-2.5-flash` | 0.15 | 0.60 |

### `set_model_pricing()`

`agentest.core.set_model_pricing`

Register custom pricing for a model (per 1M tokens). Custom pricing takes precedence over built-in defaults.

```python
set_model_pricing(model: str, input_price_per_1m: float, output_price_per_1m: float) -> None
```

### `unset_model_pricing()`

`agentest.core.unset_model_pricing`

Remove custom pricing for a model. Raises `KeyError` if the model has no custom pricing set.

```python
unset_model_pricing(model: str) -> None
```

### `reset_model_pricing()`

`agentest.core.reset_model_pricing`

Remove all custom pricing overrides, reverting to the built-in defaults.

```python
reset_model_pricing() -> None
```

### `get_model_pricing()`

`agentest.core.get_model_pricing`

Get the full pricing table (built-in defaults merged with custom overrides). Custom entries take precedence.

```python
get_model_pricing() -> dict[str, tuple[float, float]]
```

### `LLMResponse.cost_estimate`

`agentest.core.LLMResponse.cost_estimate`

A read-only property that estimates the cost of an LLM response based on model pricing and token counts. The lookup strategy is:

1. **Exact match** -- if the model name matches a key in the pricing table, use that price.
2. **Longest prefix match** -- if no exact match, find the pricing entry whose key is the longest prefix of the model name (e.g., `"claude-sonnet-4-6-20250514"` matches `"claude-sonnet-4-6"`).
3. **Fallback** -- if no match is found, returns `0.0`.

```python
response = LLMResponse(model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
response.cost_estimate  # (1000 * 3.0 / 1_000_000) + (500 * 15.0 / 1_000_000)
```

### `diff_traces()`

`agentest.core.diff_traces`

Compare two `AgentTrace` objects and return structured deltas for tokens, cost, duration, tool calls, and errors.
