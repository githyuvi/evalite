"""Tests for LLMExtractor and PatternExtractor (ADR-007 Decision 3, ADR-008)."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from evalite.scorer.pipeline.extractor import LLMExtractor, PatternExtractor


def _mock_provider(completion: str) -> MagicMock:
    """A minimal stand-in for LLMProvider: an object with an async `complete`."""
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=completion)
    return provider


# ---------------------------------------------------------------------------
# LLMExtractor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_extractor_parses_json_array():
    provider = _mock_provider(json.dumps(["claim one", "claim two"]))
    extractor = LLMExtractor(provider)

    result = await extractor.extract("some response text", {"outcome": "x"})

    assert result == ["claim one", "claim two"]
    provider.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_extractor_sends_response_and_expected_in_prompt():
    provider = _mock_provider(json.dumps(["claim one"]))
    extractor = LLMExtractor(provider)

    await extractor.extract("the room was booked", {"outcome": "room booked"})

    messages = provider.complete.call_args[0][0]
    joined = " ".join(m["content"] for m in messages)
    assert "the room was booked" in joined
    assert "room booked" in joined


@pytest.mark.asyncio
async def test_llm_extractor_malformed_json_falls_back_to_single_item_list():
    provider = _mock_provider("this is not json at all")
    extractor = LLMExtractor(provider)

    result = await extractor.extract("some response", {})

    assert result == ["this is not json at all"]


@pytest.mark.asyncio
async def test_llm_extractor_non_string_array_elements_falls_back_to_single_item():
    provider = _mock_provider(json.dumps(["ok", 5, "also ok"]))
    extractor = LLMExtractor(provider)

    result = await extractor.extract("some response", {})

    assert result == [json.dumps(["ok", 5, "also ok"])]


@pytest.mark.asyncio
async def test_llm_extractor_empty_response_short_circuits():
    provider = _mock_provider(json.dumps(["should not be reached"]))
    extractor = LLMExtractor(provider)

    result = await extractor.extract("   ", {})

    assert result == []
    provider.complete.assert_not_awaited()


# ---------------------------------------------------------------------------
# PatternExtractor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pattern_extractor_patterns_only_no_groups():
    extractor = PatternExtractor(patterns=[r"room \d+"])
    result = await extractor.extract("booked room 12 and room 34", {})
    assert result == ["room 12", "room 34"]


@pytest.mark.asyncio
async def test_pattern_extractor_patterns_only_with_groups():
    extractor = PatternExtractor(patterns=[r"name: (\w+)"])
    result = await extractor.extract("name: Alice, name: Bob", {})
    assert result == ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_pattern_extractor_json_path_only():
    extractor = PatternExtractor(json_path="$.result.items")
    response = json.dumps({"result": {"items": ["a", "b", "c"]}})
    result = await extractor.extract(response, {})
    assert result == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_pattern_extractor_json_path_scalar_value():
    extractor = PatternExtractor(json_path="$.result.status")
    response = json.dumps({"result": {"status": "booked"}})
    result = await extractor.extract(response, {})
    assert result == ["booked"]


@pytest.mark.asyncio
async def test_pattern_extractor_json_path_invalid_json_degrades_to_empty():
    extractor = PatternExtractor(json_path="$.result")
    result = await extractor.extract("not json", {})
    assert result == []


@pytest.mark.asyncio
async def test_pattern_extractor_json_path_unresolvable_path_degrades_to_empty():
    extractor = PatternExtractor(json_path="$.missing.path")
    response = json.dumps({"result": {"status": "booked"}})
    result = await extractor.extract(response, {})
    assert result == []


@pytest.mark.asyncio
async def test_pattern_extractor_both_patterns_and_json_path_concatenate():
    extractor = PatternExtractor(patterns=[r"room \d+"], json_path="$.result.items")
    response_text = "booked room 12"

    # patterns applied to raw response text; json_path needs JSON, so use a
    # response that is itself valid JSON and also contains a pattern match
    # in one of its string values.
    response = json.dumps({"note": "booked room 12", "result": {"items": ["a", "b"]}})

    result = await extractor.extract(response, {})

    assert result == ["room 12", "a", "b"]


@pytest.mark.asyncio
async def test_pattern_extractor_no_patterns_or_json_path_returns_empty():
    extractor = PatternExtractor()
    result = await extractor.extract("anything", {})
    assert result == []
