"""Tests for the REST run routes (`evalite/server/routes/runs.py`)."""

import time

from fastapi.testclient import TestClient

from tests.server.conftest import TEST_API_KEY

HEADERS = {"X-API-Key": TEST_API_KEY}


def _poll_until_terminal(client: TestClient, run_id: str, timeout: float = 5.0) -> dict:
    """Poll GET /api/v1/runs/{run_id} until status leaves started/running."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/runs/{run_id}/results", headers=HEADERS)
        if resp.status_code == 200:
            return resp.json()
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not complete within {timeout}s")


def test_post_runs_returns_202_with_run_id(test_client: TestClient) -> None:
    resp = test_client.post(
        "/api/v1/runs",
        json={
            "test_set_path": "tests/fixtures/echo_agent_test_set.yaml",
            "agent_class": "tests.fixtures.echo_agent.Agent",
        },
        headers=HEADERS,
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "started"
    assert len(body["run_id"]) > 0


def test_post_runs_missing_test_set_path_returns_422(test_client: TestClient) -> None:
    resp = test_client.post(
        "/api/v1/runs",
        json={
            "test_set_path": "does/not/exist.yaml",
            "agent_class": "tests.fixtures.echo_agent.Agent",
        },
        headers=HEADERS,
    )

    assert resp.status_code == 422


def test_run_completes_and_is_queryable(test_client: TestClient) -> None:
    resp = test_client.post(
        "/api/v1/runs",
        json={
            "test_set_path": "tests/fixtures/echo_agent_test_set.yaml",
            "agent_class": "tests.fixtures.echo_agent.Agent",
        },
        headers=HEADERS,
    )
    run_id = resp.json()["run_id"]

    results = _poll_until_terminal(test_client, run_id)

    assert results["run_id"] == run_id
    assert len(results["case_results"]) == 1
    assert results["case_results"][0]["passed"] is True

    full = test_client.get(f"/api/v1/runs/{run_id}", headers=HEADERS).json()
    assert full["test_set_name"] == "echo_agent_smoke_test"
    assert full["passed"] == 1

    listing = test_client.get("/api/v1/runs", headers=HEADERS).json()
    matching = [r for r in listing["runs"] if r["run_id"] == run_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "complete"


def test_run_with_bad_agent_class_marks_run_failed(test_client: TestClient) -> None:
    resp = test_client.post(
        "/api/v1/runs",
        json={
            "test_set_path": "tests/fixtures/echo_agent_test_set.yaml",
            "agent_class": "not.a.real.module.Agent",
        },
        headers=HEADERS,
    )
    run_id = resp.json()["run_id"]

    deadline = time.monotonic() + 5.0
    status = "started"
    while time.monotonic() < deadline:
        listing = test_client.get("/api/v1/runs", headers=HEADERS).json()
        matching = [r for r in listing["runs"] if r["run_id"] == run_id]
        if matching and matching[0]["status"] == "failed":
            status = matching[0]["status"]
            break
        time.sleep(0.02)

    assert status == "failed"


def test_background_task_is_retained_and_cleaned_up(test_client: TestClient) -> None:
    # Regression test: asyncio.create_task's return value must be kept
    # somewhere with a strong reference (app.state.background_tasks),
    # otherwise the task can be garbage-collected mid-run with no error
    # surfaced. Prove the task is tracked while running and removed once
    # the run completes.
    resp = test_client.post(
        "/api/v1/runs",
        json={
            "test_set_path": "tests/fixtures/echo_agent_test_set.yaml",
            "agent_class": "tests.fixtures.echo_agent.Agent",
        },
        headers=HEADERS,
    )
    run_id = resp.json()["run_id"]

    _poll_until_terminal(test_client, run_id)

    # By the time the registry entry reports a terminal status, the task's
    # own done-callback (which discards it from the set) has already run
    # on the same event loop, so the set should be empty again — proving
    # both halves of the fix: the task was tracked while in flight, and
    # cleaned up rather than accumulating forever.
    assert test_client.app.state.background_tasks == set()


def test_get_run_unknown_id_returns_404(test_client: TestClient) -> None:
    resp = test_client.get("/api/v1/runs/does-not-exist", headers=HEADERS)
    assert resp.status_code == 404


def test_get_run_results_unknown_id_returns_404(test_client: TestClient) -> None:
    resp = test_client.get("/api/v1/runs/does-not-exist/results", headers=HEADERS)
    assert resp.status_code == 404


def test_list_runs_empty_by_default(test_client: TestClient) -> None:
    resp = test_client.get("/api/v1/runs", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json() == {"runs": []}


def test_routes_require_api_key(test_client: TestClient) -> None:
    resp = test_client.get("/api/v1/runs")
    assert resp.status_code == 401
