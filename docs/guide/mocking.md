---
sidebar_position: 3
title: Tool Mocking
---

# Tool Mocking

`ToolMock` and `MockToolkit` provide a fluent API for mocking tool calls in agent tests.

## MockToolkit

```python
from agentest import MockToolkit

toolkit = MockToolkit()
toolkit.mock("read_file").returns("file contents")
result = toolkit.execute("read_file", path="test.txt")  # "file contents"
```

## Conditional Returns

```python
toolkit.mock("search") \
    .when(query="python").returns(["python result"]) \
    .when(query="rust").returns(["rust result"]) \
    .otherwise().returns([])
```

Conditions support regex matching for string arguments.

## Sequential Returns

```python
toolkit.mock("get_page").returns_sequence(["page 1", "page 2", "page 3"])
```

## Custom Logic

```python
toolkit.mock("calculator").responds_with(lambda args: args["a"] + args["b"])
```

## Error Simulation

```python
toolkit.mock("flaky_api").raises(TimeoutError("service unavailable"))
```

## Assertions

```python
toolkit.mock("read_file").assert_called()
toolkit.mock("read_file").assert_called_times(1)
toolkit.mock("read_file").assert_called_with(path="test.txt")
toolkit.assert_all_called()  # all registered mocks called at least once
```

## Resolution Order

When a mock is called, the result is resolved in this order:

1. Custom handler (`.responds_with(...)`)
2. Sequence (`.returns_sequence(...)`)
3. Conditional match (`.when(...).returns(...)`)
4. Default value (`.returns(...)` or `.raises(...)`)
