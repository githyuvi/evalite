"""Ollama adapter for the `LLMProvider` Protocol (ADR-006).

Talks to a local (or remote) Ollama server's `/api/chat` endpoint. Uses
`httpx.AsyncClient` for all I/O per ADR-002 (no blocking calls on the
event loop). Accepts the same enterprise proxy/cert config as agent
adapters, per ADR-006's Consequences.

Ollama deployments are typically local and unauthenticated (no API
key), so this adapter deviates from the shared `api_key`-based
constructor pattern used by the other three providers: it takes an
optional `base_url` (default `http://localhost:11434`) instead of
requiring credentials. This is the most conservative interpretation
that still works out of the box against a default local Ollama
install; callers proxying to an authenticated Ollama-compatible gateway
can still supply an `Authorization` header via `**kwargs` on
`complete()` if needed — the API surface does not currently have a
dedicated param for that since it is not the common case.
"""

import httpx

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider:
    """`LLMProvider` for a local (or remote) Ollama server.

    Satisfies the `LLMProvider` Protocol structurally — no inheritance
    required.
    """

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        http_proxy: str | None = None,
        ssl_ca_bundle: str | None = None,
        ssl_client_cert: str | None = None,
        **kwargs,
    ) -> None:
        """
        Args:
            model: Ollama model name/tag, e.g. "llama3.1".
            base_url: Ollama server base URL. Defaults to
                "http://localhost:11434" — Ollama is typically local and
                unauthenticated, so unlike the other three providers this
                adapter takes no `api_key` param.
            http_proxy: Optional proxy URL, forwarded to
                `httpx.AsyncClient(proxy=...)`.
            ssl_ca_bundle: Optional path to a custom CA bundle, forwarded
                to `httpx.AsyncClient(verify=...)`.
            ssl_client_cert: Optional path to a client certificate (mTLS),
                forwarded to `httpx.AsyncClient(cert=...)`.
        """
        self.model = model
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.http_proxy = http_proxy
        self.ssl_ca_bundle = ssl_ca_bundle
        self.ssl_client_cert = ssl_client_cert
        self._extra_init_kwargs = kwargs

    def _client_kwargs(self) -> dict:
        """Builds the httpx.AsyncClient kwargs for proxy/TLS config."""
        client_kwargs: dict = {}
        if self.http_proxy:
            client_kwargs["proxy"] = self.http_proxy
        if self.ssl_ca_bundle:
            client_kwargs["verify"] = self.ssl_ca_bundle
        if self.ssl_client_cert:
            client_kwargs["cert"] = self.ssl_client_cert
        return client_kwargs

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Sends `messages` to the Ollama `/api/chat` endpoint and returns
        the completion text.

        Raises:
            RuntimeError: on a non-2xx response (message includes the
                status code and response body), or if the response body
                does not have the expected shape.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **kwargs,
        }

        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )

        if response.status_code >= 300:
            raise RuntimeError(
                f"OllamaProvider: request to {self.base_url}/api/chat failed "
                f"with status {response.status_code}: {response.text}"
            )

        data = response.json()
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(
                f"OllamaProvider: unexpected response shape from Ollama: {data}"
            ) from exc
