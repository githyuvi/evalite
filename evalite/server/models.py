"""Pydantic request/response schemas for the evalite API server.

These are wire-format schemas (not ORM models) per the Phase 4 API
contract (`docs/plans/phase-4-api-server.md`). Later Wave 2 tasks (REST
routes) use these directly; kept intentionally minimal here since the
routes themselves don't exist yet in this task.
"""

from typing import Literal

from pydantic import BaseModel


class StartRunRequest(BaseModel):
    """Body of `POST /api/v1/runs`.

    test_set_path: filesystem path to a YAML test set file.
    agent_class: dotted import path to an `AgentAdapter` class.
    max_workers: max concurrent agent calls for the run.
    tags: optional free-form tags to filter/annotate the run.
    """

    test_set_path: str
    agent_class: str
    max_workers: int = 10
    tags: list[str] = []


class RunSummary(BaseModel):
    """Lightweight per-run summary, as returned by `GET /api/v1/runs`.

    run_id: UUID string assigned to the run.
    test_set_name: name of the test set that was run.
    passed: number of cases that passed.
    failed: number of cases that failed.
    timestamp: ISO-8601 timestamp of when the run was recorded.
    status: lifecycle state of the run.
    """

    run_id: str
    test_set_name: str
    passed: int
    failed: int
    timestamp: str
    status: Literal["started", "running", "complete", "failed"]
