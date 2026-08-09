import asyncio
import time

import pytest

from evalite.agent.protocol import AgentResponse
from evalite.agent.sync_adapter import sync_adapter


def blocking_echo(messages: list[dict]) -> str:
    return f"echo:{messages[0]['content']}"


def blocking_sleep(messages: list[dict]) -> str:
    time.sleep(0.3)
    return "slept"


@pytest.mark.asyncio
async def test_sync_adapter_returns_agent_response():
    adapter = sync_adapter(blocking_echo)
    result = await adapter.send([{"role": "user", "content": "hi"}])

    assert isinstance(result, AgentResponse)
    assert result.content == "echo:hi"


@pytest.mark.asyncio
async def test_sync_adapter_does_not_block_event_loop():
    adapter = sync_adapter(blocking_sleep)

    start = time.perf_counter()
    results = await asyncio.gather(
        adapter.send([{"role": "user", "content": "hi"}]),
        asyncio.sleep(0.3),
    )
    elapsed = time.perf_counter() - start

    # If run_in_executor were blocking the loop, total time would be
    # ~0.6s (sum). Running concurrently, it should be close to ~0.3s (max).
    assert elapsed < 0.5
    assert isinstance(results[0], AgentResponse)
    assert results[0].content == "slept"
