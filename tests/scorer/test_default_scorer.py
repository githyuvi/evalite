"""Tests for DefaultScorer."""

import pytest

from evalite.agent.protocol import AgentResponse
from evalite.scorer.default import DefaultScorer


@pytest.fixture
def scorer():
    """Provide a DefaultScorer instance."""
    return DefaultScorer()


async def test_all_expected_values_found(scorer):
    """When all expected values are found, score is 1.0 and passed=True."""
    actual = AgentResponse(content="The booking was confirmed and paid")
    expected = {"result": "booking was confirmed"}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0
    assert "1/1 expected values found" in score.reasoning


async def test_no_expected_values_found(scorer):
    """When no expected values are found, score is 0.0 and passed=False."""
    actual = AgentResponse(content="The booking failed")
    expected = {"result": "confirmed"}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is False
    assert score.value == 0.0
    assert "0/1 expected values found" in score.reasoning


async def test_partial_match(scorer):
    """When some expected values are found, score is the fraction and passed=False."""
    actual = AgentResponse(content="The booking was confirmed. Payment pending.")
    expected = {"status": "confirmed", "payment": "completed"}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is False
    assert score.value == 0.5
    assert "1/2 expected values found" in score.reasoning


async def test_case_insensitive_match(scorer):
    """Case-insensitive substring matching works."""
    actual = AgentResponse(content="The booking was Booked successfully")
    expected = {"status": "booked"}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0


async def test_empty_expected_dict(scorer):
    """Empty expected dict is treated as vacuously true."""
    actual = AgentResponse(content="Any content")
    expected = {}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0
    assert "0/0 expected values found" in score.reasoning


async def test_nested_expected_dict(scorer):
    """Nested dicts are flattened to leaf values only."""
    actual = AgentResponse(content="The status is ok and user is john")
    expected = {"result": {"status": "ok", "user": {"name": "john"}}}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0
    assert "2/2 expected values found" in score.reasoning


async def test_nested_dict_partial_match(scorer):
    """Nested dicts with partial matches."""
    actual = AgentResponse(content="The status is ok but no user info")
    expected = {"result": {"status": "ok", "user": {"name": "john"}}}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is False
    assert score.value == 0.5
    assert "1/2 expected values found" in score.reasoning


async def test_substring_matching_not_exact(scorer):
    """Substring matching, not exact word matching."""
    actual = AgentResponse(content="The booking confirmation was sent")
    expected = {"message": "confirm"}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0


async def test_multiple_expected_values_all_present(scorer):
    """Multiple expected values all present."""
    actual = AgentResponse(
        content="Booking confirmed. Price: $100. Seats: 5. Status: active"
    )
    expected = {"info": {"booking": "confirmed", "price": "100", "seats": "5"}}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0
    assert "3/3 expected values found" in score.reasoning


async def test_deeply_nested_dict(scorer):
    """Very deeply nested dicts are properly flattened."""
    actual = AgentResponse(content="value1 and value2 and value3")
    expected = {
        "level1": {
            "level2": {
                "level3": {
                    "level4": "value1"
                }
            },
            "sibling": "value2"
        },
        "root": "value3"
    }

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0
    assert "3/3 expected values found" in score.reasoning


async def test_numeric_values_in_expected(scorer):
    """Numeric values in expected dict are converted to strings."""
    actual = AgentResponse(content="Count is 42 and price is 99.99")
    expected = {"data": {"count": 42, "price": 99.99}}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0
    assert "2/2 expected values found" in score.reasoning


async def test_empty_string_in_expected(scorer):
    """Empty strings in expected are handled (will always match)."""
    actual = AgentResponse(content="some content")
    expected = {"value": ""}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0


async def test_special_characters_in_expected(scorer):
    """Special characters in expected values are matched."""
    actual = AgentResponse(content="Email: test@example.com and phone: +1-555-1234")
    expected = {"email": "test@example.com", "phone": "+1-555-1234"}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0


async def test_list_values_in_expected(scorer):
    """List values in expected dict are flattened element-wise, not stringified as a whole."""
    actual = AgentResponse(content="Ticket marked urgent and flagged vip")
    expected = {"tags": ["urgent", "vip"]}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value == 1.0
    assert "2/2 expected values found" in score.reasoning


async def test_list_values_partial_match(scorer):
    """List-sourced values are counted correctly alongside other values on partial match."""
    actual = AgentResponse(content="Ticket marked urgent")
    expected = {"tags": ["urgent", "vip"], "status": "closed"}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is False
    assert score.value == pytest.approx(1 / 3)
    assert "1/3 expected values found" in score.reasoning


async def test_input_parameter_unused(scorer):
    """The input parameter is provided but not used by the scorer."""
    actual = AgentResponse(content="found it")
    expected = {"result": "found it"}

    score1 = await scorer.score(input="input1", expected=expected, actual=actual)
    score2 = await scorer.score(input="input2", expected=expected, actual=actual)

    assert score1.passed == score2.passed
    assert score1.value == score2.value
