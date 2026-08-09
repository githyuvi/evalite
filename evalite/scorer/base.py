"""Scorer contract.

Defines the structural interface any scorer must satisfy to be run by
evalite. Like `AgentAdapter` (see ADR-001), this is a `Protocol` rather
than an ABC: a scorer implementation never needs to import from this
library to satisfy the contract.

Unlike `AgentAdapter`, this Protocol is not `runtime_checkable` — scorers
are always library-internal (built-in scorers, or user scorers passed
directly into the runner's config), so there is no need for an
`isinstance` startup check.
"""

from typing import Protocol

from evalite.agent.protocol import AgentResponse
from evalite.runner.result import Score


class Scorer(Protocol):
    """Structural contract for anything evalite can use to score a case.

    Implementations must be async (ADR-002): all I/O (e.g. an LLM-judge
    call) runs on the event loop, and the runner bounds concurrency
    across many simultaneous `score` calls.
    """

    async def score(
        self,
        input: str,
        expected: dict,
        actual: AgentResponse,
    ) -> Score: ...
