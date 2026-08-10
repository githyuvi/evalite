"""Tests for `evalite.server.auth.require_api_key`.

No real routes exist yet (this is Wave 1) so a throwaway test-only route
is registered directly on the `test_client`'s underlying app, within each
test, purely to exercise the auth dependency in isolation.
"""

from fastapi.testclient import TestClient

from evalite.server.app import create_app

TEST_API_KEY = "test-key-123"


def _add_test_route(client: TestClient) -> None:
    @client.app.get("/_test_route")
    def _test_route() -> dict:
        return {"ok": True}


def test_missing_api_key_returns_401(test_client: TestClient) -> None:
    _add_test_route(test_client)

    response = test_client.get("/_test_route")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_wrong_api_key_returns_401(test_client: TestClient) -> None:
    _add_test_route(test_client)

    response = test_client.get("/_test_route", headers={"X-API-Key": "wrong-key"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_correct_api_key_is_not_401(test_client: TestClient) -> None:
    _add_test_route(test_client)

    response = test_client.get("/_test_route", headers={"X-API-Key": TEST_API_KEY})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_unset_env_var_returns_401_regardless_of_key(mock_storage, monkeypatch) -> None:
    monkeypatch.delenv("EVALITE_API_KEY", raising=False)

    app = create_app(mock_storage)
    client = TestClient(app)
    _add_test_route(client)

    response = client.get("/_test_route", headers={"X-API-Key": "anything"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}
