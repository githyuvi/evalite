"""Fan-out of live run progress events to WebSocket subscribers.

The runner (a background task started by `POST /api/v1/runs`, wired up in
a later task) publishes progress events onto a `ProgressBus` as it works
through a run. The WebSocket route (`/ws/v1/runs/{run_id}`, also a later
task) subscribes to the bus for a given `run_id` and streams events to
the connected client as they arrive.

Event shape (dicts, JSON-serializable, matching the API contract in
`docs/plans/phase-4-api-server.md`):

    {"event": "case_started",   "case_id": "...", "iteration": 0}
    {"event": "case_completed", "case_id": "...", "iteration": 0, "passed": true, "score": 0.9}
    {"event": "run_completed",  "run_id": "...", "passed": 8, "failed": 2, "pass_rate": 0.8}
    {"event": "run_failed",     "run_id": "...", "error": "..."}

`run_completed` and `run_failed` are terminal: `subscribe` stops
iterating (and the bus drops the per-run queue) once one of these is
yielded, since no further events are expected for that `run_id`.
"""

import asyncio
from collections.abc import AsyncGenerator


class ProgressBus:
    """Per-run_id fan-out of progress events to WebSocket subscribers.

    Each run_id gets its own `asyncio.Queue`. `publish` pushes an event
    dict onto that run's queue (creating the queue on first use).
    `subscribe` returns an async generator that yields events from the
    queue as they arrive, stopping after a "run_completed" or
    "run_failed" event (and cleaning up the queue for that run_id at that
    point).
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}

    def _get_queue(self, run_id: str) -> asyncio.Queue:
        """Return the queue for `run_id`, creating it on first use."""
        if run_id not in self._queues:
            self._queues[run_id] = asyncio.Queue()
        return self._queues[run_id]

    async def publish(self, run_id: str, event: dict) -> None:
        """Push an event onto run_id's queue.

        Args:
            run_id: id of the run this event belongs to.
            event: a JSON-serializable event dict (see module docstring
                for the shape).
        """
        await self._get_queue(run_id).put(event)

    async def subscribe(self, run_id: str) -> AsyncGenerator[dict, None]:
        """Async-generator: yields events for run_id until a terminal event.

        A fresh queue is created on first subscribe if `publish` hasn't
        been called yet for this `run_id`, so subscribing early (before
        any events are published) is safe and simply blocks until the
        first event arrives.

        Args:
            run_id: id of the run to stream events for.

        Yields:
            Event dicts in publish order, stopping (and cleaning up the
            queue for `run_id`) after a "run_completed" or "run_failed"
            event.
        """
        queue = self._get_queue(run_id)
        while True:
            event = await queue.get()
            yield event
            if event.get("event") in ("run_completed", "run_failed"):
                self._queues.pop(run_id, None)
                return
