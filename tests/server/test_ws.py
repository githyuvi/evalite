"""Tests for the WebSocket progress route (`evalite/server/routes/ws.py`)."""

import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from evalite.server.routes.ws import RUN_NOT_FOUND_CLOSE_CODE, UNAUTHORIZED_CLOSE_CODE
from tests.server.conftest import TEST_API_KEY

HEADERS = {"X-API-Key": TEST_API_KEY}


def _start_run(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/runs",
        json={
            "test_set_path": "tests/fixtures/echo_agent_test_set.yaml",
            "agent_class": "tests.fixtures.echo_agent.Agent",
        },
        headers=HEADERS,
    )
    return resp.json()["run_id"]


def test_ws_streams_events_and_closes_after_run_completed(test_client: TestClient) -> None:
    run_id = _start_run(test_client)

    events = []
    with test_client.websocket_connect(f"/ws/v1/runs/{run_id}", headers=HEADERS) as ws:
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["event"] == "run_completed":
                break

    assert events[-1]["event"] == "run_completed"
    assert events[-1]["run_id"] == run_id
    # At least one case_completed event should precede the terminal one
    # (the test set has exactly one case).
    assert any(e["event"] == "case_completed" for e in events)


def test_ws_unknown_run_id_closes_with_4404(test_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with test_client.websocket_connect(
            "/ws/v1/runs/does-not-exist", headers=HEADERS
        ) as ws:
            ws.receive_json()

    assert exc_info.value.code == RUN_NOT_FOUND_CLOSE_CODE


def test_ws_requires_api_key(test_client: TestClient) -> None:
    run_id = _start_run(test_client)
    # Give the (fast) background run a brief moment so the case is scored
    # before we assert on connection rejection — irrelevant to auth, but
    # avoids interleaving flakiness with other tests polling the same run.
    time.sleep(0.05)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with test_client.websocket_connect(f"/ws/v1/runs/{run_id}") as ws:
            ws.receive_json()

    assert exc_info.value.code == UNAUTHORIZED_CLOSE_CODE


def test_ws_wrong_api_key_closes_with_4401(test_client: TestClient) -> None:
    run_id = _start_run(test_client)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with test_client.websocket_connect(
            f"/ws/v1/runs/{run_id}", headers={"X-API-Key": "wrong-key"}
        ) as ws:
            ws.receive_json()

    assert exc_info.value.code == UNAUTHORIZED_CLOSE_CODE


def test_ws_unset_env_var_closes_with_4401_regardless_of_key(test_client: TestClient, monkeypatch) -> None:
    run_id = _start_run(test_client)
    monkeypatch.delenv("EVALITE_API_KEY", raising=False)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with test_client.websocket_connect(
            f"/ws/v1/runs/{run_id}", headers={"X-API-Key": "anything"}
        ) as ws:
            ws.receive_json()

    assert exc_info.value.code == UNAUTHORIZED_CLOSE_CODE
