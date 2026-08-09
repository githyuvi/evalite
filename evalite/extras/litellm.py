"""LiteLLM adapter for the `LLMProvider` Protocol (ADR-006).

Wraps `litellm.acompletion` so any model litellm supports (OpenAI,
Anthropic, Azure, Bedrock, Ollama, etc.) can be used as an `LLMProvider`
through a single adapter.

This provider has an optional dependency on `litellm`, which is not a
project dependency of evalite itself. Install it with
`pip install evalite[litellm]` to use this provider.
"""


class LiteLLMProvider:
    """`LLMProvider` for any model supported by litellm.

    Satisfies the `LLMProvider` Protocol structurally — no inheritance
    required.
    """

    def __init__(self, model: str, **kwargs) -> None:
        """
        Args:
            model: litellm model identifier, e.g. "gpt-4o" or
                "anthropic/claude-3-opus-20240229".
            **kwargs: Extra options (e.g. `api_key`, `api_base`) forwarded
                to every `litellm.acompletion` call.

        Raises:
            ImportError: If litellm is not installed.
        """
        try:
            import litellm
        except ImportError as e:
            raise ImportError(
                "LiteLLMProvider requires litellm: pip install evalite[litellm]"
            ) from e

        self._litellm = litellm
        self._model = model
        self._extra_init_kwargs = kwargs

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Sends `messages` to the configured model via litellm and returns
        the completion text.
        """
        response = await self._litellm.acompletion(
            model=self._model,
            messages=messages,
            **{**self._extra_init_kwargs, **kwargs},
        )
        return response.choices[0].message.content
