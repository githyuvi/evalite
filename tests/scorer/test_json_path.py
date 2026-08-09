"""Tests for JsonPathScorer."""

from evalite.agent.protocol import AgentResponse
from evalite.scorer.json_path import JsonPathScorer


async def test_path_resolves_and_matches():
    """When the path resolves to expected_value, passed is True."""
    scorer = JsonPathScorer(path="$.result.status", expected_value="ok")
    actual = AgentResponse(content='{"result": {"status": "ok"}}')

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is True
    assert score.value == 1.0


async def test_path_resolves_but_value_mismatches():
    """When the path resolves but to a different value, passed is False."""
    scorer = JsonPathScorer(path="$.items[0].name", expected_value="widget")
    actual = AgentResponse(content='{"items": [{"name": "gadget"}]}')

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is False
    assert score.value == 0.0


async def test_invalid_json_is_not_an_error():
    """Malformed JSON in actual.content produces passed=False, not a raise."""
    scorer = JsonPathScorer(path="$.result.status", expected_value="ok")
    actual = AgentResponse(content="not valid json")

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is False
    assert score.value == 0.0


async def test_unresolvable_path_is_not_an_error():
    """A path that doesn't resolve (missing key) produces passed=False, not a raise."""
    scorer = JsonPathScorer(path="$.result.missing", expected_value="ok")
    actual = AgentResponse(content='{"result": {"status": "ok"}}')

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is False
    assert score.value == 0.0


async def test_index_out_of_range_is_not_an_error():
    """An out-of-range list index produces passed=False, not a raise."""
    scorer = JsonPathScorer(path="$.items[5].name", expected_value="widget")
    actual = AgentResponse(content='{"items": [{"name": "widget"}]}')

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is False
    assert score.value == 0.0
