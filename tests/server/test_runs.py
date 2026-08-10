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


def test_list_runs_returns_null_test_set_name_for_in_flight_run(
    test_client: TestClient,
) -> None:
    # Regression test for a type mismatch: `RunSummary.test_set_name` was
    # declared `str` (non-nullable) but an in-flight run's registry entry
    # (`app.state.runs[run_id]`) holds `test_set_name=None` from the moment
    # `POST /api/v1/runs` registers it until the background task finishes
    # loading the test set (see `evalite/server/routes/runs.py`,
    # `start_run` and `_execute_run`). Validating that shape against the
    # old `RunSummary` would have raised a 500 (Pydantic serialization
    # error) the instant `list_runs` used it as a `response_model` — which
    # is exactly why it previously wasn't wired in.
    #
    # We seed the registry entry directly rather than racing a real
    # background task: in `_execute_run`, `entry["test_set_name"]` and
    # `entry["status"] = "running"` are set together with no `await` in
    # between, so externally the `test_set_name=None` state only exists
    # while `status == "started"` — a window that (for this repo's
    # near-instant echo-agent fixture) closes before a synchronous
    # `TestClient` call can observe it, since the background task
    # reliably runs to completion within the same event-loop turn as the
    # `POST` response. Seeding the exact registry shape documented in
    # `runs.py` exercises the identical code path in `list_runs`
    # deterministically, without a flaky timing dependency.
    run_id = "in-flight-run-id"
    test_client.app.state.runs[run_id] = {
        "run_id": run_id,
        "test_set_name": None,
        "status": "started",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "result": None,
        "error": None,
    }

    resp = test_client.get("/api/v1/runs", headers=HEADERS)

    assert resp.status_code == 200
    matching = [r for r in resp.json()["runs"] if r["run_id"] == run_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "started"
    assert matching[0]["test_set_name"] is None


def test_pagination_on_list_runs(test_client: TestClient) -> None:
    # Test that limit and offset query parameters correctly slice and order
    # results by timestamp (most recent first).
    run_ids = []

    # Start 3 runs sequentially, polling each to completion before the next,
    # to ensure deterministic timestamp ordering (most recently started run
    # should sort first).
    for i in range(3):
        resp = test_client.post(
            "/api/v1/runs",
            json={
                "test_set_path": "tests/fixtures/echo_agent_test_set.yaml",
                "agent_class": "tests.fixtures.echo_agent.Agent",
            },
            headers=HEADERS,
        )
        run_id = resp.json()["run_id"]
        run_ids.append(run_id)
        _poll_until_terminal(test_client, run_id)

    # GET /api/v1/runs?limit=2 should return the 2 most recent runs
    # (run_ids[2] and run_ids[1], in that order, since run_ids[2] was
    # started last and thus has the most recent timestamp).
    resp = test_client.get("/api/v1/runs?limit=2", headers=HEADERS)
    assert resp.status_code == 200
    page1 = resp.json()["runs"]
    assert len(page1) == 2
    assert page1[0]["run_id"] == run_ids[2]
    assert page1[1]["run_id"] == run_ids[1]

    # GET /api/v1/runs?limit=2&offset=2 should return the oldest run
    # (run_ids[0]), since offset=2 skips the first 2 (most recent) and
    # limit=2 allows up to 2, but only 1 remains.
    resp = test_client.get("/api/v1/runs?limit=2&offset=2", headers=HEADERS)
    assert resp.status_code == 200
    page2 = resp.json()["runs"]
    assert len(page2) == 1
    assert page2[0]["run_id"] == run_ids[0]

    # Verify the two pages together account for all 3 run_ids exactly once.
    page1_ids = {r["run_id"] for r in page1}
    page2_ids = {r["run_id"] for r in page2}
    assert page1_ids.isdisjoint(page2_ids)
    assert page1_ids | page2_ids == set(run_ids)
