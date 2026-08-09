import pytest

from evalite.agent.protocol import AgentResponse
from evalite.runner.result import RunResult, Score
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


class MockStorage:
    """Fake StorageBackend that records every `save_run` call."""

    def __init__(self) -> None:
        self.saved_runs: list[RunResult] = []

    async def save_run(self, run: RunResult) -> str:
        self.saved_runs.append(run)
        return "mock-run-id-123"

    async def get_run(self, run_id: str) -> RunResult | None:
        raise NotImplementedError

    async def list_runs(self, limit: int = 50) -> list[dict]:
        raise NotImplementedError


def _make_case(case_id: str, expected_value: str, iterations: int = 1) -> TestCase:
    return TestCase(
        id=case_id,
        input=f"input for {case_id}",
        expected=ExpectedOutput(value=expected_value),
        iterations=iterations,
    )


def _make_test_set() -> TestSet:
    cases = [
        _make_case("case-1", "foo"),
        _make_case("case-2", "bar"),
    ]
    return TestSet(name="storage-test", cases=cases)


@pytest.mark.asyncio
async def test_run_with_storage_calls_save_run_once_with_result():
    adapter = MockAdapter(response_fn=lambda messages: messages[0]["content"] + " foo bar")
    scorer = MockScorer()
    storage = MockStorage()
    runner = Runner(adapter=adapter, scorer=scorer, storage=storage)

    test_set = _make_test_set()
    result = await runner.run(test_set)

    assert len(storage.saved_runs) == 1
    saved = storage.saved_runs[0]
    assert saved.test_set_name == result.test_set_name
    assert saved.total == result.total
    assert saved.passed == result.passed
    assert saved.failed == result.failed
    assert saved.case_results == result.case_results


@pytest.mark.asyncio
async def test_run_without_storage_never_calls_save_run():
    adapter = MockAdapter(response_fn=lambda messages: messages[0]["content"] + " foo bar")
    scorer = MockScorer()
    storage = MockStorage()
    # storage is not passed to this runner at all — it must never be touched.
    runner = Runner(adapter=adapter, scorer=scorer)

    test_set = _make_test_set()
    await runner.run(test_set)

    assert storage.saved_runs == []


@pytest.mark.asyncio
async def test_run_id_populated_when_storage_configured():
    adapter = MockAdapter(response_fn=lambda messages: messages[0]["content"] + " foo bar")
    scorer = MockScorer()
    storage = MockStorage()
    runner = Runner(adapter=adapter, scorer=scorer, storage=storage)

    test_set = _make_test_set()
    result = await runner.run(test_set)

    assert result.run_id == "mock-run-id-123"


@pytest.mark.asyncio
async def test_run_id_none_when_storage_not_configured():
    adapter = MockAdapter(response_fn=lambda messages: messages[0]["content"] + " foo bar")
    scorer = MockScorer()
    runner = Runner(adapter=adapter, scorer=scorer, storage=None)

    test_set = _make_test_set()
    result = await runner.run(test_set)

    assert result.run_id is None
