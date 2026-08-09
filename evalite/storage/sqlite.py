"""SQLite-backed `StorageBackend` implementation.

Per ADR-003, SQLite (via the `aiosqlite` async driver) is the default
storage backend: zero infra, file-based, safe for single-node/CI use.
`SqliteStorage` implements the `StorageBackend` Protocol
(`evalite/storage/base.py`) on top of the ORM models produced by
`create_models` (`evalite/storage/models.py`).

Reconstruction strategy: `get_run` rebuilds the `RunResult` from the
`result_json` column via `RunResult.model_validate_json(...)` rather than
re-assembling it from the relational `CaseResult` rows. `result_json` is
stored specifically to make this a lossless round-trip (see the `Run`
model's docstring), whereas rebuilding from relational columns would be
redundant work that risks losing information the JSON already preserves
exactly (e.g. Pydantic validation, field order, any future fields added
to `CaseResult`/`Score` that don't get a dedicated column).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evalite.runner.result import RunResult
from evalite.storage.models import Models, create_models


class SqliteStorage:
    """`StorageBackend` implementation backed by SQLite via `aiosqlite`.

    Not safe for concurrent writes from multiple processes (ADR-003);
    fine for single-node/CI use, which is the default use case.
    """

    def __init__(self, db_path: str = "evalite.db", prefix: str = "") -> None:
        """Configure the engine and ORM models for this storage instance.

        Args:
            db_path: filesystem path to the SQLite database file.
            prefix: table name prefix, passed through to `create_models`.
        """
        self._engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
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
