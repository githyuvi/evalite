"""Tests for LLMJudge and RuleJudge (ADR-007 Decision 3, ADR-008)."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from evalite.scorer.pipeline.category import Category
from evalite.scorer.pipeline.judge import LLMJudge, RuleJudge

CATEGORIES = [
    Category(name="correct", description="Factually correct", weight=1.0),
    Category(name="wrong", description="Factually incorrect", weight=-1.0),
    Category(name="missing", description="Absent from response", weight=-0.5),
]


def _mock_provider(completion: str) -> MagicMock:
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=completion)
    return provider


# ---------------------------------------------------------------------------
# LLMJudge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_judge_parses_valid_classification_json():
    completion = json.dumps({"room booked": "correct", "wrong claim": "wrong"})
    provider = _mock_provider(completion)
    judge = LLMJudge(provider)

    result = await judge.classify(
        ["room booked", "wrong claim"], CATEGORIES, {"outcome": "room booked"}
    )

    assert result == {"room booked": "correct", "wrong claim": "wrong"}


@pytest.mark.asyncio
async def test_llm_judge_empty_items_short_circuits():
    provider = _mock_provider(json.dumps({}))
    judge = LLMJudge(provider)

    result = await judge.classify([], CATEGORIES, {})

    assert result == {}
    provider.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_judge_default_mode_lists_categories_in_system_prompt():
    provider = _mock_provider(json.dumps({"x": "correct"}))
    judge = LLMJudge(provider)

    await judge.classify(["x"], CATEGORIES, {})

    messages = provider.complete.call_args[0][0]
    system_message = next(m["content"] for m in messages if m["role"] == "system")
    for category in CATEGORIES:
        assert category.name in system_message
        assert category.description in system_message


@pytest.mark.asyncio
async def test_llm_judge_append_mode_adds_instructions_below_base():
    provider = _mock_provider(json.dumps({"x": "correct"}))
    judge = LLMJudge(provider, additional_instructions="Be extra strict.")

    await judge.classify(["x"], CATEGORIES, {})

    messages = provider.complete.call_args[0][0]
    system_message = next(m["content"] for m in messages if m["role"] == "system")
    assert "Be extra strict." in system_message
    # Base prompt content (category info) is still present
    assert "correct" in system_message
    assert "Factually correct" in system_message


@pytest.mark.asyncio
async def test_llm_judge_override_mode_replaces_base_entirely():
    provider = _mock_provider(json.dumps({"x": "correct"}))
    judge = LLMJudge(provider, system_prompt="Only this text, nothing else.")

    await judge.classify(["x"], CATEGORIES, {})

    messages = provider.complete.call_args[0][0]
    system_message = next(m["content"] for m in messages if m["role"] == "system")
    assert system_message == "Only this text, nothing else."


@pytest.mark.asyncio
async def test_llm_judge_three_modes_produce_different_system_prompts():
    default_provider = _mock_provider(json.dumps({"x": "correct"}))
    append_provider = _mock_provider(json.dumps({"x": "correct"}))
    override_provider = _mock_provider(json.dumps({"x": "correct"}))

    default_judge = LLMJudge(default_provider)
    append_judge = LLMJudge(append_provider, additional_instructions="Extra rule.")
    override_judge = LLMJudge(override_provider, system_prompt="Completely different.")

    await default_judge.classify(["x"], CATEGORIES, {})
    await append_judge.classify(["x"], CATEGORIES, {})
    await override_judge.classify(["x"], CATEGORIES, {})

    def _system_content(provider):
        messages = provider.complete.call_args[0][0]
        return next(m["content"] for m in messages if m["role"] == "system")

    default_prompt = _system_content(default_provider)
    append_prompt = _system_content(append_provider)
    override_prompt = _system_content(override_provider)

    assert default_prompt != append_prompt
    assert default_prompt != override_prompt
    assert append_prompt != override_prompt
    # append mode is a strict extension of the default base prompt
    assert default_prompt in append_prompt


@pytest.mark.asyncio
async def test_llm_judge_malformed_response_falls_back_to_first_category():
    provider = _mock_provider("not valid json")
    judge = LLMJudge(provider)

    result = await judge.classify(["a", "b"], CATEGORIES, {})

    assert result == {"a": "correct", "b": "correct"}


@pytest.mark.asyncio
async def test_llm_judge_partial_or_invalid_categories_fall_back_per_item():
    # "b" missing from response, "c" assigned an unknown category name
    completion = json.dumps({"a": "wrong", "c": "not_a_real_category"})
    provider = _mock_provider(completion)
    judge = LLMJudge(provider)

    result = await judge.classify(["a", "b", "c"], CATEGORIES, {})

    assert result == {"a": "wrong", "b": "correct", "c": "correct"}


# ---------------------------------------------------------------------------
# RuleJudge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rule_judge_matches_expected_value_as_correct():
    judge = RuleJudge()
    result = await judge.classify(
        ["the room was booked successfully"], CATEGORIES, {"outcome": "room booked"}
    )
    # substring match check: does item contain expected value verbatim?
    # "room booked" is not literally in "the room was booked successfully",
    # so this exercises the no-match (wrong) branch instead.
    assert result == {"the room was booked successfully": "wrong"}


@pytest.mark.asyncio
async def test_rule_judge_exact_substring_match_classifies_correct():
    judge = RuleJudge()
    result = await judge.classify(
        ["confirmation: room booked for tomorrow"],
        CATEGORIES,
        {"outcome": "room booked"},
    )
    assert result == {"confirmation: room booked for tomorrow": "correct"}


@pytest.mark.asyncio
async def test_rule_judge_no_match_classifies_wrong():
    judge = RuleJudge()
    result = await judge.classify(
        ["completely unrelated statement"], CATEGORIES, {"outcome": "room booked"}
    )
    assert result == {"completely unrelated statement": "wrong"}


@pytest.mark.asyncio
async def test_rule_judge_case_insensitive_matching():
    judge = RuleJudge()
    result = await judge.classify(
        ["ROOM BOOKED for tomorrow"], CATEGORIES, {"outcome": "room booked"}
    )
    assert result == {"ROOM BOOKED for tomorrow": "correct"}


@pytest.mark.asyncio
async def test_rule_judge_falls_back_to_first_category_when_wrong_missing():
    categories = [
        Category(name="correct", description="ok", weight=1.0),
        Category(name="other", description="n/a", weight=0.0),
    ]
    judge = RuleJudge()
    result = await judge.classify(
        ["unrelated"], categories, {"outcome": "room booked"}
    )
    # no category named "wrong" -> falls back to categories[0] ("correct")
    assert result == {"unrelated": "correct"}


@pytest.mark.asyncio
async def test_rule_judge_falls_back_to_first_category_when_correct_missing():
    categories = [
        Category(name="other", description="n/a", weight=0.0),
        Category(name="wrong", description="bad", weight=-1.0),
    ]
    judge = RuleJudge()
    result = await judge.classify(
        ["room booked for tomorrow"], categories, {"outcome": "room booked"}
    )
    # no category named "correct" -> falls back to categories[0] ("other")
    assert result == {"room booked for tomorrow": "other"}


@pytest.mark.asyncio
async def test_rule_judge_flattens_nested_expected_dict():
    judge = RuleJudge()
    expected = {"details": {"outcome": "room booked", "list": ["confirmation sent"]}}
    result = await judge.classify(
        ["confirmation sent to the user"], CATEGORIES, expected
    )
    assert result == {"confirmation sent to the user": "correct"}
