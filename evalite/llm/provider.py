"""LLMProvider contract.

Defines the structural interface (`LLMProvider`) that any user-supplied or
built-in LLM client must satisfy to be used as an LLM judge in evalite
(e.g. by a future `LLMJudgeScorer`).

Per ADR-006, this is a `Protocol` rather than an ABC: implementations
never need to import from this library to satisfy the contract, and users
can plug in a completely custom adapter for internal or private models
with no exposed external API.
"""

from typing import Protocol


class LLMProvider(Protocol):
    """Structural contract for anything evalite can use as an LLM judge.

    `messages` follows standard chat format:
        [{"role": "user", "content": "..."}, ...]

    Implementations must be async (ADR-002): all I/O runs on the event
    loop, and callers (e.g. an LLM-judge scorer run through the runner)
    bound concurrency with an `asyncio.Semaphore` across many
    simultaneous `complete` calls.
    """

    async def complete(self, messages: list[dict], **kwargs) -> str: ...
