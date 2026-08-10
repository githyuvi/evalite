"""Shared fixtures for `tests/server/`.

`mock_storage`: an in-memory fake implementing `StorageBackend`
(`save_run`, `get_run`, `list_runs`), backed by a plain dict keyed by a
generated UUID `run_id`. Used by this task's own tests and every later
Phase 4 test file (REST routes, WebSocket route) that needs a storage
backend without a real database.

`test_client`: a `fastapi.testclient.TestClient` wrapping
`create_app(mock_storage)`, with `EVALITE_API_KEY` set to a known-good
test value so tests can send it in the `X-API-Key` header.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from evalite.runner.result import RunResult
from evalite.server.app import create_app

TEST_API_KEY = "test-key-123"


class MockStorage:
    """In-memory fake `StorageBackend`, backed by a dict keyed by run_id."""

    def __init__(self) -> None:
        self.runs: dict[str, RunResult] = {}

    async def save_run(self, run: RunResult) -> str:
        run_id = str(uuid.uuid4())
        self.runs[run_id] = run
        return run_id

    async def get_run(self, run_id: str) -> RunResult | None:
        return self.runs.get(run_id)

    async def list_runs(self, limit: int = 50) -> list[dict]:
        entries = [
            {
                "run_id": run_id,
                "test_set_name": run.test_set_name,
                "passed": run.passed,
                "failed": run.failed,
                "timestamp": "",
            }
            for run_id, run in self.runs.items()
        ]
        return entries[:limit]


@pytest.fixture
def mock_storage() -> MockStorage:
    return MockStorage()


@pytest.fixture
def test_client(mock_storage: MockStorage, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("EVALITE_API_KEY", TEST_API_KEY)
    app = create_app(mock_storage)
    return TestClient(app)
