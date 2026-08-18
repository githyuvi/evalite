# evalite

[![PyPI version](https://img.shields.io/pypi/v/evalite.svg)](https://pypi.org/project/evalite/)
[![Python versions](https://img.shields.io/pypi/pyversions/evalite.svg)](https://pypi.org/project/evalite/)
[![License: MIT](https://img.shields.io/pypi/l/evalite.svg)](https://github.com/githyuvi/evalite/blob/main/LICENSE)

## Introduction

**evalite** is a lightweight, fully customizable framework for evaluating
LLM systems. Every extension point, agents and scorers alike, is a plain
structural contract: an object with the right method, nothing to import
from evalite and nothing to inherit from.

evalite incorporates a range of built-in scorers: exact/substring match,
JSON path, regex, tool-call verification, semantic similarity, and an
LLM-judge pipeline (extract, classify, weighted score) that works across
OpenAI, Anthropic, Azure OpenAI, Ollama, or any LiteLLM-supported model.
It can cover any kind of evaluation, from a simple string check to a full
graded rubric.

evalite can evaluate:

- **Any LLM system end-to-end, as a black box.** A single LLM call, a
  tool-using agent, or a RAG pipeline, through a plain `send(messages)`
  method.
- **Multi-turn conversations**, with scripted or LLM-generated follow-up
  turns.
- **Individual scorers on their own**, without the runner or CLI.

Required dependencies are minimal (`pydantic`, `pyyaml`, `typer`, `httpx`).
Persistent storage, LLM-judge scoring, semantic similarity, and the API
server are opt-in extras.

## Install

```bash
pip install evalite
```

Optional extras, install only what you need:

```bash
pip install "evalite[storage]"   # persist runs to SQLite/PostgreSQL
pip install "evalite[server]"    # REST + WebSocket API server
pip install "evalite[semantic]"  # embedding-based similarity scorer
pip install "evalite[litellm]"   # LLM judge via any LiteLLM-supported model
```

## Quickstart

**1. Write an agent adapter:**

```python
# agent.py
from dataclasses import dataclass, field

@dataclass
class AgentResponse:
    content: str
    metadata: dict = field(default_factory=dict)

class Agent:
    async def send(self, messages: list[dict]) -> AgentResponse:
        last = messages[-1]["content"] if messages else ""
        return AgentResponse(content=last)
```

**2. Write a test set.** Single-turn cases can be defined in YAML:

```yaml
# test-set.yaml
name: echo_agent_smoke_test
cases:
  - id: smoke_001
    input: "the answer is 42"
    expected:
      contains: "42"
    tags: [smoke]
    iterations: 1
```

Multi-turn conversations are defined directly in Python instead; see
Features below.

**3. Run it:**

```bash
evalite run test-set.yaml --agent agent.py
```

The exit code reflects pass/fail, so this drops straight into CI.

## Features

- **Persistent storage**, SQLite or PostgreSQL (`[storage]` extra):
  `--db` on `evalite run` persists a run, `evalite results` lists and
  inspects past runs, `evalite db migrate` prepares a fresh database file.
- **Built-in scorers**: exact/substring match, JSON path, regex,
  tool-call verification, semantic similarity, and an LLM-judge pipeline
  (extract, classify, weighted score) across OpenAI, Anthropic, Azure
  OpenAI, Ollama, or any LiteLLM-supported model. A scorer is a plain
  async `Protocol` (`score(input, expected, actual)`), so a custom scorer
  plugs in exactly like a built-in one, no subclassing required.
- **Conversation Runner**: `ConversationRunner` executes multi-turn
  `ConversationTestCase`s. Follow-up turns can be a static, deterministic
  `turn_inputs` list, or generated dynamically by a `ConversationDriver`
  you implement, including one backed by an LLM.
- `evalite serve` starts a REST + WebSocket API server (`[server]` extra)
  for programmatic access to runs and live progress.
- Proxy, mutual TLS, and custom CA-bundle support, plus automatic secret
  redaction in logs, for running evalite in regulated or enterprise
  network environments.

## Examples

See [evalite-demos](https://github.com/githyuvi/evalite-demos) for full
example applications built with evalite: an agent under test, an eval
suite scored against it, and a viewer for the results.

## Documentation

See the [docs folder](https://github.com/githyuvi/evalite/tree/main/docs):
[Protocols](https://github.com/githyuvi/evalite/blob/main/docs/protocols.md)
for the `AgentAdapter`, `Scorer`, and `ConversationDriver` extension
points, and the [CLI reference](https://github.com/githyuvi/evalite/blob/main/docs/cli.md)
for `run`, `serve`, `db migrate`, and `results`.

## Contributing

See [CONTRIBUTING.md](https://github.com/githyuvi/evalite/blob/main/CONTRIBUTING.md).

## License

MIT — see [LICENSE](https://github.com/githyuvi/evalite/blob/main/LICENSE).
