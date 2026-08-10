"""Tests for `build_httpx_client` (evalite/enterprise/proxy.py).

No real HTTP requests are made. For the all-defaults case we construct a
real `httpx.AsyncClient` (safe — no proxy/verify/cert kwargs are passed,
so nothing eagerly touches the filesystem) and inspect its public/
semi-public attributes. For the proxy/TLS cases we mock `httpx.AsyncClient`
and inspect the kwargs it was constructed with — the same pattern already
used in `tests/llm/test_providers.py` — since httpx eagerly loads
`verify=`/`cert=` files at construction time (raising `FileNotFoundError`
for fake paths), so real construction with those kwargs would require
real certificate files on disk.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from evalite.enterprise.config import EnterpriseConfig
from evalite.enterprise.proxy import build_httpx_client


@pytest.mark.asyncio
async def test_defaults_produce_plain_client_with_no_proxy_or_cert():
    client = build_httpx_client(EnterpriseConfig())
    try:
        assert isinstance(client, httpx.AsyncClient)
        # No proxy configured means no extra transport mounts.
        assert client._mounts == {}
    finally:
        await client.aclose()


def test_http_proxy_applied_when_https_proxy_unset():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        config = EnterpriseConfig(http_proxy="http://proxy.corp.com:8080")
        build_httpx_client(config)

    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["proxy"] == "http://proxy.corp.com:8080"


def test_https_proxy_wins_over_http_proxy():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        config = EnterpriseConfig(
            http_proxy="http://proxy.corp.com:8080",
            https_proxy="https://proxy.corp.com:8443",
        )
        build_httpx_client(config)

    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["proxy"] == "https://proxy.corp.com:8443"


def test_no_proxy_kwarg_when_neither_proxy_set():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        build_httpx_client(EnterpriseConfig())

    _, call_kwargs = mock_cls.call_args
    assert "proxy" not in call_kwargs


def test_ssl_ca_bundle_sets_verify():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        config = EnterpriseConfig(ssl_ca_bundle="/etc/ssl/corp-ca.pem")
        build_httpx_client(config)

    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["verify"] == "/etc/ssl/corp-ca.pem"


def test_no_verify_kwarg_when_ca_bundle_unset():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        build_httpx_client(EnterpriseConfig())

    _, call_kwargs = mock_cls.call_args
    assert "verify" not in call_kwargs


def test_cert_and_key_both_set_gives_tuple():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        config = EnterpriseConfig(
            ssl_client_cert="/etc/ssl/client.pem",
            ssl_client_key="/etc/ssl/client.key",
        )
        build_httpx_client(config)

    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["cert"] == ("/etc/ssl/client.pem", "/etc/ssl/client.key")


def test_cert_only_set_gives_bare_path():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        config = EnterpriseConfig(ssl_client_cert="/etc/ssl/combined.pem")
        build_httpx_client(config)

    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["cert"] == "/etc/ssl/combined.pem"


def test_no_cert_kwarg_when_neither_cert_nor_key_set():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        build_httpx_client(EnterpriseConfig())

    _, call_kwargs = mock_cls.call_args
    assert "cert" not in call_kwargs


def test_key_alone_without_cert_is_ignored():
    """A key with no cert is meaningless to httpx's `cert=`, so it should
    not be passed at all."""
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        config = EnterpriseConfig(ssl_client_key="/etc/ssl/client.key")
        build_httpx_client(config)

    _, call_kwargs = mock_cls.call_args
    assert "cert" not in call_kwargs
