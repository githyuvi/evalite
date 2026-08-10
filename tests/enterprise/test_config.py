"""Tests for `EnterpriseConfig` (evalite/enterprise/config.py)."""

from evalite.enterprise.config import EnterpriseConfig

ENV_VARS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "SSL_CA_BUNDLE",
    "SSL_CLIENT_CERT",
    "SSL_CLIENT_KEY",
]


def _clear_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_all_none_or_empty():
    config = EnterpriseConfig()
    assert config.http_proxy is None
    assert config.https_proxy is None
    assert config.no_proxy == []
    assert config.ssl_ca_bundle is None
    assert config.ssl_client_cert is None
    assert config.ssl_client_key is None
    assert config.secret_patterns == []


def test_from_env_reads_all_standard_env_vars(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.corp.com:8080")
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy.corp.com:8443")
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,.internal.corp.com")
    monkeypatch.setenv("SSL_CA_BUNDLE", "/etc/ssl/corp-ca.pem")
    monkeypatch.setenv("SSL_CLIENT_CERT", "/etc/ssl/client.pem")
    monkeypatch.setenv("SSL_CLIENT_KEY", "/etc/ssl/client.key")

    config = EnterpriseConfig.from_env()

    assert config.http_proxy == "http://proxy.corp.com:8080"
    assert config.https_proxy == "https://proxy.corp.com:8443"
    assert config.no_proxy == ["localhost", "127.0.0.1", ".internal.corp.com"]
    assert config.ssl_ca_bundle == "/etc/ssl/corp-ca.pem"
    assert config.ssl_client_cert == "/etc/ssl/client.pem"
    assert config.ssl_client_key == "/etc/ssl/client.key"
    # secret_patterns has no env var convention, always empty from from_env().
    assert config.secret_patterns == []


def test_from_env_with_no_env_vars_set_gives_defaults(monkeypatch):
    _clear_env(monkeypatch)

    config = EnterpriseConfig.from_env()

    assert config.http_proxy is None
    assert config.https_proxy is None
    assert config.no_proxy == []
    assert config.ssl_ca_bundle is None
    assert config.ssl_client_cert is None
    assert config.ssl_client_key is None
    assert config.secret_patterns == []


def test_from_env_no_proxy_empty_string_gives_empty_list(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("NO_PROXY", "")

    config = EnterpriseConfig.from_env()

    assert config.no_proxy == []
