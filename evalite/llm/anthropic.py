"""Anthropic adapter for the `LLMProvider` Protocol (ADR-006).

Talks to the Anthropic Messages API (`/v1/messages`). Uses
`httpx.AsyncClient` for all I/O per ADR-002 (no blocking calls on the
event loop). Accepts the same enterprise proxy/cert config as agent
adapters, per ADR-006's Consequences.
"""

import os

import httpx

DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 1024


class AnthropicProvider:
    """`LLMProvider` for Anthropic's Messages API.

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
            model: Anthropic model name, e.g. "claude-opus-4-7".
            api_key: Anthropic API key. Falls back to the
                ANTHROPIC_API_KEY env var if not given. Raises at
                construction time if neither is set.
            http_proxy: Optional proxy URL, forwarded to
                `httpx.AsyncClient(proxy=...)`.
            ssl_ca_bundle: Optional path to a custom CA bundle, forwarded
                to `httpx.AsyncClient(verify=...)`.
            ssl_client_cert: Optional path to a client certificate (mTLS),
                forwarded to `httpx.AsyncClient(cert=...)`.
            **kwargs: Extra options. `base_url` overrides the default
                Anthropic API base URL. `anthropic_version` overrides the
                default `anthropic-version` header.
        """
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "AnthropicProvider requires an API key. Pass api_key= "
                "explicitly or set the ANTHROPIC_API_KEY environment variable."
            )
        self.http_proxy = http_proxy
        self.ssl_ca_bundle = ssl_ca_bundle
        self.ssl_client_cert = ssl_client_cert
        self.base_url = kwargs.pop("base_url", DEFAULT_BASE_URL)
        self.anthropic_version = kwargs.pop("anthropic_version", DEFAULT_ANTHROPIC_VERSION)
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
        """Sends `messages` to the Anthropic Messages API and returns the
        completion text.

        The Anthropic API takes system prompts as a top-level `system`
        field rather than a "system" role message, so any `role: system`
        entries in `messages` are extracted and joined into `system`
        before sending the remaining user/assistant turns.

        Raises:
            RuntimeError: on a non-2xx response (message includes the
                status code and response body), or if the response body
                does not have the expected shape.
        """
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        conversation = [m for m in messages if m.get("role") != "system"]

        max_tokens = kwargs.pop("max_tokens", DEFAULT_MAX_TOKENS)
        payload = {
            "model": self.model,
            "messages": conversation,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                json=payload,
                headers=headers,
            )

        if response.status_code >= 300:
            raise RuntimeError(
                f"AnthropicProvider: request to {self.base_url}/v1/messages "
                f"failed with status {response.status_code}: {response.text}"
            )

        data = response.json()
        try:
            blocks = data["content"]
            return "".join(
                block.get("text", "") for block in blocks if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise RuntimeError(
                f"AnthropicProvider: unexpected response shape from Anthropic: {data}"
            ) from exc
