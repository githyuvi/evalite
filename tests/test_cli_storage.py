import asyncio

from typer.testing import CliRunner

from evalite.cli import app
from evalite.storage.sqlite import SqliteStorage

runner = CliRunner()

ECHO_AGENT = "tests/fixtures/echo_agent.py"


def _write_test_set(tmp_path, *, expected_contains: str = "42"):
    """Write a minimal test set YAML whose single case echoes `input` back."""
    yaml_content = f"""
name: echo_test_set
cases:
  - id: case_1
    input: "the answer is 42"
    expected:
      contains: "{expected_contains}"
"""
    test_set_path = tmp_path / "test_set.yaml"
    test_set_path.write_text(yaml_content)
    return str(test_set_path)


def test_run_with_db_persists_and_creates_file(tmp_path):
    test_set_path = _write_test_set(tmp_path)
    db_path = tmp_path / "test.db"

    result = runner.invoke(
        app,
        ["run", test_set_path, "--agent", ECHO_AGENT, "--db", f"sqlite:///{db_path}"],
    )

    assert result.exit_code == 0, result.output
    assert db_path.exists()


def test_db_migrate_creates_fresh_sqlite_file_with_working_tables(tmp_path):
    db_path = tmp_path / "fresh.db"
    assert not db_path.exists()

    result = runner.invoke(app, ["db", "migrate", "--db", f"sqlite:///{db_path}"])

    assert result.exit_code == 0, result.output
    assert db_path.exists()

    # Prove the tables actually exist by querying against the same file.
    storage = SqliteStorage(db_path=str(db_path))
    runs = asyncio.run(storage.list_runs())
    assert runs == []


def test_results_lists_recent_runs(tmp_path):
    test_set_path = _write_test_set(tmp_path)
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"

    run_result = runner.invoke(
        app, ["run", test_set_path, "--agent", ECHO_AGENT, "--db", db_url]
    )
    assert run_result.exit_code == 0, run_result.output

    result = runner.invoke(app, ["results", "--db", db_url])

    assert result.exit_code == 0, result.output
    assert "echo_test_set" in result.output


def test_results_with_run_id_shows_case_detail(tmp_path):
    test_set_path = _write_test_set(tmp_path)
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"

    runner.invoke(app, ["run", test_set_path, "--agent", ECHO_AGENT, "--db", db_url])

    storage = SqliteStorage(db_path=str(db_path))
    runs = asyncio.run(storage.list_runs())
    assert len(runs) == 1
    run_id = runs[0]["run_id"]

    result = runner.invoke(app, ["results", "--db", db_url, "--run-id", run_id])

    assert result.exit_code == 0, result.output
    assert "case_1" in result.output


def test_results_with_nonexistent_run_id_exits_one(tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"

    # Prepare the schema first so the lookup fails on "not found", not on
    # a missing table.
    runner.invoke(app, ["db", "migrate", "--db", db_url])

    result = runner.invoke(app, ["results", "--db", db_url, "--run-id", "nonexistent-id"])

    assert result.exit_code == 1
    assert "not found" in result.output
