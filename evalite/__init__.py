import logging

from evalite.agent.protocol import AgentAdapter, AgentResponse
from evalite.agent.sync_adapter import sync_adapter
from evalite.testcase.models import TestCase, TestSet, ExpectedOutput
from evalite.testcase.loader import load_test_set
from evalite.runner.runner import Runner
from evalite.runner.result import Score, CaseResult, RunResult
from evalite.scorer.base import Scorer
from evalite.scorer.default import DefaultScorer
from evalite.reporter.console import ConsoleReporter
from evalite.llm import (
    LLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    AzureOpenAIProvider,
    OllamaProvider,
)
from evalite.scorer.pipeline import (
    Category,
    DEFAULT_CATEGORIES,
    Extractor,
    LLMExtractor,
    PatternExtractor,
    Judge,
    LLMJudge,
    RuleJudge,
    PipelineScorer,
)
from evalite.scorer.pipeline.accumulator import Accumulator, DefaultAccumulator
from evalite.scorer.regex import RegexScorer
from evalite.scorer.json_path import JsonPathScorer
from evalite.scorer.tool_call import ToolCallScorer
from evalite.scorer.semantic import SemanticSimilarityScorer
from evalite.testcase.conversation import ConversationTestCase, ConversationDriver
from evalite.runner.conversation_runner import ConversationRunner
from evalite.enterprise.masker import SecretMasker

# Storage classes (`StorageBackend`, `SqliteStorage`, `PostgresStorage`) are
# intentionally NOT re-exported here. Import them from `evalite.storage.*`
# directly. The core `evalite` package must stay importable without
# `sqlalchemy`/`aiosqlite` installed, since storage is an opt-in extra
# (ADR-003) — re-exporting them at the top level would force those
# dependencies onto every `import evalite`.
#
# `LiteLLMProvider` (from `evalite.extras.litellm`) is likewise intentionally
# NOT re-exported here. Import it from `evalite.extras.litellm` directly —
# `evalite/extras/` is a separate opt-in namespace for power-user providers
# with heavier optional dependencies (ADR-006).


def _install_masker() -> None:
    """Adds a SecretMasker filter to the evalite logger, so log output
    never leaks secrets like API keys or Bearer tokens.
    """
    logger = logging.getLogger("evalite")
    logger.addFilter(SecretMasker())


_install_masker()

__all__ = [
    "AgentAdapter", "AgentResponse", "sync_adapter",
    "TestCase", "TestSet", "ExpectedOutput", "load_test_set",
    "Runner", "Score", "CaseResult", "RunResult",
    "Scorer", "DefaultScorer",
    "ConsoleReporter",
    "LLMProvider", "OpenAIProvider", "AnthropicProvider", "AzureOpenAIProvider", "OllamaProvider",
    "Category", "DEFAULT_CATEGORIES", "Extractor", "LLMExtractor", "PatternExtractor",
    "Judge", "LLMJudge", "RuleJudge", "Accumulator", "DefaultAccumulator", "PipelineScorer",
    "RegexScorer", "JsonPathScorer", "ToolCallScorer", "SemanticSimilarityScorer",
    "ConversationTestCase", "ConversationDriver",
    "ConversationRunner",
]
