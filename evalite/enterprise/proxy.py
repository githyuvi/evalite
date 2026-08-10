"""Builds a proxy/TLS-aware `httpx.AsyncClient` from an `EnterpriseConfig`.

This mirrors the `_client_kwargs()` pattern already used by the built-in
LLM provider adapters (see `evalite/llm/openai.py`), so users have a
single well-tested place to build proxy/TLS-aware `httpx` clients from
instead of hand-rolling the kwargs mapping themselves. It is standalone
and decoupled — it does not know about `OpenAIProvider` or any other
adapter.
"""

import httpx

from evalite.enterprise.config import EnterpriseConfig


def build_httpx_client(config: EnterpriseConfig) -> httpx.AsyncClient:
    """Returns an `httpx.AsyncClient` configured from `config`.

    - Proxy: `config.https_proxy` is used if set, otherwise
      `config.http_proxy`, otherwise no `proxy=` kwarg is passed at all.
      `httpx.AsyncClient`'s `proxy=` kwarg accepts a single proxy URL (not
      separate http/https ones), so a choice has to be made between the
      two; `https_proxy` is preferred as the more specific/relevant one
      for a client that is mostly making HTTPS calls.
    - CA bundle: `config.ssl_ca_bundle`, forwarded to `verify=`. If unset,
      `verify=` is omitted entirely and httpx falls back to its own
      default (bundled certifi) automatically.
    - mTLS client cert: `config.ssl_client_cert` +
      `config.ssl_client_key`, forwarded to `cert=`. If both are set,
      `cert=` is the tuple `(ssl_client_cert, ssl_client_key)`. If only
      `ssl_client_cert` is set (a single combined PEM with no separate key
      file), `cert=` is that path alone. If neither is set, `cert=` is
      omitted.
    """
    client_kwargs: dict = {}

    proxy = config.https_proxy or config.http_proxy
    if proxy:
        client_kwargs["proxy"] = proxy

    if config.ssl_ca_bundle:
        client_kwargs["verify"] = config.ssl_ca_bundle

    if config.ssl_client_cert and config.ssl_client_key:
        client_kwargs["cert"] = (config.ssl_client_cert, config.ssl_client_key)
    elif config.ssl_client_cert:
        client_kwargs["cert"] = config.ssl_client_cert

    return httpx.AsyncClient(**client_kwargs)
