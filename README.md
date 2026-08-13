# evalite

A lightweight, model-agnostic agent evaluation framework for Python. Define
test cases in YAML, point them at any agent (async or sync, any LLM
provider or none at all), and get pass/fail results — from the CLI, or as a
REST/WebSocket API with a live dashboard.

evalite has almost no required dependencies (`pydantic`, `pyyaml`, `typer`,
`httpx`) and everything else — persistent storage, LLM-judge scoring,
semantic similarity, the API server, the dashboard — is an opt-in extra.
Your agent adapter never needs to import from evalite at all: it just needs
an async `send(messages)` method.

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
pip install evalite-ui           # React dashboard (separate package, needs [server])
```

## Quickstart

**1. Write an agent adapter** — any object with an async `send`:

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

No import from `evalite` required — this is a plain structural (`Protocol`)
contract, not an interface you inherit from.

**2. Write a test set:**

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

**3. Run it:**

```bash
evalite run test-set.yaml --agent agent.py
```

Exit code reflects pass/fail, so it drops straight into CI.

## Beyond the basics

- `--db sqlite:///evalite.db` persists every run (`[storage]` extra).
- `evalite results --db sqlite:///evalite.db` lists/inspects past runs.
- `evalite serve` starts a REST + WebSocket API server (`[server]` extra) —
  pair it with `pip install evalite-ui` for a browser dashboard showing live
  run progress.
- Built-in scorers beyond exact/substring match: JSON path, regex, tool-call
  verification, semantic similarity, and an LLM-judge pipeline
  (extract → classify → weighted score) that's model-agnostic across
  OpenAI, Anthropic, Azure OpenAI, Ollama, or any LiteLLM-supported model.
- Multi-turn conversation evaluation, with either scripted or LLM-driven
  follow-up turns.
- `--proxy` / `--ca-bundle` / `--client-cert` / `--client-key` and
  automatic secret redaction in logs, for corporate/regulated deployments.

## License

MIT — see [LICENSE](https://github.com/githyuvi/evalite/blob/main/LICENSE).
