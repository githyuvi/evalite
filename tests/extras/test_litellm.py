"""Tests for LiteLLMProvider.

Note: `pytest.importorskip("litellm")` is called inside the test that
needs the real package (rather than at module level), so that the
`ImportError` test below (which specifically exercises the missing-package
path) still runs and passes even when litellm is not installed, instead of
being skipped along with everything else.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evalite.extras.litellm import LiteLLMProvider


def test_import_error_without_litellm(monkeypatch):
    """When litellm is not installed, ImportError is raised with a clear message."""
    monkeypatch.setitem(sys.modules, "litellm", None)

    with pytest.raises(ImportError, match=r"pip install evalite\[litellm\]"):
        LiteLLMProvider(model="gpt-4")


async def test_complete_returns_content():
    """complete() calls litellm.acompletion and returns the message content."""
    litellm = pytest.importorskip("litellm")

    fake_response = MagicMock()
    fake_response.choices[0].message.content = "test response"

    with patch.object(
        litellm, "acompletion", new=AsyncMock(return_value=fake_response)
    ) as mock_acompletion:
        provider = LiteLLMProvider(model="gpt-4")
        messages = [{"role": "user", "content": "hello"}]

        result = await provider.complete(messages)

        assert result == "test response"
        mock_acompletion.assert_awaited_once_with(
            model="gpt-4", messages=messages
        )
