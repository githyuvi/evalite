# Protocols

evalite has three structural extension points. Each is a plain
`typing.Protocol`: implement the right method(s) and you're done. Nothing
to import from evalite, nothing to inherit from.

## AgentAdapter

The system under test.

```python
@runtime_checkable
class AgentAdapter(Protocol):
    async def send(self, messages: list[dict]) -> AgentResponse: ...
```

- `messages` is standard chat format: `[{"role": "user", "content": "..."}, ...]`.
- Must return an `AgentResponse(content: str, metadata: dict = {})`.
- Must be async. Wrap synchronous agent code with
  `evalite.agent.sync_adapter.sync_adapter` rather than implementing this
  Protocol directly.
- This is the one Protocol that's `runtime_checkable`: the runner does an
  `isinstance` check at startup and fails fast with a clear error before
  any test cases run.

## Scorer

Decides whether a response passes.

```python
class Scorer(Protocol):
    async def score(self, input: str, expected: dict, actual: AgentResponse) -> Score: ...
```

- Must be async: an LLM-judge scorer needs to make an HTTP call, and the
  runner bounds concurrency across many simultaneous `score` calls.
- Built-in scorers: exact/substring match (`DefaultScorer`, the default
  when none is given), JSON path, regex, tool-call verification, semantic
  similarity, and an LLM-judge pipeline. See `evalite/scorer/`.
- A scorer can be called directly and standalone, outside the runner or
  CLI, since it's just an async method on a plain object.

## ConversationDriver

Drives the "test user" side of a multi-turn conversation, used by
`ConversationTestCase` / `ConversationRunner`.

```python
class ConversationDriver(Protocol):
    async def next_message(self, history: list[dict], response: str) -> str: ...
    async def should_continue(self, history: list[dict], response: str) -> bool: ...
```

- Only needed for dynamic follow-ups. For a fixed, scripted sequence of
  follow-up messages, pass `turn_inputs: list[str]` to
  `ConversationTestCase` instead; no driver required.
- `next_message` can call an LLM to generate the next turn;
  `should_continue` decides when the conversation ends.
- Named `ConversationDriver` rather than "test user agent" specifically to
  avoid confusion with `AgentAdapter`, which refers to the system under
  test.
