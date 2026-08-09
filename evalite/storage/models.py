"""SQLAlchemy 2.x async ORM models for evalite's storage layer.

Two tables are defined per `Storage` instance: `{prefix}runs` (one row
per `RunResult`) and `{prefix}case_results` (one row per `CaseResult`,
kept relational for queryability even though the full run is also stored
as JSON on the `runs` row). These models use `DeclarativeBase` /
`Mapped` / `mapped_column` (SQLAlchemy 2.x style) and only column types
that both `aiosqlite` and `asyncpg` support identically — no engine-
specific types — so the same model code works against either backend
per ADR-003; only the connection string changes.

Table prefix is a `Storage` construction-time concern, but SQLAlchemy
declarative models normally have `__tablename__` as a class-level
constant fixed at class-definition time. To reconcile that, models are
built by a factory function, `create_models(prefix)`, instead of being
declared as fixed module-level classes. Each call returns a *fresh*
`DeclarativeBase` subclass and a fresh pair of model classes bound to
it, rather than one shared `Base` reused across calls. This is the more
conservative of the two approaches described in the task brief (factory
function vs. shared-`Base` + `__table_args__` tricks): a shared registry
would raise `InvalidRequestError: Table '...' is already defined` the
moment two `Storage` instances used the same prefix (e.g. two SQLite
files, or unit tests instantiating the factory twice with prefix=""),
since SQLAlchemy's declarative registry maps table name -> class within
a single `Base`. Giving every `create_models` call its own `Base` avoids
that entirely and matches the requirement that two factory calls must
produce genuinely independent classes, not the same object reused.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def table_name(prefix: str, base: str) -> str:
    """Construct a prefixed table name.

    Args:
        prefix: table name prefix configured on `Storage` (e.g.
            "myteam_"). Empty string means no prefix.
        base: the unprefixed table base name (e.g. "runs").

    Returns:
        `f"{prefix}{base}"`.
    """
    return f"{prefix}{base}"


@dataclass(frozen=True)
class Models:
    """Bundle of ORM classes produced by `create_models` for one prefix.

    Attributes:
        Base: the `DeclarativeBase` subclass `Run` and `CaseResult` are
            registered on. Callers use `Base.metadata.create_all`
            (invoked via an async engine's `run_sync`, since
            `create_all` itself is a sync call) to create the tables.
        Run: ORM model for the `{prefix}runs` table.
        CaseResult: ORM model for the `{prefix}case_results` table.
    """

    Base: type[DeclarativeBase]
    Run: type
    CaseResult: type


def create_models(prefix: str = "") -> Models:
    """Build a fresh, independently-registered set of ORM model classes.

    SQLAlchemy declarative models need `__tablename__` as a class
    attribute, but the table prefix is only known once a `Storage` is
    constructed (an instance-level concern). This factory closes over
    `prefix` and builds the classes dynamically, on a brand-new `Base`,
    so each call is fully isolated: calling this twice — even with the
    identical prefix — never returns the same class objects and never
    shares a declarative registry, so multiple `Storage` instances (or
    tests) can coexist in the same process without colliding.

    Args:
        prefix: table name prefix, e.g. "myteam_". Empty string
            (default) means no prefix — tables are named "runs" and
            "case_results".

    Returns:
        A `Models` bundle with `.Base`, `.Run`, and `.CaseResult`.
    """

    class Base(DeclarativeBase):
        pass

    class Run(Base):
        """One row per `RunResult`.

        `result_json` holds the full `RunResult` as serialised by
        `RunResult.model_dump_json()`, so `StorageBackend.get_run` can
        reconstruct the exact Pydantic object (including every
        `CaseResult` and `Score`) without lossily rebuilding it from
        relational columns. The other columns exist so `list_runs` and
        ad-hoc SQL queries don't need to deserialise JSON just to get
        summary fields.
        """

        __tablename__ = table_name(prefix, "runs")

        id: Mapped[str] = mapped_column(primary_key=True)
        test_set_name: Mapped[str] = mapped_column()
        total: Mapped[int] = mapped_column()
        passed: Mapped[int] = mapped_column()
        failed: Mapped[int] = mapped_column()
        pass_rate: Mapped[float] = mapped_column()
        duration_ms: Mapped[float] = mapped_column()
        result_json: Mapped[str] = mapped_column(Text())
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), server_default=func.now()
        )

    class CaseResult(Base):
        """One row per `CaseResult`, kept relational for queryability."""

        __tablename__ = table_name(prefix, "case_results")

        id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
        run_id: Mapped[str] = mapped_column(ForeignKey(f"{Run.__tablename__}.id"))
        case_id: Mapped[str] = mapped_column()
        iteration: Mapped[int] = mapped_column()
        input: Mapped[str] = mapped_column(Text())
        actual: Mapped[str] = mapped_column(Text())
        score_value: Mapped[float] = mapped_column()
        score_passed: Mapped[bool] = mapped_column()
        score_reasoning: Mapped[str] = mapped_column(Text())
        passed: Mapped[bool] = mapped_column()
        duration_ms: Mapped[float] = mapped_column()

    return Models(Base=Base, Run=Run, CaseResult=CaseResult)
