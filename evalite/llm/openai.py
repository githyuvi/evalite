"""OpenAI adapter for the `LLMProvider` Protocol (ADR-006).

Talks to the OpenAI Chat Completions API (`/v1/chat/completions`). Uses
`httpx.AsyncClient` for all I/O per ADR-002 (no blocking calls on the
event loop). Accepts the same enterprise proxy/cert config as agent
adapters, per ADR-006's Consequences.
"""

import os

import httpx

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider:
    """`LLMProvider` for OpenAI's Chat Completions API.

    Satisfies the `LLMProvider` Protocol structurally — no inheritance
    required.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        http_proxy: str | None = None,
        ssl_ca_bundle: str | None = None,
        ssl_client_cert: str | None = None,
        **kwargs,
    ) -> None:
        """
        Args:
            model: OpenAI model name, e.g. "gpt-4o".
            api_key: OpenAI API key. Falls back to the OPENAI_API_KEY
                env var if not given. Raises at construction time (the
                earliest point of misconfiguration) if neither is set.
            http_proxy: Optional proxy URL, forwarded to
                `httpx.AsyncClient(proxy=...)`.
            ssl_ca_bundle: Optional path to a custom CA bundle, forwarded
                to `httpx.AsyncClient(verify=...)`.
            ssl_client_cert: Optional path to a client certificate (mTLS),
                forwarded to `httpx.AsyncClient(cert=...)`.
            **kwargs: Extra options. `base_url` overrides the default
                OpenAI API base URL (useful for OpenAI-compatible
                self-hosted endpoints).
        """
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAIProvider requires an API key. Pass api_key= explicitly "
                "or set the OPENAI_API_KEY environment variable."
            )
        self.http_proxy = http_proxy
        self.ssl_ca_bundle = ssl_ca_bundle
        self.ssl_client_cert = ssl_client_cert
        self.base_url = kwargs.pop("base_url", DEFAULT_BASE_URL)
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
        """Sends `messages` to the OpenAI Chat Completions API and returns
        the completion text.

        Raises:
            RuntimeError: on a non-2xx response (message includes the
                status code and response body), or if the response body
                does not have the expected shape.
        """
        payload = {"model": self.model, "messages": messages, **kwargs}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )

        if response.status_code >= 300:
            raise RuntimeError(
                f"OpenAIProvider: request to {self.base_url}/chat/completions "
                f"failed with status {response.status_code}: {response.text}"
            )

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"OpenAIProvider: unexpected response shape from OpenAI: {data}"
            ) from exc
