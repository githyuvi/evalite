"""Wrap a synchronous agent function as an `AgentAdapter`.

Per ADR-002, all agent I/O runs on the asyncio event loop, bounded by a
semaphore across many concurrent test cases. Users with synchronous agent
code (blocking HTTP clients, SDKs without an async API, etc.) cannot
implement `AgentAdapter.send` directly without risking blocking the event
loop for every other in-flight case. `sync_adapter` offloads the call to
the default executor (a thread pool) so the loop stays free.
"""

import asyncio
from typing import Callable

from evalite.agent.protocol import AgentAdapter, AgentResponse


class _SyncAgentAdapter:
    """Adapts a sync `fn(messages) -> str` to the async `AgentAdapter` contract."""

    def __init__(self, fn: Callable[[list[dict]], str]) -> None:
        self._fn = fn

    async def send(self, messages: list[dict]) -> AgentResponse:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._fn, messages)
        return AgentResponse(content=result)


def sync_adapter(fn: Callable[[list[dict]], str]) -> AgentAdapter:
    """Wrap a synchronous `fn(messages: list[dict]) -> str` as an `AgentAdapter`.

    The function is run in the default executor via
    `loop.run_in_executor(None, fn, messages)`, so it never blocks the
    event loop, and its `str` result is wrapped into an `AgentResponse`.
    """
    return _SyncAgentAdapter(fn)
