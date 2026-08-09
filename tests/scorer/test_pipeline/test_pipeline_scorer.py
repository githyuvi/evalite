"""Tests for PipelineScorer (ADR-007 Decision 3/4, ADR-008)."""

from unittest.mock import MagicMock

import pytest

from evalite.agent.protocol import AgentResponse
from evalite.scorer.pipeline.category import Category
from evalite.scorer.pipeline.extractor import LLMExtractor
from evalite.scorer.pipeline.judge import LLMJudge, RuleJudge
from evalite.scorer.pipeline.scorer import PipelineScorer

CATEGORIES = [
    Category(name="correct", description="Factually correct", weight=1.0),
    Category(name="wrong", description="Factually incorrect", weight=-1.0),
    Category(name="missing", description="Absent from response", weight=-0.5),
]


class FakeExtractor:
    """Fake Extractor satisfying the Extractor Protocol for tests."""

    def __init__(self, items: list[str]) -> None:
        self.items = items
        self.calls: list[tuple[str, dict]] = []

    async def extract(self, response: str, expected: dict) -> list[str]:
        self.calls.append((response, expected))
        return self.items


class FakeJudge:
    """Fake Judge satisfying the Judge Protocol for tests."""

    def __init__(self, classification: dict[str, str]) -> None:
        self.classification = classification
        self.calls: list[tuple[list[str], list[Category], dict]] = []

    async def classify(
        self, items: list[str], categories: list[Category], expected: dict
    ) -> dict[str, str]:
        self.calls.append((items, categories, expected))
        return self.classification


def _response(content: str = "some response") -> AgentResponse:
    return AgentResponse(content=content)


@pytest.mark.asyncio
async def test_full_match_scores_one_and_passes():
    extractor = FakeExtractor(["item1", "item2"])
    judge = FakeJudge({"item1": "correct", "item2": "correct"})
    scorer = PipelineScorer(
        provider=MagicMock(), categories=CATEGORIES, extractor=extractor, judge=judge
    )

    score = await scorer.score(
        input="do the thing", expected={"a": "x", "b": "y"}, actual=_response()
    )

    assert score.value == 1.0
    assert score.passed is True


@pytest.mark.asyncio
async def test_partial_match_computes_value_by_formula():
    extractor = FakeExtractor(["c1", "w1", "m1", "c2"])
    judge = FakeJudge(
        {"c1": "correct", "w1": "wrong", "m1": "missing", "c2": "correct"}
    )
    scorer = PipelineScorer(
        provider=MagicMock(), categories=CATEGORIES, extractor=extractor, judge=judge
    )

    expected = {"a": "1", "b": "2", "c": "3", "d": "4"}  # 4 flattened values
    score = await scorer.score(input="x", expected=expected, actual=_response())

    weights_by_name = {c.name: c.weight for c in CATEGORIES}
    weighted_sum = (
        weights_by_name["correct"]
        + weights_by_name["wrong"]
        + weights_by_name["missing"]
        + weights_by_name["correct"]
    )
    expected_value = max(0.0, min(1.0, weighted_sum / 4))

    assert score.value == pytest.approx(expected_value)
    # sanity: this partial mix should not be a perfect pass
    assert expected_value < 1.0
    assert score.passed is False


@pytest.mark.asyncio
async def test_empty_expected_dict_returns_zero_without_zero_division():
    extractor = FakeExtractor(["item1"])
    judge = FakeJudge({"item1": "correct"})
    scorer = PipelineScorer(
        provider=MagicMock(), categories=CATEGORIES, extractor=extractor, judge=judge
    )

    score = await scorer.score(input="x", expected={}, actual=_response())

    assert score.value == 0.0
    assert score.passed is False
    assert "no values to score against" in score.reasoning


@pytest.mark.asyncio
async def test_constructor_defaults_build_llm_extractor_and_judge():
    provider = MagicMock()
    scorer = PipelineScorer(provider=provider)

    assert isinstance(scorer._extractor, LLMExtractor)
    assert isinstance(scorer._judge, LLMJudge)


@pytest.mark.asyncio
async def test_custom_judge_does_not_receive_llm_judge_only_kwargs():
    provider = MagicMock()
    custom_judge = RuleJudge()

    # additional_instructions/system_prompt are LLMJudge-specific and must
    # have no effect when a custom (non-LLMJudge) judge is supplied.
    scorer = PipelineScorer(
        provider=provider,
        judge=custom_judge,
        additional_instructions="be strict",
        system_prompt="override prompt",
    )

    assert scorer._judge is custom_judge
    assert not isinstance(scorer._judge, LLMJudge)

    # Exercise scoring end-to-end with the custom judge to confirm no error.
    extractor = FakeExtractor(["room booked for tomorrow"])
    scorer._extractor = extractor
    score = await scorer.score(
        input="x", expected={"outcome": "room booked"}, actual=_response()
    )
    assert score.value == 1.0
    assert score.passed is True
