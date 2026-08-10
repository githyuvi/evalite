"""Test set execution engine.

`Runner` drives a `TestSet` through an `AgentAdapter`, scores each response
with a `Scorer`, and aggregates the results into a `RunResult`.

Per ADR-002, concurrency is bounded with a single `asyncio.Semaphore`
created once in `__init__` and shared across the entire run. Every
case/iteration unit in the test set is scheduled as a coroutine and
gathered together, so `max_workers` bounds the number of concurrent
`adapter.send` + `scorer.score` calls (per case/iteration unit) across
the whole test set at any point in time — not per test case.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

from evalite.agent.protocol import AgentAdapter
from evalite.runner.result import CaseResult, RunResult
from evalite.scorer.base import Scorer
from evalite.storage.base import StorageBackend
from evalite.testcase.models import TestCase, TestSet


class Runner:
    """Executes a `TestSet` against an `AgentAdapter` with bounded concurrency."""

    def __init__(
        self,
        adapter: AgentAdapter,
        scorer: Scorer,
        max_workers: int = 10,
        storage: StorageBackend | None = None,
        progress_callback: Callable[[dict], Awaitable[None]] | None = None,
    ) -> None:
        """
        Args:
            adapter: the agent under test. Must satisfy the `AgentAdapter`
                Protocol (validated eagerly via `isinstance`, since the
                Protocol is `runtime_checkable`).
            scorer: scores each agent response against the case's expected
                output. Not validated with `isinstance` — `Scorer` is not
                `runtime_checkable` (see `evalite/scorer/base.py`).
            max_workers: maximum number of case/iteration units in flight
                at once, across the entire run — bounds `adapter.send`
                and `scorer.score` together, since both run inside the
                same semaphore-held block.
            storage: optional `StorageBackend` to persist the `RunResult`
                to after each run (see `evalite/storage/base.py`). Storage
                is opt-in per ADR-003 — when `None` (the default), `run`
                behaves exactly as it did in Phase 1: no persistence, and
                `RunResult.run_id` stays `None`.
            progress_callback: optional async callback, awaited twice per
                case/iteration unit: once right before `adapter.send` is
                called, with a `{"event": "case_started", "case_id",
                "iteration"}` dict, and once after the resulting
                `CaseResult` is produced, with a `{"event":
                "case_completed", "case_id", "iteration", "passed",
                "score"}` dict (see `evalite/server/progress.py` for the
                full event-shape contract). Used by the API server
                (Phase 4) to stream live progress over WebSocket; entirely
                optional and has no effect on `run`'s return value or on
                existing callers that don't pass it.

        Raises:
            ValueError: if `adapter` does not implement `AgentAdapter`.
        """
        if not isinstance(adapter, AgentAdapter):
            raise ValueError(
                "adapter must implement AgentAdapter Protocol — missing async send(messages) method"
            )

        self._adapter = adapter
        self._scorer = scorer
        self._max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._storage = storage
        self._progress_callback = progress_callback

    async def _run_case_iteration(self, case: TestCase, iteration: int) -> CaseResult:
        """Run a single (case, iteration) unit: send, time, score, wrap result."""
        messages = [{"role": "user", "content": case.input}]

        async with self._semaphore:
            if self._progress_callback is not None:
                await self._progress_callback(
                    {
                        "event": "case_started",
                        "case_id": case.id,
                        "iteration": iteration,
                    }
                )

            start = time.perf_counter()
            response = await self._adapter.send(messages)
            duration_ms = (time.perf_counter() - start) * 1000

            score = await self._scorer.score(case.input, case.expected.model_dump(), response)

        result = CaseResult(
            case_id=case.id,
            iteration=iteration,
            input=case.input,
            actual=response.content,
            score=score,
            passed=score.passed,
            duration_ms=duration_ms,
        )

        if self._progress_callback is not None:
            await self._progress_callback(
                {
                    "event": "case_completed",
                    "case_id": result.case_id,
                    "iteration": result.iteration,
                    "passed": result.passed,
                    "score": result.score.value,
                }
            )

        return result

    async def run(self, test_set: TestSet) -> RunResult:
        """Run every case (and iteration) in `test_set`, scoring each response.

        All case/iteration units are scheduled concurrently via
        `asyncio.gather`, bounded by the shared semaphore from `__init__`.

        Args:
            test_set: the test cases to run.

        Returns:
            A `RunResult` aggregating pass/fail counts and per-case results.
            If a `StorageBackend` was configured in `__init__`, the run is
            persisted via `storage.save_run` before returning, and the
            returned `RunResult.run_id` is set to the id it was stored
            under; otherwise `run_id` stays `None`.
        """
        start = time.perf_counter()

        tasks = [
            self._run_case_iteration(case, iteration)
            for case in test_set.cases
            for iteration in range(case.iterations)
        ]

        case_results = await asyncio.gather(*tasks) if tasks else []

        total = len(case_results)
        passed = sum(1 for result in case_results if result.passed)
        failed = total - passed
        pass_rate = passed / total if total > 0 else 0.0

        duration_ms = (time.perf_counter() - start) * 1000

        result = RunResult(
            test_set_name=test_set.name,
            total=total,
            passed=passed,
            failed=failed,
            pass_rate=pass_rate,
            case_results=list(case_results),
            duration_ms=duration_ms,
        )

        if self._storage is not None:
            run_id = await self._storage.save_run(result)
            result.run_id = run_id

        return result
