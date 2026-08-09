import asyncio
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from evalite.cli import app
from evalite.storage.sqlite import SqliteStorage

runner = CliRunner()

ECHO_AGENT = "tests/fixtures/echo_agent.py"

# `evalite/` project root (where pyproject.toml lives) — this file is at
# `evalite/tests/test_cli_storage.py`, so it's two levels up.
REPO_ROOT = Path(__file__).resolve().parent.parent


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


def test_parse_db_url_rejects_unsupported_scheme():
    """`_parse_db_url` only supports `sqlite:///` — anything else (e.g. a
    real postgresql:// URL) must exit 1 with a clear message, without ever
    reaching (or requiring) `SqliteStorage`/sqlalchemy.

    Exercised through the `db migrate` subcommand since it takes no
    arguments besides `--db`, so this stays a fast in-process CliRunner
    test rather than a subprocess test.
    """
    result = runner.invoke(
        app, ["db", "migrate", "--db", "postgresql+asyncpg://user:pass@host/db"]
    )

    assert result.exit_code == 1
    assert "unsupported --db value" in result.output
    assert "only sqlite:/// URLs are supported" in result.output


def test_cli_help_works_without_storage_extras_installed(tmp_path):
    """Regression test: cli.py must not import sqlalchemy/aiosqlite at
    module level, since evalite's core install (no `[storage]` extra)
    must not require them.

    This builds a throwaway venv, installs *only* the bare `evalite`
    package (no `[storage]`/`[dev]` extras) into it, and proves that both
    `evalite --help` and a no-`--db` `evalite run` succeed there — i.e.
    that `sqlalchemy`/`aiosqlite` are genuinely absent and unneeded for
    those code paths.

    This is slower than the rest of the suite (real venv creation + pip
    install, tens of seconds) by design: it's the only way to actually
    prove "works without storage extras installed", since the `dev`
    extras used by every other test in this repo (and CI) always pull in
    sqlalchemy/aiosqlite anyway, which is exactly how this bug shipped
    undetected the first time.
    """
    venv_dir = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    venv_python = venv_dir / "bin" / "python"
    venv_evalite = venv_dir / "bin" / "evalite"

    install = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "-q", "-e", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    # Sanity-check the premise of the test: sqlalchemy/aiosqlite must NOT
    # be importable in this venv, otherwise this test would pass for the
    # wrong reason (i.e. it wouldn't actually be exercising the bug).
    check_absent = subprocess.run(
        [str(venv_python), "-c", "import sqlalchemy"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert check_absent.returncode != 0, (
        "sqlalchemy is importable in the bare venv — this test's premise "
        "doesn't hold (check pyproject.toml core `dependencies`)"
    )

    help_result = subprocess.run(
        [str(venv_evalite), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert help_result.returncode == 0, help_result.stdout + help_result.stderr
    assert "ModuleNotFoundError" not in help_result.stderr

    test_set_path = tmp_path / "test_set.yaml"
    test_set_path.write_text(
        """
name: echo_test_set
cases:
  - id: case_1
    input: "the answer is 42"
    expected:
      contains: "42"
"""
    )
    agent_path = REPO_ROOT / ECHO_AGENT

    run_result = subprocess.run(
        [str(venv_evalite), "run", str(test_set_path), "--agent", str(agent_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert "ModuleNotFoundError" not in run_result.stderr
