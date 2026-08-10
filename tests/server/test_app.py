"""Smoke tests for `evalite.server.app.create_app`."""

import importlib.util
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from evalite.server.app import create_app
from evalite.server.progress import ProgressBus

TEST_API_KEY = "test-key-123"


def test_create_app_returns_fastapi_instance(mock_storage) -> None:
    app = create_app(mock_storage)

    assert isinstance(app, FastAPI)


def test_create_app_sets_storage_on_state(mock_storage) -> None:
    app = create_app(mock_storage)

    assert app.state.storage is mock_storage


def test_create_app_sets_progress_bus_on_state(mock_storage) -> None:
    app = create_app(mock_storage)

    assert isinstance(app.state.progress_bus, ProgressBus)


def test_create_app_without_evalite_ui_serves_api_only(
    mock_storage, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Simulates `evalite_ui` not being installed (regardless of whether it
    actually is in this venv) by making `importlib.util.find_spec` report
    it as absent for that one name, and asserts `create_app` still builds
    a fully-functional API app — the conditional UI mount must be a no-op,
    never a hard dependency — and logs the documented info message.
    """
    monkeypatch.setenv("EVALITE_API_KEY", TEST_API_KEY)

    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, *args, **kwargs):
        if name == "evalite_ui":
            return None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr("importlib.util.find_spec", fake_find_spec)

    with caplog.at_level(logging.INFO, logger="evalite.server.app"):
        app = create_app(mock_storage)

    assert "evalite-ui not installed — serving API only" in caplog.text

    client = TestClient(app)
    response = client.get("/api/v1/runs", headers={"X-API-Key": TEST_API_KEY})

    assert response.status_code == 200
