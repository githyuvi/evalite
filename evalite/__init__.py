from evalite.agent.protocol import AgentAdapter, AgentResponse
from evalite.agent.sync_adapter import sync_adapter
from evalite.testcase.models import TestCase, TestSet, ExpectedOutput
from evalite.testcase.loader import load_test_set
from evalite.runner.runner import Runner
from evalite.runner.result import Score, CaseResult, RunResult
from evalite.scorer.base import Scorer
from evalite.scorer.default import DefaultScorer
from evalite.reporter.console import ConsoleReporter

# Storage classes (`StorageBackend`, `SqliteStorage`, `PostgresStorage`) are
# intentionally NOT re-exported here. Import them from `evalite.storage.*`
# directly. The core `evalite` package must stay importable without
# `sqlalchemy`/`aiosqlite` installed, since storage is an opt-in extra
# (ADR-003) — re-exporting them at the top level would force those
# dependencies onto every `import evalite`.
__all__ = [
    "AgentAdapter", "AgentResponse", "sync_adapter",
    "TestCase", "TestSet", "ExpectedOutput", "load_test_set",
    "Runner", "Score", "CaseResult", "RunResult",
    "Scorer", "DefaultScorer",
    "ConsoleReporter",
]
