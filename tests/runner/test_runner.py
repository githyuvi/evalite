import asyncio

import pytest

from evalite.agent.protocol import AgentResponse
from evalite.runner.result import Score
from evalite.runner.runner import Runner
from evalite.testcase.models import ExpectedOutput, TestCase, TestSet


class MockAdapter:
    """Fake AgentAdapter: echoes back a canned response per call."""

    def __init__(self, response_fn=None) -> None:
        # response_fn(messages) -> str content. Defaults to echoing the input.
        self._response_fn = response_fn or (lambda messages: messages[0]["content"])

    async def send(self, messages: list[dict]) -> AgentResponse:
        content = self._response_fn(messages)
        return AgentResponse(content=content)


class MockScorer:
    """Fake Scorer: passes if the (stringified) expected 'value' is a substring of actual.content."""

    async def score(self, input: str, expected: dict, actual: AgentResponse) -> Score:
        expected_value = str(expected.get("value", ""))
        found = expected_value in actual.content
        return Score(passed=found, value=1.0 if found else 0.0, reasoning="mock scorer")


class ConcurrencyTrackingAdapter:
    """Fake AgentAdapter that tracks the max number of concurrent in-flight sends."""

    def __init__(self) -> None:
        self.current = 0
        self.max_seen = 0

    async def send(self, messages: list[dict]) -> AgentResponse:
        self.current += 1
        self.max_seen = max(self.max_seen, self.current)
        await asyncio.sleep(0.01)
        self.current -= 1
        return AgentResponse(content="ok")


class FastAdapter:
    """Fake AgentAdapter that returns immediately (no sleep) — isolates the
    concurrency bound to the scorer for the scorer-concurrency test below."""

    async def send(self, messages: list[dict]) -> AgentResponse:
        return AgentResponse(content="ok")


class ConcurrencyTrackingScorer:
    """Fake Scorer that tracks the max number of concurrent in-flight score() calls."""

    def __init__(self) -> None:
        self.current = 0
        self.max_seen = 0

    async def score(self, input: str, expected: dict, actual: AgentResponse) -> Score:
        self.current += 1
        self.max_seen = max(self.max_seen, self.current)
        await asyncio.sleep(0.02)
        self.current -= 1
        return Score(passed=True, value=1.0, reasoning="mock scorer")


def _make_case(case_id: str, expected_value: str, iterations: int = 1) -> TestCase:
    return TestCase(
        id=case_id,
        input=f"input for {case_id}",
        expected=ExpectedOutput(value=expected_value),
        iterations=iterations,
    )


@pytest.mark.asyncio
async def test_happy_path_all_pass():
    cases = [
        _make_case("case-1", "foo"),
        _make_case("case-2", "bar"),
        _make_case("case-3", "baz"),
    ]

    def response_fn(messages):
        # Return content that contains whatever "expected value" the input implies.
        return messages[0]["content"] + " foo bar baz"

    adapter = MockAdapter(response_fn=response_fn)
    scorer = MockScorer()
    runner = Runner(adapter=adapter, scorer=scorer, max_workers=10)

    test_set = TestSet(name="happy-path", cases=cases)
    result = await runner.run(test_set)

    assert result.total == 3
    assert result.passed == 3
    assert result.failed == 0
    assert result.pass_rate == 1.0
    assert all(cr.passed for cr in result.case_results)
    assert result.test_set_name == "happy-path"


@pytest.mark.asyncio
async def test_concurrency_bounded_by_max_workers():
    num_cases = 20
    cases = [_make_case(f"case-{i}", "irrelevant") for i in range(num_cases)]
    adapter = ConcurrencyTrackingAdapter()
    scorer = MockScorer()
    max_workers = 5
    runner = Runner(adapter=adapter, scorer=scorer, max_workers=max_workers)

    test_set = TestSet(name="concurrency-test", cases=cases)
    result = await runner.run(test_set)

    assert result.total == num_cases
    assert adapter.max_seen <= max_workers
    # Sanity check that concurrency was actually exercised (not fully sequential).
    assert adapter.max_seen > 1


@pytest.mark.asyncio
async def test_concurrency_bounded_by_max_workers_for_scorer_too():
    # Proves the semaphore bounds scorer.score() calls too, not just
    # adapter.send() — e.g. a future LLM-judge scorer that does I/O.
    # Adapter is fast (no sleep) so any concurrency observed is coming
    # from the scorer being held inside the semaphore block.
    num_cases = 20
    cases = [_make_case(f"case-{i}", "irrelevant") for i in range(num_cases)]
    adapter = FastAdapter()
    scorer = ConcurrencyTrackingScorer()
    max_workers = 5
    runner = Runner(adapter=adapter, scorer=scorer, max_workers=max_workers)

    test_set = TestSet(name="scorer-concurrency-test", cases=cases)
    result = await runner.run(test_set)

    assert result.total == num_cases
    assert scorer.max_seen <= max_workers
    # Sanity check that concurrency was actually exercised (not fully sequential).
    assert scorer.max_seen > 1


def test_adapter_validation_raises_at_init_time():
    class BadAdapter:
        """Does not implement async send — should fail isinstance check."""

        def not_send(self):
            pass

    bad_adapter = BadAdapter()
    scorer = MockScorer()

    with pytest.raises(ValueError, match="adapter must implement AgentAdapter Protocol"):
        Runner(adapter=bad_adapter, scorer=scorer)


@pytest.mark.asyncio
async def test_failed_case_reports_not_passed():
    case = _make_case("case-fail", "unmatched-expected-value")
    adapter = MockAdapter(response_fn=lambda messages: "totally different content")
    scorer = MockScorer()
    runner = Runner(adapter=adapter, scorer=scorer)

    test_set = TestSet(name="failing-set", cases=[case])
    result = await runner.run(test_set)

    assert result.total == 1
    assert result.passed == 0
    assert result.failed == 1
    assert result.case_results[0].passed is False


@pytest.mark.asyncio
async def test_iterations_produce_multiple_case_results():
    case = _make_case("case-multi", "foo", iterations=3)
    adapter = MockAdapter(response_fn=lambda messages: "foo")
    scorer = MockScorer()
    runner = Runner(adapter=adapter, scorer=scorer)

    test_set = TestSet(name="iterations-set", cases=[case])
    result = await runner.run(test_set)

    matching = [cr for cr in result.case_results if cr.case_id == "case-multi"]
    assert len(matching) == 3
    assert sorted(cr.iteration for cr in matching) == [0, 1, 2]


@pytest.mark.asyncio
async def test_progress_callback_receives_one_case_completed_event_per_case():
    cases = [_make_case("case-1", "foo"), _make_case("case-2", "bar")]
    adapter = MockAdapter(response_fn=lambda messages: "foo bar")
    scorer = MockScorer()
    events: list[dict] = []

    async def progress_callback(event: dict) -> None:
        events.append(event)

    runner = Runner(adapter=adapter, scorer=scorer, progress_callback=progress_callback)
    test_set = TestSet(name="progress-set", cases=cases)
    result = await runner.run(test_set)

    completed_events = [e for e in events if e["event"] == "case_completed"]
    assert len(completed_events) == 2
    assert {e["event"] for e in events} == {"case_started", "case_completed"}
    assert {e["case_id"] for e in completed_events} == {"case-1", "case-2"}
    for event, case_result in zip(
        sorted(completed_events, key=lambda e: e["case_id"]),
        sorted(result.case_results, key=lambda cr: cr.case_id),
    ):
        assert event["iteration"] == case_result.iteration
        assert event["passed"] == case_result.passed
        assert event["score"] == case_result.score.value


@pytest.mark.asyncio
async def test_progress_callback_receives_case_started_before_case_completed():
    cases = [_make_case("case-1", "foo"), _make_case("case-2", "bar")]
    adapter = MockAdapter(response_fn=lambda messages: "foo bar")
    scorer = MockScorer()
    events: list[dict] = []

    async def progress_callback(event: dict) -> None:
        events.append(event)

    runner = Runner(adapter=adapter, scorer=scorer, progress_callback=progress_callback)
    test_set = TestSet(name="progress-order-set", cases=cases)
    await runner.run(test_set)

    # One case_started + one case_completed per case, in that relative order.
    started = [e for e in events if e["event"] == "case_started"]
    completed = [e for e in events if e["event"] == "case_completed"]
    assert {(e["case_id"], e["iteration"]) for e in started} == {
        (e["case_id"], e["iteration"]) for e in completed
    }

    for key in {(e["case_id"], e["iteration"]) for e in started}:
        started_index = next(
            i
            for i, e in enumerate(events)
            if e["event"] == "case_started" and (e["case_id"], e["iteration"]) == key
        )
        completed_index = next(
            i
            for i, e in enumerate(events)
            if e["event"] == "case_completed" and (e["case_id"], e["iteration"]) == key
        )
        assert started_index < completed_index


@pytest.mark.asyncio
async def test_no_progress_callback_by_default_does_not_raise():
    case = _make_case("case-1", "foo")
    adapter = MockAdapter(response_fn=lambda messages: "foo")
    scorer = MockScorer()
    runner = Runner(adapter=adapter, scorer=scorer)  # no progress_callback

    result = await runner.run(TestSet(name="no-callback-set", cases=[case]))

    assert result.total == 1


@pytest.mark.asyncio
async def test_empty_test_set_returns_zero_results_no_division_error():
    adapter = MockAdapter()
    scorer = MockScorer()
    runner = Runner(adapter=adapter, scorer=scorer)

    test_set = TestSet(name="empty-set", cases=[])
    result = await runner.run(test_set)

    assert result.total == 0
    assert result.passed == 0
    assert result.failed == 0
    assert result.pass_rate == 0.0
    assert result.case_results == []
