"""Tests for `evalite.server.progress.ProgressBus`."""

from evalite.server.progress import ProgressBus


async def test_publish_then_subscribe_yields_event() -> None:
    # A "case_started" event is non-terminal, so `subscribe` keeps the
    # generator open waiting for more events after yielding it — draining
    # the generator fully here (e.g. via a list comprehension) would hang
    # forever. Pull exactly one item instead.
    bus = ProgressBus()
    event = {"event": "case_started", "case_id": "c1", "iteration": 0}

    await bus.publish("run-1", event)

    received = await bus.subscribe("run-1").__anext__()

    assert received == event


async def test_multiple_events_yielded_in_order() -> None:
    bus = ProgressBus()
    events = [
        {"event": "case_started", "case_id": "c1", "iteration": 0},
        {"event": "case_completed", "case_id": "c1", "iteration": 0, "passed": True, "score": 0.9},
        {"event": "run_completed", "run_id": "run-1", "passed": 1, "failed": 0, "pass_rate": 1.0},
    ]

    for event in events:
        await bus.publish("run-1", event)

    received = [e async for e in bus.subscribe("run-1")]

    assert received == events


async def test_generator_terminates_after_run_completed() -> None:
    bus = ProgressBus()
    await bus.publish("run-1", {"event": "case_started", "case_id": "c1", "iteration": 0})
    await bus.publish(
        "run-1", {"event": "run_completed", "run_id": "run-1", "passed": 1, "failed": 0, "pass_rate": 1.0}
    )
    # Anything published after the terminal event belongs to a would-be
    # fresh queue and must not be consumed by this subscription.
    received = [e async for e in bus.subscribe("run-1")]

    assert len(received) == 2
    assert received[-1]["event"] == "run_completed"
    assert "run-1" not in bus._queues


async def test_generator_terminates_after_run_failed() -> None:
    bus = ProgressBus()
    await bus.publish("run-1", {"event": "run_failed", "run_id": "run-1", "error": "boom"})

    received = [e async for e in bus.subscribe("run-1")]

    assert received == [{"event": "run_failed", "run_id": "run-1", "error": "boom"}]
    assert "run-1" not in bus._queues


async def test_fresh_subscribe_after_termination_gets_new_queue() -> None:
    bus = ProgressBus()
    await bus.publish("run-1", {"event": "run_completed", "run_id": "run-1", "passed": 1, "failed": 0, "pass_rate": 1.0})

    first = [e async for e in bus.subscribe("run-1")]
    assert len(first) == 1

    # A brand-new subscribe on the same run_id after termination should
    # not replay the old event — it gets a fresh, empty queue and blocks
    # until something new is published. "case_started" is non-terminal,
    # so fully draining the generator here would hang forever — pull
    # exactly one item instead (mirrors test_publish_then_subscribe_yields_event).
    await bus.publish("run-1", {"event": "case_started", "case_id": "c2", "iteration": 0})
    second = await bus.subscribe("run-1").__anext__()
    assert second == {"event": "case_started", "case_id": "c2", "iteration": 0}


async def test_subscribe_before_publish_waits_for_event() -> None:
    bus = ProgressBus()

    async def publisher():
        await bus.publish("run-2", {"event": "case_started", "case_id": "c1", "iteration": 0})
        await bus.publish(
            "run-2", {"event": "run_completed", "run_id": "run-2", "passed": 1, "failed": 0, "pass_rate": 1.0}
        )

    import asyncio

    consume_task = asyncio.create_task(_collect(bus, "run-2"))
    await publisher()
    received = await consume_task

    assert len(received) == 2
    assert received[-1]["event"] == "run_completed"


async def _collect(bus: ProgressBus, run_id: str) -> list[dict]:
    return [e async for e in bus.subscribe(run_id)]
