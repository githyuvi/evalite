"""Tests for RegexScorer."""

import re

import pytest

from evalite.agent.protocol import AgentResponse
from evalite.scorer.regex import RegexScorer


async def test_pattern_matches():
    """When the pattern matches anywhere in actual.content, passed is True."""
    scorer = RegexScorer(pattern=r"booking \w+ confirmed")
    actual = AgentResponse(content="The booking was confirmed today")

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is True
    assert score.value == 1.0


async def test_pattern_does_not_match():
    """When the pattern does not match, passed is False."""
    scorer = RegexScorer(pattern=r"booking \w+ cancelled")
    actual = AgentResponse(content="The booking was confirmed today")

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is False
    assert score.value == 0.0


async def test_pattern_with_flags():
    """Flags (e.g. re.IGNORECASE) are passed through to re.search."""
    scorer = RegexScorer(pattern=r"CONFIRMED", flags=re.IGNORECASE)
    actual = AgentResponse(content="the booking was confirmed")

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is True
    assert score.value == 1.0
