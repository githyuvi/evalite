"""Tests for `evalite.storage.sqlite.SqliteStorage`.

Unlike `tests/storage/test_models.py` (which only exercises model
*definitions*), these tests open a real (temp-file) SQLite database and
exercise the full `save_run` / `get_run` / `list_runs` round trip.
"""

import asyncio

from evalite.runner.result import CaseResult, RunResult, Score
from evalite.storage.sqlite import SqliteStorage


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


async def test_save_and_get_run_round_trips(tmp_path):
    """A saved run is retrievable with matching fields via `get_run`."""
    db_path = str(tmp_path / "test.db")
    storage = SqliteStorage(db_path=db_path)
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


async def test_get_run_returns_none_for_missing_run(tmp_path):
    """`get_run` with a non-existent id returns `None`."""
    db_path = str(tmp_path / "test.db")
    storage = SqliteStorage(db_path=db_path)
    await storage.init()

    result = await storage.get_run("does-not-exist")

    assert result is None


async def test_list_runs_returns_all_saved_runs(tmp_path):
    """`list_runs()` after saving 3 runs returns exactly 3 entries."""
    db_path = str(tmp_path / "test.db")
    storage = SqliteStorage(db_path=db_path)
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


async def test_list_runs_respects_limit_and_orders_most_recent_first(tmp_path):
    """`list_runs(limit=2)` after saving 3 runs returns exactly 2, newest first."""
    db_path = str(tmp_path / "test.db")
    storage = SqliteStorage(db_path=db_path)
    await storage.init()

    # SQLite's CURRENT_TIMESTAMP (used for `created_at` via `func.now()` in
    # models.py) only has second-level resolution, so a short sleep isn't
    # enough to guarantee distinct, orderable timestamps between saves —
    # sleep past a full second boundary between each save instead.
    run_ids = []
    for i in range(3):
        run = _make_run_result(test_set_name=f"test_set_{i}")
        run_id = await storage.save_run(run)
        run_ids.append(run_id)
        await asyncio.sleep(1.1)

    runs = await storage.list_runs(limit=2)

    assert len(runs) == 2
    # Most recent first: the last two saved runs, in reverse save order.
    assert [entry["run_id"] for entry in runs] == [run_ids[2], run_ids[1]]


async def test_prefix_isolation_across_shared_db_file(tmp_path):
    """Two `SqliteStorage` instances with different prefixes, same db file, don't collide."""
    db_path = str(tmp_path / "shared.db")

    storage_default = SqliteStorage(db_path=db_path, prefix="")
    storage_team_a = SqliteStorage(db_path=db_path, prefix="teamA_")

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
