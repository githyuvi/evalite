"""Tests for SemanticSimilarityScorer.

Note: `pytest.importorskip("sentence_transformers")` is called inside each
test that needs real embeddings (rather than at module level), so that the
`ImportError` test below (which specifically exercises the missing-package
path) still runs and passes even when sentence-transformers is not
installed, instead of being skipped along with everything else.
"""

import sys

import pytest

from evalite.agent.protocol import AgentResponse
from evalite.scorer.semantic import SemanticSimilarityScorer


async def test_high_similarity_passes():
    """When actual.content is semantically close to an expected value, passed=True."""
    pytest.importorskip("sentence_transformers")

    scorer = SemanticSimilarityScorer(threshold=0.6)
    actual = AgentResponse(content="The booking was confirmed successfully")
    expected = {"result": "The reservation has been confirmed"}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is True
    assert score.value >= 0.6


async def test_low_similarity_fails():
    """When actual.content is semantically unrelated to expected values, passed=False."""
    pytest.importorskip("sentence_transformers")

    scorer = SemanticSimilarityScorer(threshold=0.8)
    actual = AgentResponse(content="The weather today is sunny and warm")
    expected = {"result": "The booking was confirmed"}

    score = await scorer.score(input="test", expected=expected, actual=actual)

    assert score.passed is False
    assert score.value < 0.8


def test_import_error_without_sentence_transformers(monkeypatch):
    """When sentence-transformers is not installed, ImportError is raised with a clear message."""
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    with pytest.raises(ImportError, match=r"pip install evalite\[semantic\]"):
        SemanticSimilarityScorer()
