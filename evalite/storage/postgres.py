"""PostgreSQL-backed `StorageBackend` implementation.

Per ADR-003, PostgreSQL is an opt-in storage backend (the `postgres`
extra, `asyncpg>=0.29`) for multi-node/production use, as opposed to the
default `SqliteStorage` (zero infra, single-node/CI use). `PostgresStorage`
implements the same `StorageBackend` Protocol (`evalite/storage/base.py`)
on top of the same engine-agnostic ORM models produced by `create_models`
(`evalite/storage/models.py`) — only the engine construction in
`__init__` differs from `SqliteStorage`; `init`, `save_run`, `get_run`,
and `list_runs` are structurally identical.

This module must never be imported unconditionally from elsewhere in the
package (e.g. not from `evalite/storage/__init__.py`), since `asyncpg` is
not a mandatory dependency. Note that this module does not import
`asyncpg` directly — `create_async_engine` resolves the `asyncpg` dialect
lazily, only when a `PostgresStorage` is actually instantiated, so simply
importing this module is safe even without the `postgres` extra
installed; only *constructing* `PostgresStorage` requires it.

Reconstruction strategy: identical to `SqliteStorage` — `get_run` rebuilds
the `RunResult` from the `result_json` column via
`RunResult.model_validate_json(...)` rather than re-assembling it from the
relational `CaseResult` rows (see `evalite/storage/sqlite.py`'s module
docstring for the full rationale).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evalite.runner.result import RunResult
from evalite.storage.models import Models, create_models


class PostgresStorage:
    """`StorageBackend` implementation backed by PostgreSQL via `asyncpg`.

    Suitable for multi-node/production use, unlike `SqliteStorage`
    (ADR-003).
    """

    def __init__(self, url: str, prefix: str = "") -> None:
        """Configure the engine and ORM models for this storage instance.

        Args:
            url: full async SQLAlchemy connection URL, expected to
                already be in `postgresql+asyncpg://...` form (e.g.
                `"postgresql+asyncpg://user:password@host:5432/dbname"`).
                Passed through to `create_async_engine` as-is — it is
                not normalized or rewritten, so a bare `postgresql://`
                URL will fail; callers must include the `+asyncpg`
                driver segment themselves.
            prefix: table name prefix, passed through to `create_models`.
        """
        self._engine = create_async_engine(url)
        self._models: Models = create_models(prefix)
        self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init(self) -> None:
        """Create the backend's tables if they don't already exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(self._models.Base.metadata.create_all)

    async def save_run(self, run: RunResult) -> str:
        """Persist a completed run as one `Run` row and N `CaseResult` rows.

        All rows are written in a single transaction (one session, one
        commit) rather than one commit per row.

        Args:
            run: the aggregated result of a test set run.

        Returns:
            The generated `run_id` (UUID string) the run was stored under.
        """
        run_id = str(uuid.uuid4())

        async with self._sessionmaker() as session:
            session.add(
                self._models.Run(
                    id=run_id,
                    test_set_name=run.test_set_name,
                    total=run.total,
                    passed=run.passed,
                    failed=run.failed,
                    pass_rate=run.pass_rate,
                    duration_ms=run.duration_ms,
                    result_json=run.model_dump_json(),
                )
            )

            for case_result in run.case_results:
                session.add(
                    self._models.CaseResult(
                        run_id=run_id,
                        case_id=case_result.case_id,
                        iteration=case_result.iteration,
                        input=case_result.input,
                        actual=case_result.actual,
                        score_value=case_result.score.value,
                        score_passed=case_result.score.passed,
                        score_reasoning=case_result.score.reasoning,
                        passed=case_result.passed,
                        duration_ms=case_result.duration_ms,
                    )
                )

            await session.commit()

        return run_id

    async def get_run(self, run_id: str) -> RunResult | None:
        """Fetch a previously persisted run by id.

        Reconstructs the `RunResult` from the stored `result_json`
        (see module docstring for why).

        Args:
            run_id: the UUID string returned by `save_run`.

        Returns:
            The reconstructed `RunResult`, or `None` if no run with that
            id exists.
        """
        async with self._sessionmaker() as session:
            row = await session.get(self._models.Run, run_id)

        if row is None:
            return None

        return RunResult.model_validate_json(row.result_json)

    async def list_runs(self, limit: int = 50) -> list[dict]:
        """List recent runs without loading full per-case detail.

        Args:
            limit: maximum number of runs to return, most recent first.

        Returns:
            Lightweight dicts, one per run, each with keys: `run_id`,
            `test_set_name`, `passed`, `failed`, `timestamp`.
        """
        Run = self._models.Run
        stmt = select(Run).order_by(Run.created_at.desc()).limit(limit)

        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            {
                "run_id": row.id,
                "test_set_name": row.test_set_name,
                "passed": row.passed,
                "failed": row.failed,
                "timestamp": row.created_at.isoformat(),
            }
            for row in rows
        ]
