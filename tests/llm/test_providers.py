"""Tests for the built-in LLMProvider adapters (ADR-006).

No real API calls are made — `httpx.AsyncClient` is mocked out via
`unittest.mock.patch` (no pytest-mock dependency needed; the `dev` extra
in pyproject.toml only has plain pytest/pytest-asyncio/pytest-cov).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evalite.llm.anthropic import AnthropicProvider
from evalite.llm.azure import AzureOpenAIProvider
from evalite.llm.ollama import OllamaProvider
from evalite.llm.openai import OpenAIProvider


def _mock_client(json_body: dict, status_code: int = 200) -> MagicMock:
    """Builds a MagicMock standing in for an `httpx.AsyncClient` instance,
    usable as `async with httpx.AsyncClient(...) as client: await client.post(...)`.
    """
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.text = json.dumps(json_body)
    mock_response.json.return_value = json_body

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_complete_returns_string():
    body = {"choices": [{"message": {"content": "hello from openai"}}]}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client(body)
        provider = OpenAIProvider(model="gpt-4o", api_key="fake-key")
        result = await provider.complete([{"role": "user", "content": "hi"}])

    assert isinstance(result, str)
    assert result == "hello from openai"


def test_openai_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider(model="gpt-4o")


@pytest.mark.asyncio
async def test_openai_proxy_and_cert_passed_to_client():
    body = {"choices": [{"message": {"content": "ok"}}]}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client(body)
        provider = OpenAIProvider(
            model="gpt-4o",
            api_key="fake-key",
            http_proxy="http://proxy.corp.com:8080",
            ssl_ca_bundle="/etc/ssl/corp-ca.pem",
            ssl_client_cert="/etc/ssl/client.pem",
        )
        await provider.complete([{"role": "user", "content": "hi"}])

    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["proxy"] == "http://proxy.corp.com:8080"
    assert call_kwargs["verify"] == "/etc/ssl/corp-ca.pem"
    assert call_kwargs["cert"] == "/etc/ssl/client.pem"


@pytest.mark.asyncio
async def test_openai_non_2xx_raises_descriptive_error():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client({"error": "bad request"}, status_code=400)
        provider = OpenAIProvider(model="gpt-4o", api_key="fake-key")
        with pytest.raises(RuntimeError, match="400"):
            await provider.complete([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_complete_returns_string():
    body = {"content": [{"type": "text", "text": "hello from anthropic"}]}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client(body)
        provider = AnthropicProvider(model="claude-opus-4-7", api_key="fake-key")
        result = await provider.complete([{"role": "user", "content": "hi"}])

    assert isinstance(result, str)
    assert result == "hello from anthropic"


def test_anthropic_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider(model="claude-opus-4-7")


@pytest.mark.asyncio
async def test_anthropic_proxy_and_cert_passed_to_client():
    body = {"content": [{"type": "text", "text": "ok"}]}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client(body)
        provider = AnthropicProvider(
            model="claude-opus-4-7",
            api_key="fake-key",
            http_proxy="http://proxy.corp.com:8080",
            ssl_ca_bundle="/etc/ssl/corp-ca.pem",
            ssl_client_cert="/etc/ssl/client.pem",
        )
        await provider.complete([{"role": "user", "content": "hi"}])

    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["proxy"] == "http://proxy.corp.com:8080"
    assert call_kwargs["verify"] == "/etc/ssl/corp-ca.pem"
    assert call_kwargs["cert"] == "/etc/ssl/client.pem"


@pytest.mark.asyncio
async def test_anthropic_extracts_system_message():
    body = {"content": [{"type": "text", "text": "ok"}]}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = _mock_client(body)
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(model="claude-opus-4-7", api_key="fake-key")
        await provider.complete(
            [
                {"role": "system", "content": "You are a judge."},
                {"role": "user", "content": "hi"},
            ]
        )

    _, post_call_kwargs = mock_client.post.call_args
    payload = post_call_kwargs["json"]
    assert payload["system"] == "You are a judge."
    assert payload["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_anthropic_non_2xx_raises_descriptive_error():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client({"error": "unauthorized"}, status_code=401)
        provider = AnthropicProvider(model="claude-opus-4-7", api_key="fake-key")
        with pytest.raises(RuntimeError, match="401"):
            await provider.complete([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# Azure OpenAI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_azure_complete_returns_string():
    body = {"choices": [{"message": {"content": "hello from azure"}}]}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client(body)
        provider = AzureOpenAIProvider(
            model="gpt-4o",
            api_key="fake-key",
            azure_endpoint="https://my-resource.openai.azure.com",
        )
        result = await provider.complete([{"role": "user", "content": "hi"}])

    assert isinstance(result, str)
    assert result == "hello from azure"


def test_azure_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AZURE_OPENAI_API_KEY"):
        AzureOpenAIProvider(
            model="gpt-4o", azure_endpoint="https://my-resource.openai.azure.com"
        )


def test_azure_missing_endpoint_raises(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    with pytest.raises(ValueError, match="azure_endpoint"):
        AzureOpenAIProvider(model="gpt-4o", api_key="fake-key")


@pytest.mark.asyncio
async def test_azure_proxy_and_cert_passed_to_client():
    body = {"choices": [{"message": {"content": "ok"}}]}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client(body)
        provider = AzureOpenAIProvider(
            model="gpt-4o",
            api_key="fake-key",
            azure_endpoint="https://my-resource.openai.azure.com",
            http_proxy="http://proxy.corp.com:8080",
            ssl_ca_bundle="/etc/ssl/corp-ca.pem",
            ssl_client_cert="/etc/ssl/client.pem",
        )
        await provider.complete([{"role": "user", "content": "hi"}])

    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["proxy"] == "http://proxy.corp.com:8080"
    assert call_kwargs["verify"] == "/etc/ssl/corp-ca.pem"
    assert call_kwargs["cert"] == "/etc/ssl/client.pem"


@pytest.mark.asyncio
async def test_azure_non_2xx_raises_descriptive_error():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client({"error": "server error"}, status_code=500)
        provider = AzureOpenAIProvider(
            model="gpt-4o",
            api_key="fake-key",
            azure_endpoint="https://my-resource.openai.azure.com",
        )
        with pytest.raises(RuntimeError, match="500"):
            await provider.complete([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ollama_complete_returns_string():
    body = {"message": {"role": "assistant", "content": "hello from ollama"}}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client(body)
        provider = OllamaProvider(model="llama3.1")
        result = await provider.complete([{"role": "user", "content": "hi"}])

    assert isinstance(result, str)
    assert result == "hello from ollama"


def test_ollama_requires_no_api_key():
    # Should not raise even with no key-related env vars set at all.
    provider = OllamaProvider(model="llama3.1")
    assert provider.base_url == "http://localhost:11434"


def test_ollama_custom_base_url():
    provider = OllamaProvider(model="llama3.1", base_url="http://ollama.internal:11434/")
    assert provider.base_url == "http://ollama.internal:11434"


@pytest.mark.asyncio
async def test_ollama_proxy_and_cert_passed_to_client():
    body = {"message": {"role": "assistant", "content": "ok"}}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client(body)
        provider = OllamaProvider(
            model="llama3.1",
            http_proxy="http://proxy.corp.com:8080",
            ssl_ca_bundle="/etc/ssl/corp-ca.pem",
            ssl_client_cert="/etc/ssl/client.pem",
        )
        await provider.complete([{"role": "user", "content": "hi"}])

    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["proxy"] == "http://proxy.corp.com:8080"
    assert call_kwargs["verify"] == "/etc/ssl/corp-ca.pem"
    assert call_kwargs["cert"] == "/etc/ssl/client.pem"


@pytest.mark.asyncio
async def test_ollama_non_2xx_raises_descriptive_error():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client({"error": "model not found"}, status_code=404)
        provider = OllamaProvider(model="nonexistent-model")
        with pytest.raises(RuntimeError, match="404"):
            await provider.complete([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# Protocol satisfaction
# ---------------------------------------------------------------------------


def test_all_providers_satisfy_llmprovider_protocol():
    """All four adapters must structurally satisfy LLMProvider (an async
    `complete(self, messages, **kwargs) -> str` method) without inheriting
    from it — Protocol conformance is structural, not nominal.
    """
    for cls in (OpenAIProvider, AnthropicProvider, AzureOpenAIProvider, OllamaProvider):
        assert hasattr(cls, "complete")
        assert callable(cls.complete)
