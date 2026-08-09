"""Azure OpenAI adapter for the `LLMProvider` Protocol (ADR-006).

Talks to an Azure OpenAI resource's chat completions endpoint:
`{azure_endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}`.
Uses `httpx.AsyncClient` for all I/O per ADR-002 (no blocking calls on
the event loop). Accepts the same enterprise proxy/cert config as agent
adapters, per ADR-006's Consequences.

Azure OpenAI requires more configuration than public OpenAI (a resource
endpoint, a deployment name, and an API version) that the shared
`model` / `api_key` / proxy / cert constructor pattern from ADR-006 does
not have dedicated params for. This adapter adds them as explicit
keyword args rather than burying them in `**kwargs`, since silently
requiring undocumented kwargs would violate the "fail loud, actionable"
standard for a resource that cannot work without them.
"""

import os

import httpx

DEFAULT_API_VERSION = "2024-02-01"


class AzureOpenAIProvider:
    """`LLMProvider` for Azure OpenAI's chat completions API.

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
        azure_endpoint: str | None = None,
        deployment: str | None = None,
        api_version: str = DEFAULT_API_VERSION,
        **kwargs,
    ) -> None:
        """
        Args:
            model: Underlying model name. Also used as the deployment
                name if `deployment` is not given — the most common
                Azure setup names the deployment after the model, but
                callers with differently-named deployments should pass
                `deployment` explicitly.
            api_key: Azure OpenAI API key. Falls back to the
                AZURE_OPENAI_API_KEY env var if not given. Raises at
                construction time if neither is set.
            http_proxy: Optional proxy URL, forwarded to
                `httpx.AsyncClient(proxy=...)`.
            ssl_ca_bundle: Optional path to a custom CA bundle, forwarded
                to `httpx.AsyncClient(verify=...)`.
            ssl_client_cert: Optional path to a client certificate (mTLS),
                forwarded to `httpx.AsyncClient(cert=...)`.
            azure_endpoint: The Azure OpenAI resource endpoint, e.g.
                "https://my-resource.openai.azure.com". Falls back to
                the AZURE_OPENAI_ENDPOINT env var. Raises at construction
                time if neither is set — a request cannot be built
                without it.
            deployment: The Azure deployment name. Defaults to `model`.
            api_version: The Azure OpenAI API version query param.
        """
        self.model = model
        self.api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "AzureOpenAIProvider requires an API key. Pass api_key= "
                "explicitly or set the AZURE_OPENAI_API_KEY environment variable."
            )
        self.azure_endpoint = azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        if not self.azure_endpoint:
            raise ValueError(
                "AzureOpenAIProvider requires azure_endpoint (e.g. "
                "'https://my-resource.openai.azure.com'). Pass azure_endpoint= "
                "explicitly or set the AZURE_OPENAI_ENDPOINT environment variable."
            )
        self.azure_endpoint = self.azure_endpoint.rstrip("/")
        self.deployment = deployment or model
        self.api_version = api_version
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
        """Sends `messages` to the Azure OpenAI deployment's chat
        completions endpoint and returns the completion text.

        Raises:
            RuntimeError: on a non-2xx response (message includes the
                status code and response body), or if the response body
                does not have the expected shape.
        """
        url = (
            f"{self.azure_endpoint}/openai/deployments/{self.deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )
        payload = {"messages": messages, **kwargs}
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code >= 300:
            raise RuntimeError(
                f"AzureOpenAIProvider: request to {url} failed with status "
                f"{response.status_code}: {response.text}"
            )

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"AzureOpenAIProvider: unexpected response shape from Azure OpenAI: {data}"
            ) from exc
