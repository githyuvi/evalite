import asyncio

import pytest

from evalite.agent.protocol import AgentResponse
from evalite.runner.conversation_runner import ConversationRunner
from evalite.runner.result import Score
from evalite.testcase.conversation import ConversationTestCase


class MockAdapter:
    """Fake AgentAdapter: echoes back a canned response per call."""

    def __init__(self, response_fn=None) -> None:
        # response_fn(messages) -> str content. Defaults to a fixed "ok".
        self._response_fn = response_fn or (lambda messages: "ok")

    async def send(self, messages: list[dict]) -> AgentResponse:
        content = self._response_fn(messages)
        return AgentResponse(content=content)


class ConcurrencyTrackingAdapter:
    """Fake AgentAdapter that tracks the max number of concurrent in-flight
    sends. Since each conversation only has one send in flight at a time
    (turns run sequentially within a conversation), the max observed here
    reflects the number of concurrent *conversations*, which is exactly
    what ConversationRunner's semaphore is meant to bound."""

    def __init__(self) -> None:
        self.current = 0
        self.max_seen = 0

    async def send(self, messages: list[dict]) -> AgentResponse:
        self.current += 1
        self.max_seen = max(self.max_seen, self.current)
        await asyncio.sleep(0.01)
        self.current -= 1
        return AgentResponse(content="ok")


class SlowAdapter:
    """Fake AgentAdapter that always takes longer than the configured
    per-turn timeout, to exercise asyncio.wait_for's TimeoutError path."""

    async def send(self, messages: list[dict]) -> AgentResponse:
        await asyncio.sleep(0.2)
        return AgentResponse(content="ok")


class MockScorer:
    """Fake Scorer: passes if 'match' is a key in expected outcomes and a
    substring of actual.content."""

    async def score(self, input: str, expected: dict, actual: AgentResponse) -> Score:
        found = "match" in actual.content
        return Score(passed=found, value=1.0 if found else 0.0, reasoning="mock scorer")


class SequenceScorer:
    """Fake Scorer that returns a predetermined sequence of Score.value on
    successive calls, for testing accumulator averaging deterministically."""

    def __init__(self, values: list[float]) -> None:
        self._values = values
        self._calls = 0

    async def score(self, input: str, expected: dict, actual: AgentResponse) -> Score:
        value = self._values[self._calls]
        self._calls += 1
        return Score(passed=value >= 1.0, value=value, reasoning="sequence scorer")


class ScriptedDriver:
    """Fake ConversationDriver: should_continue follows a scripted list of
    bools (one per call); next_message always returns a fixed string."""

    def __init__(self, continue_script: list[bool], message: str = "follow-up") -> None:
        self._continue_script = continue_script
        self._message = message
        self.should_continue_calls = 0
        self.next_message_calls = 0

    async def should_continue(self, history: list[dict], response: str) -> bool:
        result = self._continue_script[self.should_continue_calls]
        self.should_continue_calls += 1
        return result

    async def next_message(self, history: list[dict], response: str) -> str:
        self.next_message_calls += 1
        return self._message


class AlwaysContinueDriver:
    """Fake ConversationDriver that always continues — used to prove
    max_turns (not the driver) bounds the conversation length."""

    async def should_continue(self, history: list[dict], response: str) -> bool:
        return True

    async def next_message(self, history: list[dict], response: str) -> str:
        return "keep going"


def _make_case(**overrides) -> ConversationTestCase:
    defaults = dict(
        id="case-1",
        initial_message="hello",
        expected_outcomes=["match"],
    )
    defaults.update(overrides)
    return ConversationTestCase(**defaults)


@pytest.mark.asyncio
async def test_turn_inputs_drive_conversation_until_exhausted():
    case = _make_case(
        turn_inputs=["ok", "thanks"],
        max_turns=10,
        scorer=MockScorer(),
    )
    adapter = MockAdapter(response_fn=lambda messages: "match")
    runner = ConversationRunner(adapter=adapter)

    result = await runner.run("turn-inputs-set", [case])

    assert len(result.case_results) == 3
    assert sorted(cr.iteration for cr in result.case_results) == [0, 1, 2]
    assert all(cr.case_id == "case-1" for cr in result.case_results)


@pytest.mark.asyncio
async def test_driver_ends_conversation_before_max_turns():
    driver = ScriptedDriver(continue_script=[True, True, False])
    case = _make_case(driver=driver, max_turns=10, scorer=MockScorer())
    adapter = MockAdapter(response_fn=lambda messages: "match")
    runner = ConversationRunner(adapter=adapter)

    result = await runner.run("driver-set", [case])

    assert len(result.case_results) == 3
    assert sorted(cr.iteration for cr in result.case_results) == [0, 1, 2]
    assert driver.should_continue_calls == 3
    assert driver.next_message_calls == 2


@pytest.mark.asyncio
async def test_no_driver_no_turn_inputs_single_follow_up_turn():
    case = _make_case(scorer=MockScorer())
    adapter = MockAdapter(response_fn=lambda messages: "match")
    runner = ConversationRunner(adapter=adapter)

    result = await runner.run("single-turn-set", [case])

    assert len(result.case_results) == 1
    assert result.case_results[0].iteration == 0


@pytest.mark.asyncio
async def test_max_turns_stops_conversation_with_always_continuing_driver():
    driver = AlwaysContinueDriver()
    case = _make_case(driver=driver, max_turns=3, scorer=MockScorer())
    adapter = MockAdapter(response_fn=lambda messages: "match")
    runner = ConversationRunner(adapter=adapter)

    result = await runner.run("max-turns-set", [case])

    assert len(result.case_results) == 3
    assert sorted(cr.iteration for cr in result.case_results) == [0, 1, 2]


@pytest.mark.asyncio
async def test_accumulate_true_appends_summary_row_with_averaged_score():
    scorer = SequenceScorer(values=[1.0, 0.5])
    case = _make_case(
        turn_inputs=["second"],
        max_turns=10,
        scorer=scorer,
        accumulate=True,
    )
    adapter = MockAdapter(response_fn=lambda messages: "ok")
    runner = ConversationRunner(adapter=adapter)

    result = await runner.run("accumulate-set", [case])

    # 2 per-turn rows (iteration 0, 1) + 1 summary row (iteration -1).
    assert len(result.case_results) == 3
    summary_rows = [cr for cr in result.case_results if cr.iteration == -1]
    assert len(summary_rows) == 1

    summary = summary_rows[0]
    manual_average = (1.0 + 0.5) / 2
    assert summary.score.value == pytest.approx(manual_average)
    assert summary.passed == (manual_average >= 1.0)


@pytest.mark.asyncio
async def test_accumulate_true_with_max_turns_exhaustion_uses_executed_turn_count():
    # Regression test: the loop here exits because `turn < case.max_turns`
    # goes false (max_turns exhaustion), not via an explicit `break` (driver
    # stop or turn_inputs exhaustion). This exit path previously miscounted
    # `total_turns` as `case.max_turns + 1` instead of the actual number of
    # turns executed (`case.max_turns`), silently corrupting the averaged
    # accumulator score.
    driver = AlwaysContinueDriver()
    scorer = SequenceScorer(values=[1.0, 1.0, 1.0])
    case = _make_case(driver=driver, max_turns=3, scorer=scorer, accumulate=True)
    adapter = MockAdapter(response_fn=lambda messages: "ok")
    runner = ConversationRunner(adapter=adapter)

    result = await runner.run("max-turns-accumulate-set", [case])

    # 3 per-turn rows (iteration 0, 1, 2) + 1 summary row (iteration -1).
    assert len(result.case_results) == 4
    turn_rows = [cr for cr in result.case_results if cr.iteration != -1]
    assert len(turn_rows) == 3

    summary_rows = [cr for cr in result.case_results if cr.iteration == -1]
    assert len(summary_rows) == 1
    summary = summary_rows[0]

    assert summary.actual == "Final accumulated score across 3 turns."
    assert summary.score.value == pytest.approx(1.0)
    assert summary.passed is True


@pytest.mark.asyncio
async def test_no_accumulate_no_accumulator_no_summary_row():
    case = _make_case(turn_inputs=["second"], max_turns=10, scorer=MockScorer())
    adapter = MockAdapter(response_fn=lambda messages: "match")
    runner = ConversationRunner(adapter=adapter)

    result = await runner.run("no-accumulate-set", [case])

    assert all(cr.iteration != -1 for cr in result.case_results)


@pytest.mark.asyncio
async def test_default_scorer_used_when_case_scorer_is_none():
    passing_case = _make_case(
        id="pass-case", expected_outcomes=["hello"], scorer=None
    )
    failing_case = _make_case(
        id="fail-case", expected_outcomes=["goodbye"], scorer=None
    )
    adapter = MockAdapter(response_fn=lambda messages: "hello world")
    runner = ConversationRunner(adapter=adapter)

    result = await runner.run("default-scorer-set", [passing_case, failing_case])

    by_case = {cr.case_id: cr for cr in result.case_results}
    assert by_case["pass-case"].passed is True
    assert by_case["fail-case"].passed is False


@pytest.mark.asyncio
async def test_iterations_encode_conversation_repetition_into_case_id():
    case = _make_case(iterations=2, scorer=MockScorer())
    adapter = MockAdapter(response_fn=lambda messages: "match")
    runner = ConversationRunner(adapter=adapter)

    result = await runner.run("iterations-set", [case])

    case_ids = sorted(cr.case_id for cr in result.case_results)
    assert case_ids == ["case-1[iter=0]", "case-1[iter=1]"]


@pytest.mark.asyncio
async def test_concurrency_bounded_at_conversation_level():
    num_conversations = 5
    cases = [
        _make_case(
            id=f"case-{i}",
            turn_inputs=["ok", "thanks"],
            max_turns=10,
            scorer=MockScorer(),
        )
        for i in range(num_conversations)
    ]
    adapter = ConcurrencyTrackingAdapter()
    max_workers = 2
    runner = ConversationRunner(adapter=adapter, max_workers=max_workers)

    result = await runner.run("concurrency-set", cases)

    # 5 conversations x 3 turns each = 15 CaseResults.
    assert len(result.case_results) == 15
    assert adapter.max_seen <= max_workers
    # Sanity check that concurrency was actually exercised (not fully sequential).
    assert adapter.max_seen > 1


@pytest.mark.asyncio
async def test_timeout_per_turn_propagates_uncaught():
    case = _make_case(timeout_per_turn=0.01, scorer=MockScorer())
    adapter = SlowAdapter()
    runner = ConversationRunner(adapter=adapter)

    with pytest.raises(asyncio.TimeoutError):
        await runner.run("timeout-set", [case])


def test_adapter_validation_raises_at_init_time():
    class BadAdapter:
        """Does not implement async send — should fail isinstance check."""

        def not_send(self):
            pass

    with pytest.raises(ValueError, match="adapter must implement AgentAdapter Protocol"):
        ConversationRunner(adapter=BadAdapter())


@pytest.mark.asyncio
async def test_progress_callback_receives_event_per_turn_and_summary_row():
    scorer = SequenceScorer(values=[1.0, 0.5])
    case = _make_case(
        turn_inputs=["second"], max_turns=10, scorer=scorer, accumulate=True
    )
    adapter = MockAdapter(response_fn=lambda messages: "ok")
    events: list[dict] = []

    async def progress_callback(event: dict) -> None:
        events.append(event)

    runner = ConversationRunner(adapter=adapter, progress_callback=progress_callback)
    result = await runner.run("progress-set", [case])

    # 2 turn events + 1 summary event, matching the 3 CaseResults produced.
    assert len(events) == 3 == len(result.case_results)
    assert {e["event"] for e in events} == {"case_completed"}
    assert sorted(e["iteration"] for e in events) == [-1, 0, 1]
    for event, case_result in zip(
        sorted(events, key=lambda e: e["iteration"]),
        sorted(result.case_results, key=lambda cr: cr.iteration),
    ):
        assert event["passed"] == case_result.passed
        assert event["score"] == case_result.score.value


@pytest.mark.asyncio
async def test_no_progress_callback_by_default_does_not_raise():
    case = _make_case(scorer=MockScorer())
    adapter = MockAdapter(response_fn=lambda messages: "match")
    runner = ConversationRunner(adapter=adapter)  # no progress_callback

    result = await runner.run("no-callback-set", [case])

    assert len(result.case_results) == 1
