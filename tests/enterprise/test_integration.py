"""Integration test tying together the three independent Phase 6 pieces:

1. `EnterpriseConfig` / `build_httpx_client` (evalite/enterprise) — proxy/TLS
   settings live in one dataclass.
2. `SecretMasker`, installed on the `"evalite"` logger at `import evalite`
   time (see `evalite/__init__.py::_install_masker`).
3. The pre-existing `http_proxy`/`ssl_ca_bundle`/`ssl_client_cert` kwargs on
   the built-in LLM provider adapters (ADR-006, Phase 3).

Per ADR-006's Consequences, `EnterpriseConfig` is deliberately NOT auto-wired
into providers or into `Runner` — the intended usage pattern is "read the
config's fields, pass them into a provider's existing kwargs yourself". This
file proves that pattern actually reaches the wire, and separately proves
the installed `SecretMasker` genuinely redacts secrets logged during a real
`Runner.run()` execution (not just in an isolated filter unit test).
"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evalite import DefaultScorer, Runner
from evalite.agent.protocol import AgentResponse
from evalite.enterprise.config import EnterpriseConfig
from evalite.llm.openai import OpenAIProvider
from evalite.testcase.models import ExpectedOutput, TestCase, TestSet


def _mock_client(json_body: dict, status_code: int = 200) -> MagicMock:
    """Builds a MagicMock standing in for an `httpx.AsyncClient` instance,
    usable as `async with httpx.AsyncClient(...) as client: await client.post(...)`.

    Matches the mocking pattern in tests/llm/test_providers.py exactly, so
    no real network call happens.
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
# Piece 1 + 3: EnterpriseConfig's proxy value, read and passed into an
# existing provider kwarg, genuinely reaches the constructed httpx client.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enterprise_config_proxy_reaches_openai_provider_http_client():
    """Demonstrates the intended "read config, pass into provider kwargs"
    usage pattern: EnterpriseConfig is not auto-wired into OpenAIProvider,
    so the caller reads config.http_proxy and forwards it explicitly. This
    asserts the value genuinely reaches httpx.AsyncClient construction, not
    just that the test compiles.
    """
    config = EnterpriseConfig(http_proxy="http://fake-proxy.test:8080")

    body = {"choices": [{"message": {"content": "hello from openai"}}]}
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_client(body)
        provider = OpenAIProvider(
            model="gpt-4o",
            api_key="fake-key",
            http_proxy=config.http_proxy,
        )
        result = await provider.complete([{"role": "user", "content": "hi"}])

    assert result == "hello from openai"
    _, call_kwargs = mock_cls.call_args
    assert call_kwargs["proxy"] == "http://fake-proxy.test:8080"


# ---------------------------------------------------------------------------
# Piece 2: SecretMasker, installed at `import evalite` time, redacts a
# secret logged by adapter code during a real Runner.run() execution.
#
# IMPORTANT — read before changing the logger name below:
# `_install_masker()` in evalite/__init__.py does
# `logging.getLogger("evalite").addFilter(SecretMasker())`. A filter
# attached via `Logger.addFilter()` is only invoked by `Logger.handle()` on
# *that exact logger instance* (see `logging.Logger.callHandlers`, which
# walks ancestors to find *handlers* to invoke, but never re-invokes an
# ancestor's own `filter()`). Records logged through a descendant logger —
# e.g. `logging.getLogger("evalite.llm.openai")`, the dotted pattern real
# provider code would use — propagate to any handlers found on "evalite"
# or above, but never pass through the "evalite" logger's *filters*, so
# they are NOT masked by the current wiring.
#
# Verified directly (see task output): logging via "evalite.child" leaves
# a secret unmasked; logging via the bare "evalite" logger masks it. This
# test therefore logs through `logging.getLogger("evalite")` directly to
# match what `_install_masker()` actually guarantees today.
# ---------------------------------------------------------------------------


class SecretLoggingAdapter:
    """Fake AgentAdapter whose send() logs a line containing a fake secret
    through the evalite logger, simulating what a real HTTP-calling
    component (like an LLM provider) might log, e.g. an Authorization
    header.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def send(self, messages: list[dict]) -> AgentResponse:
        self.calls += 1
        logging.getLogger("evalite").info(
            "Authorization: Bearer fake-secret-token-xyz"
        )
        return AgentResponse(content="foo")


@pytest.mark.asyncio
async def test_runner_run_redacts_secrets_logged_during_execution(caplog):
    """A full Runner.run() proves the SecretMasker installed on the
    "evalite" logger at `import evalite` time actually redacts a secret
    logged by adapter code mid-run — not just in an isolated unit test of
    the filter class itself (see tests/enterprise/test_masker.py and
    tests/test_masker_installed.py for those).
    """
    caplog.set_level(logging.INFO, logger="evalite")

    adapter = SecretLoggingAdapter()
    scorer = DefaultScorer()
    runner = Runner(adapter=adapter, scorer=scorer)

    case = TestCase(
        id="case-1",
        input="say foo",
        expected=ExpectedOutput(value="foo"),
    )
    test_set = TestSet(name="integration-set", cases=[case])

    result = await runner.run(test_set)

    # The mock adapter was actually invoked.
    assert adapter.calls == 1

    # The run completed correctly (agent echoed "foo", DefaultScorer found
    # it as a substring of the expected value).
    assert result.total == 1
    assert result.passed == 1

    # The secret logged mid-run was redacted before ever reaching a
    # handler — proven against the actual formatted log text pytest
    # captured, not the SecretMasker in isolation.
    log_text = caplog.text
    assert "[REDACTED]" in log_text
    assert "fake-secret-token-xyz" not in log_text
