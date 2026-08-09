"""Agent adapter contract.

Defines the structural interface (`AgentAdapter`) that any user-supplied
agent must satisfy to be run by evalite, and the response envelope
(`AgentResponse`) that adapters must return.

Per ADR-001, this is a `Protocol` rather than an ABC: users implement
`send` with a matching signature and never need to import from this
library. `runtime_checkable` allows the runner to perform an `isinstance`
startup check and fail fast with a clear error before any test cases run.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class AgentResponse:
    """The result of a single agent call.

    content: the agent's final text output.
    metadata: adapter-defined extra data (e.g. token usage, latency,
        tool calls). Free-form so adapters can attach whatever is useful
        to scorers/reporters without changing this contract.
    """

    content: str
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class AgentAdapter(Protocol):
    """Structural contract for anything evalite can run as an agent.

    `messages` follows standard chat format:
        [{"role": "user", "content": "..."}, ...]

    Implementations must be async (ADR-002): all I/O runs on the event
    loop, and the runner bounds concurrency with an `asyncio.Semaphore`
    across many simultaneous `send` calls. Sync agent code should be
    wrapped with `evalite.agent.sync_adapter.sync_adapter` rather than
    implementing this Protocol directly.
    """

    async def send(self, messages: list[dict]) -> AgentResponse: ...
