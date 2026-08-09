"""Tests for `evalite.storage.models`.

These tests only exercise model/table *definitions* — no database
connection is opened here. Persistence behaviour (actually writing to
SQLite/Postgres) belongs to the backend implementations built on top of
this factory, not to this module.
"""

from evalite.storage.models import create_models, table_name


def test_table_name_helper():
    """`table_name` just concatenates prefix and base."""
    assert table_name("", "runs") == "runs"
    assert table_name("myteam_", "runs") == "myteam_runs"


def test_run_model_has_expected_columns():
    """`Run` exposes every column needed to store a `RunResult`."""
    models = create_models(prefix="")

    for column in (
        "id",
        "test_set_name",
        "total",
        "passed",
        "failed",
        "pass_rate",
        "duration_ms",
        "result_json",
        "created_at",
    ):
        assert hasattr(models.Run, column), f"Run missing column {column!r}"


def test_case_result_model_has_expected_columns():
    """`CaseResult` exposes every column needed to store a `CaseResult`."""
    models = create_models(prefix="")

    for column in (
        "id",
        "run_id",
        "case_id",
        "iteration",
        "input",
        "actual",
        "score_value",
        "score_passed",
        "score_reasoning",
        "passed",
        "duration_ms",
    ):
        assert hasattr(
            models.CaseResult, column
        ), f"CaseResult missing column {column!r}"


def test_default_prefix_is_unprefixed_table_names():
    """Empty prefix (default) produces plain table names."""
    models = create_models(prefix="")

    assert models.Run.__tablename__ == "runs"
    assert models.CaseResult.__tablename__ == "case_results"


def test_prefix_changes_table_name():
    """A non-empty prefix is applied to both table names."""
    models = create_models(prefix="myteam_")

    assert models.Run.__tablename__ == "myteam_runs"
    assert models.CaseResult.__tablename__ == "myteam_case_results"


def test_factory_calls_produce_independent_classes():
    """Two factory calls never reuse the same class objects or registry.

    This matters because two `Storage` instances (e.g. in tests, or two
    prefixes in the same process) must not collide in SQLAlchemy's
    declarative registry, which raises if two classes claim the same
    table name within one shared `Base`.
    """
    first = create_models(prefix="")
    second = create_models(prefix="")

    assert first.Base is not second.Base
    assert first.Run is not second.Run
    assert first.CaseResult is not second.CaseResult
    # Same table names are fine as long as the classes/registries differ.
    assert first.Run.__tablename__ == second.Run.__tablename__ == "runs"


def test_case_result_foreign_key_targets_prefixed_runs_table():
    """The `run_id` foreign key follows the prefix onto the `runs` table."""
    models = create_models(prefix="myteam_")

    fk_columns = list(models.CaseResult.__table__.c.run_id.foreign_keys)
    assert len(fk_columns) == 1
    assert fk_columns[0].target_fullname == "myteam_runs.id"
