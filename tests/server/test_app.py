"""Smoke tests for `evalite.server.app.create_app`."""

from fastapi import FastAPI

from evalite.server.app import create_app
from evalite.server.progress import ProgressBus


def test_create_app_returns_fastapi_instance(mock_storage) -> None:
    app = create_app(mock_storage)

    assert isinstance(app, FastAPI)


def test_create_app_sets_storage_on_state(mock_storage) -> None:
    app = create_app(mock_storage)

    assert app.state.storage is mock_storage


def test_create_app_sets_progress_bus_on_state(mock_storage) -> None:
    app = create_app(mock_storage)

    assert isinstance(app.state.progress_bus, ProgressBus)
