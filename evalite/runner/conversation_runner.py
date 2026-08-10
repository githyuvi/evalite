"""Multi-turn conversation execution engine.

`ConversationRunner` is the multi-turn counterpart to `Runner`
(see `evalite/runner/runner.py`). It drives a list of `ConversationTestCase`s
through an `AgentAdapter`, turn by turn, scoring each turn with the case's
`Scorer` (or `DefaultScorer` when none is given), optionally folding
per-turn scores into a final conversation-level score via an `Accumulator`,
and aggregates everything into a `RunResult` (per ADR-007).

Per ADR-002, concurrency is bounded with a single `asyncio.Semaphore`
created once in `__init__`. Unlike `Runner` — where the semaphore is held
around one case/iteration unit (one `adapter.send` + one `scorer.score`) —
here the semaphore is held around an entire conversation (all of its
turns). This is deliberate: `max_workers` means "how many full
conversations run concurrently," not "how many individual turns run
concurrently," which would let one slow conversation hog many turn-level
slots.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

from evalite.agent.protocol import AgentAdapter
from evalite.runner.result import CaseResult, RunResult
from evalite.scorer.default import DefaultScorer
from evalite.scorer.pipeline.accumulator import DefaultAccumulator
from evalite.testcase.conversation import ConversationTestCase


class ConversationRunner:
    """Executes a list of `ConversationTestCase`s against an `AgentAdapter`
    with bounded concurrency, one full conversation per semaphore slot."""

    def __init__(
        self,
        adapter: AgentAdapter,
        max_workers: int = 10,
        progress_callback: Callable[[dict], Awaitable[None]] | None = None,
    ) -> None:
        """
        Args:
            adapter: the agent under test. Must satisfy the `AgentAdapter`
                Protocol (validated eagerly via `isinstance`, since the
                Protocol is `runtime_checkable`), matching `Runner`.
            max_workers: maximum number of full conversations in flight at
                once, across the entire run. Unlike `Runner`, this bounds
                whole conversations (all turns), not individual turns —
                see module docstring.
            progress_callback: optional async callback, awaited once after
                each turn's (and any summary) `CaseResult` is produced —
                same contract as `Runner.progress_callback`, see
                `evalite/runner/runner.py` and `evalite/server/progress.py`.

        Raises:
            ValueError: if `adapter` does not implement `AgentAdapter`.
        """
        if not isinstance(adapter, AgentAdapter):
            raise ValueError(
                "adapter must implement AgentAdapter Protocol — missing async send(messages) method"
            )

        self._adapter = adapter
        self._max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._progress_callback = progress_callback

    async def _emit_progress(self, result: CaseResult) -> None:
        """Await the progress callback (if any) for one produced CaseResult."""
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

    async def _run_conversation_iteration(
        self, case: ConversationTestCase, iteration: int
    ) -> list[CaseResult]:
        """Run one full conversation (all turns) for (case, iteration).

        Unlike `Runner._run_case_iteration`, which returns exactly one
        `CaseResult`, this returns a list: one `CaseResult` per turn, plus
        (optionally) one trailing summary `CaseResult` for the accumulated
        final score.
        """
        scorer = case.scorer or DefaultScorer()

        # Precedence: explicit `accumulator` wins over `accumulate`;
        # `accumulate=True` with no `accumulator` uses `DefaultAccumulator`;
        # neither means no accumulation.
        accumulator = case.accumulator if case.accumulator is not None else (
            DefaultAccumulator() if case.accumulate else None
        )

        async with self._semaphore:
            history: list[dict] = [{"role": "user", "content": case.initial_message}]
            turn = 0
            expected = {"outcomes": case.expected_outcomes}

            # `CaseResult.iteration` is normally "which repetition of the
            # case" (see evalite/runner/result.py), but here it's
            # repurposed to mean "turn number within one conversation" —
            # there is no separate "turn" field on CaseResult. So the
            # outer conversation-repetition index (this method's
            # `iteration` argument) is encoded into `case_id` instead.
            conv_case_id = (
                case.id if case.iterations == 1 else f"{case.id}[iter={iteration}]"
            )

            case_results: list[CaseResult] = []
            acc_state = accumulator.initial() if accumulator is not None else None

            turn_input = case.initial_message

            while turn < case.max_turns:
                send_coro = self._adapter.send(history)
                if case.timeout_per_turn is not None:
                    start = time.perf_counter()
                    response = await asyncio.wait_for(
                        send_coro, timeout=case.timeout_per_turn
                    )
                    duration_ms = (time.perf_counter() - start) * 1000
                else:
                    start = time.perf_counter()
                    response = await send_coro
                    duration_ms = (time.perf_counter() - start) * 1000
                # asyncio.TimeoutError propagates uncaught if it fires —
                # matches Runner's existing fail-loud convention of not
                # catching per-case exceptions.

                history.append({"role": "assistant", "content": response.content})
                score = await scorer.score(turn_input, expected, response)

                turn_result = CaseResult(
                    case_id=conv_case_id,
                    iteration=turn,
                    input=turn_input,
                    actual=response.content,
                    score=score,
                    passed=score.passed,
                    duration_ms=duration_ms,
                )
                case_results.append(turn_result)
                await self._emit_progress(turn_result)

                if accumulator is not None:
                    acc_state = accumulator.update(acc_state, score)

                # Decide whether/how to continue.
                if case.driver is not None:
                    should_continue = await case.driver.should_continue(
                        history, response.content
                    )
                    if not should_continue:
                        break
                    next_message = await case.driver.next_message(
                        history, response.content
                    )
                elif case.turn_inputs is not None:
                    next_index = turn  # turn 0 consumed initial_message
                    if next_index >= len(case.turn_inputs):
                        break
                    next_message = case.turn_inputs[next_index]
                else:
                    # Neither driver nor turn_inputs: single follow-up
                    # turn only (ADR-007 Decision 1).
                    break

                history.append({"role": "user", "content": next_message})
                turn_input = next_message
                turn += 1

            # `turn` is only reliable as "index of the last executed turn"
            # when the loop exits via an explicit `break` (driver says
            # stop, or `turn_inputs` exhausted). When the loop instead
            # exits because `turn < case.max_turns` goes false, the final
            # iteration's body — including `turn += 1` — already ran to
            # completion before the condition was re-checked, so `turn`
            # has been incremented past the last executed turn. Using
            # `len(case_results)` sidesteps this: it holds exactly one
            # entry per turn executed so far (the summary row, if any, is
            # appended below), so it's correct across all three exit paths.
            total_turns = len(case_results)

            if accumulator is not None:
                final_score = accumulator.finalize(acc_state, total_turns)
                summary_result = CaseResult(
                    case_id=conv_case_id,
                    iteration=-1,  # sentinel: summary row, not a real turn
                    input=case.initial_message,
                    actual=f"Final accumulated score across {total_turns} turns.",
                    score=final_score,
                    passed=final_score.passed,
                    duration_ms=0.0,
                )
                case_results.append(summary_result)
                await self._emit_progress(summary_result)

        return case_results

    async def run(
        self, test_set_name: str, cases: list[ConversationTestCase]
    ) -> RunResult:
        """Run every case (and iteration) in `cases`, scoring each turn.

        All (case, iteration) units are scheduled concurrently via
        `asyncio.gather`, bounded by the shared semaphore from `__init__`
        — one semaphore slot per full conversation (see module docstring).

        Args:
            test_set_name: name recorded on the returned `RunResult`.
            cases: the conversation test cases to run.

        Returns:
            A `RunResult` aggregating pass/fail counts and per-turn (plus
            any summary) `CaseResult`s. Note: summary rows (`iteration=-1`)
            count toward `total`/`passed`/`failed` the same as turn rows —
            an accepted simplification for this phase.
        """
        start = time.perf_counter()

        tasks = [
            self._run_conversation_iteration(case, iteration)
            for case in cases
            for iteration in range(case.iterations)
        ]

        results_per_conversation = await asyncio.gather(*tasks) if tasks else []

        case_results: list[CaseResult] = [
            result for conversation_results in results_per_conversation
            for result in conversation_results
        ]

        total = len(case_results)
        passed = sum(1 for result in case_results if result.passed)
        failed = total - passed
        pass_rate = passed / total if total > 0 else 0.0

        duration_ms = (time.perf_counter() - start) * 1000

        return RunResult(
            test_set_name=test_set_name,
            total=total,
            passed=passed,
            failed=failed,
            pass_rate=pass_rate,
            case_results=case_results,
            duration_ms=duration_ms,
        )
