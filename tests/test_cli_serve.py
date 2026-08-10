"""Tests for `evalite serve` (`evalite/cli.py`)."""

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from evalite.cli import app

runner = CliRunner()


def test_serve_exits_1_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("EVALITE_API_KEY", raising=False)
    db_path = tmp_path / "serve.db"

    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(app, ["serve", "--db", f"sqlite:///{db_path}"])

    assert result.exit_code == 1
    assert "EVALITE_API_KEY" in result.output
    mock_run.assert_not_called()


def test_serve_starts_with_sqlite_backend_when_api_key_set(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALITE_API_KEY", "test-key")
    db_path = tmp_path / "serve.db"

    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(
            app, ["serve", "--db", f"sqlite:///{db_path}", "--host", "127.0.0.1", "--port", "9999"]
        )

    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 9999
    assert db_path.exists()  # storage.init() ran


def test_serve_with_reload_prints_warning_but_still_starts(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALITE_API_KEY", "test-key")
    db_path = tmp_path / "serve.db"

    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(app, ["serve", "--db", f"sqlite:///{db_path}", "--reload"])

    assert result.exit_code == 0, result.output
    assert "not supported" in result.output
    mock_run.assert_called_once()


def test_serve_selects_postgres_backend_for_postgresql_url(tmp_path, monkeypatch):
    # asyncpg (the "postgres" extra) is not installed in this venv, and
    # PostgresStorage.__init__ resolves the asyncpg dialect eagerly via
    # create_async_engine — so the whole class is mocked here, not just
    # .init(), to test the CLI's backend-selection dispatch without
    # requiring a real driver or a live Postgres server.
    monkeypatch.setenv("EVALITE_API_KEY", "test-key")

    with (
        patch("uvicorn.run") as mock_run,
        patch("evalite.storage.postgres.PostgresStorage") as MockPostgresStorage,
    ):
        MockPostgresStorage.return_value.init = AsyncMock()

        result = runner.invoke(
            app,
            [
                "serve",
                "--db",
                "postgresql+asyncpg://user:pass@localhost/evalite_test",
            ],
        )

    assert result.exit_code == 0, result.output
    MockPostgresStorage.assert_called_once_with(url="postgresql+asyncpg://user:pass@localhost/evalite_test")
    MockPostgresStorage.return_value.init.assert_called_once()
    mock_run.assert_called_once()


def test_serve_without_server_extra_exits_1(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALITE_API_KEY", "test-key")
    db_path = tmp_path / "serve.db"

    with patch.dict("sys.modules", {"uvicorn": None}):
        result = runner.invoke(app, ["serve", "--db", f"sqlite:///{db_path}"])

    assert result.exit_code == 1
    assert "[server]" in result.output
