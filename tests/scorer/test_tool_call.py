"""Tests for ToolCallScorer."""

from evalite.agent.protocol import AgentResponse
from evalite.scorer.tool_call import ToolCallScorer


async def test_tool_called_without_expected_args():
    """When the expected tool was called, passed is True (args not checked)."""
    scorer = ToolCallScorer(expected_tool="search")
    actual = AgentResponse(
        content="done",
        metadata={"tool_calls": [{"name": "search", "args": {"query": "cats"}}]},
    )

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is True
    assert score.value == 1.0


async def test_tool_called_with_matching_args():
    """When expected_args is provided and matches exactly, passed is True."""
    scorer = ToolCallScorer(expected_tool="search", expected_args={"query": "cats"})
    actual = AgentResponse(
        content="done",
        metadata={"tool_calls": [{"name": "search", "args": {"query": "cats"}}]},
    )

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is True
    assert score.value == 1.0


async def test_tool_not_called():
    """When the expected tool was not called, passed is False."""
    scorer = ToolCallScorer(expected_tool="search")
    actual = AgentResponse(
        content="done",
        metadata={"tool_calls": [{"name": "book_flight", "args": {}}]},
    )

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is False
    assert score.value == 0.0


async def test_tool_called_with_mismatched_args():
    """When expected_args is provided but doesn't match, passed is False."""
    scorer = ToolCallScorer(expected_tool="search", expected_args={"query": "dogs"})
    actual = AgentResponse(
        content="done",
        metadata={"tool_calls": [{"name": "search", "args": {"query": "cats"}}]},
    )

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is False
    assert score.value == 0.0


async def test_missing_tool_calls_key_is_not_an_error():
    """A missing tool_calls key in metadata produces passed=False, not a raise."""
    scorer = ToolCallScorer(expected_tool="search")
    actual = AgentResponse(content="done", metadata={})

    score = await scorer.score(input="test", expected={}, actual=actual)

    assert score.passed is False
    assert score.value == 0.0
