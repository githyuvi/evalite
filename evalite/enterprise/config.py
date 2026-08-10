"""`EnterpriseConfig` — a single, centralised object for proxy/TLS settings.

Per Phase 6's non-negotiable rule 22, all proxy/TLS settings live in one
dataclass instead of being scattered as individual kwargs across the
codebase. This module is standalone and opt-in: nothing else in the
codebase is required to consume it. See `evalite/enterprise/proxy.py` for
the function that turns this config into a configured `httpx.AsyncClient`.
"""

import os
from dataclasses import dataclass, field


@dataclass
class EnterpriseConfig:
    """Proxy and TLS settings for outbound HTTP calls.

    All fields default to `None`/empty — nothing is ever required, matching
    every other optional-config pattern in this codebase.
    """

    http_proxy: str | None = None
    https_proxy: str | None = None
    no_proxy: list[str] = field(default_factory=list)
    ssl_ca_bundle: str | None = None
    ssl_client_cert: str | None = None
    ssl_client_key: str | None = None
    secret_patterns: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "EnterpriseConfig":
        """Builds an `EnterpriseConfig` from the standard proxy/TLS env vars.

        Reads `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, `SSL_CA_BUNDLE`,
        `SSL_CLIENT_CERT`, and `SSL_CLIENT_KEY`. `NO_PROXY` is comma-split
        into a list per standard convention (e.g.
        `NO_PROXY=localhost,127.0.0.1,.internal.corp.com` becomes
        `["localhost", "127.0.0.1", ".internal.corp.com"]`); empty/unset
        becomes `[]`.

        `secret_patterns` has no established environment variable
        convention, so it is left `[]` here — it is meant to be set by the
        caller in code.
        """
        no_proxy_raw = os.environ.get("NO_PROXY", "")
        no_proxy = [host.strip() for host in no_proxy_raw.split(",") if host.strip()]

        return cls(
            http_proxy=os.environ.get("HTTP_PROXY") or None,
            https_proxy=os.environ.get("HTTPS_PROXY") or None,
            no_proxy=no_proxy,
            ssl_ca_bundle=os.environ.get("SSL_CA_BUNDLE") or None,
            ssl_client_cert=os.environ.get("SSL_CLIENT_CERT") or None,
            ssl_client_key=os.environ.get("SSL_CLIENT_KEY") or None,
        )
