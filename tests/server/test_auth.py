"""Tests for `evalite.server.auth.require_api_key`.

Exercised against `GET /api/v1/runs` — a real route that carries
`Depends(require_api_key)` via `routes.runs.router` (see
`evalite/server/routes/runs.py`; the auth dependency is applied
per-router, not at the app level — see `evalite/server/app.py`'s
docstring for why, it's a WebSocket-route compatibility issue, not
related to this test file). Any route on that router would do equally
well; `/api/v1/runs` is a simple, side-effect-free GET.
"""

from fastapi.testclient import TestClient

from evalite.server.app import create_app

TEST_API_KEY = "test-key-123"


def test_missing_api_key_returns_401(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/runs")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_wrong_api_key_returns_401(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/runs", headers={"X-API-Key": "wrong-key"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_correct_api_key_is_not_401(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/runs", headers={"X-API-Key": TEST_API_KEY})

    assert response.status_code == 200


def test_unset_env_var_returns_401_regardless_of_key(mock_storage, monkeypatch) -> None:
    monkeypatch.delenv("EVALITE_API_KEY", raising=False)

    app = create_app(mock_storage)
    client = TestClient(app)

    response = client.get("/api/v1/runs", headers={"X-API-Key": "anything"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}
