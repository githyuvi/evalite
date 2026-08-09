"""Tests for `evalite.storage.postgres.PostgresStorage`.

Mirrors `tests/storage/test_sqlite.py`'s test cases and assertions
against a real PostgreSQL server instead of a temp-file SQLite database.

These tests require a live PostgreSQL instance and the `postgres` extra
(`asyncpg`) installed, neither of which is assumed to be available in
every environment (e.g. CI without a Postgres service, or a local dev
box). They are gated on the `EVALITE_TEST_POSTGRES_URL` environment
variable and skipped entirely when it isn't set — see `pytestmark`
below. `EVALITE_TEST_POSTGRES_URL` must be a full async SQLAlchemy URL in
`postgresql+asyncpg://...` form, matching what `PostgresStorage.__init__`
expects (e.g.
`"postgresql+asyncpg://postgres:postgres@localhost:5432/evalite_test"`).

Each test uses a unique table prefix (derived from a `uuid4` fragment via
the `prefix` fixture) so concurrent/repeated test runs against the same
shared database don't collide on table names.
"""

import asyncio
import os
import uuid

import pytest

from evalite.runner.result import CaseResult, RunResult, Score

POSTGRES_URL = os.environ.get("EVALITE_TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="EVALITE_TEST_POSTGRES_URL not set — skipping PostgreSQL integration tests",
)

if POSTGRES_URL is not None:
    from evalite.storage.postgres import PostgresStorage


@pytest.fixture
def prefix() -> str:
    """A unique table prefix per test, so tests don't collide on table names."""
    return f"test_{uuid.uuid4().hex[:8]}_"


def _make_run_result(test_set_name: str = "my_test_set") -> RunResult:
    """Build a `RunResult` with real Pydantic model constructors (no mocking)."""
    case_results = [
        CaseResult(
            case_id="case-1",
            iteration=0,
            input="what is 2+2?",
            actual="4",
            score=Score(passed=True, value=1.0, reasoning="exact match"),
            passed=True,
            duration_ms=12.5,
        ),
        CaseResult(
            case_id="case-2",
            iteration=0,
            input="what is the capital of France?",
            actual="London",
            score=Score(passed=False, value=0.0, reasoning="wrong city"),
            passed=False,
            duration_ms=8.3,
        ),
        CaseResult(
            case_id="case-3",
            iteration=1,
            input="what is 2+2?",
            actual="4",
            score=Score(passed=True, value=1.0, reasoning="exact match"),
            passed=True,
            duration_ms=10.1,
        ),
    ]
    return RunResult(
        test_set_name=test_set_name,
        total=len(case_results),
        passed=2,
        failed=1,
        pass_rate=2 / 3,
        case_results=case_results,
        duration_ms=30.9,
    )


async def test_save_and_get_run_round_trips(prefix):
    """A saved run is retrievable with matching fields via `get_run`."""
    storage = PostgresStorage(url=POSTGRES_URL, prefix=prefix)
    await storage.init()

    original = _make_run_result()
    run_id = await storage.save_run(original)

    retrieved = await storage.get_run(run_id)

    assert retrieved is not None
    assert retrieved.test_set_name == original.test_set_name
    assert retrieved.total == original.total
    assert retrieved.passed == original.passed
    assert retrieved.failed == original.failed
    assert retrieved.pass_rate == original.pass_rate
    assert retrieved.duration_ms == original.duration_ms
    assert len(retrieved.case_results) == len(original.case_results)
    assert retrieved.case_results == original.case_results


async def test_get_run_returns_none_for_missing_run(prefix):
    """`get_run` with a non-existent id returns `None`."""
    storage = PostgresStorage(url=POSTGRES_URL, prefix=prefix)
    await storage.init()

    result = await storage.get_run("does-not-exist")

    assert result is None


async def test_list_runs_returns_all_saved_runs(prefix):
    """`list_runs()` after saving 3 runs returns exactly 3 entries."""
    storage = PostgresStorage(url=POSTGRES_URL, prefix=prefix)
    await storage.init()

    run_ids = []
    for i in range(3):
        run = _make_run_result(test_set_name=f"test_set_{i}")
        run_id = await storage.save_run(run)
        run_ids.append(run_id)
        await asyncio.sleep(0.01)

    runs = await storage.list_runs()

    assert len(runs) == 3
    listed_ids = {entry["run_id"] for entry in runs}
    assert listed_ids == set(run_ids)

    for entry in runs:
        assert "run_id" in entry
        assert "test_set_name" in entry
        assert "passed" in entry
        assert "failed" in entry
        assert "timestamp" in entry
        assert entry["passed"] == 2
        assert entry["failed"] == 1


async def test_list_runs_respects_limit_and_orders_most_recent_first(prefix):
    """`list_runs(limit=2)` after saving 3 runs returns exactly 2, newest first."""
    storage = PostgresStorage(url=POSTGRES_URL, prefix=prefix)
    await storage.init()

    # Unlike SQLite's CURRENT_TIMESTAMP (second-level resolution), Postgres's
    # NOW() (used for `created_at` via `func.now()` in models.py) has
    # microsecond resolution, so a short sleep between saves is enough to
    # guarantee distinct, orderable timestamps.
    run_ids = []
    for i in range(3):
        run = _make_run_result(test_set_name=f"test_set_{i}")
        run_id = await storage.save_run(run)
        run_ids.append(run_id)
        await asyncio.sleep(0.01)

    runs = await storage.list_runs(limit=2)

    assert len(runs) == 2
    # Most recent first: the last two saved runs, in reverse save order.
    assert [entry["run_id"] for entry in runs] == [run_ids[2], run_ids[1]]


async def test_prefix_isolation_across_shared_db(prefix):
    """Two `PostgresStorage` instances with different prefixes, same db, don't collide."""
    storage_default = PostgresStorage(url=POSTGRES_URL, prefix=prefix)
    storage_team_a = PostgresStorage(url=POSTGRES_URL, prefix=f"{prefix}teamA_")

    await storage_default.init()
    await storage_team_a.init()

    default_run_id = await storage_default.save_run(
        _make_run_result(test_set_name="default_set")
    )
    team_a_run_id = await storage_team_a.save_run(
        _make_run_result(test_set_name="team_a_set")
    )

    default_runs = await storage_default.list_runs()
    team_a_runs = await storage_team_a.list_runs()

    assert len(default_runs) == 1
    assert default_runs[0]["run_id"] == default_run_id
    assert default_runs[0]["test_set_name"] == "default_set"

    assert len(team_a_runs) == 1
    assert team_a_runs[0]["run_id"] == team_a_run_id
    assert team_a_runs[0]["test_set_name"] == "team_a_set"

    # Cross-check: each storage can only fetch its own run via get_run.
    assert await storage_default.get_run(team_a_run_id) is None
    assert await storage_team_a.get_run(default_run_id) is None
