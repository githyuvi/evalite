"""REST routes for starting and querying evaluation runs.

`POST /api/v1/runs` starts a run as a background `asyncio` task and
returns immediately (202) with a `run_id`. `GET /api/v1/runs` and
`GET /api/v1/runs/{run_id}[/results]` read from an in-memory run
registry (`request.app.state.runs`) rather than delegating straight to
`storage.get_run`/`storage.list_runs`.

This is a deliberate scope choice for this phase, not a `StorageBackend`
Protocol change: `StorageBackend.save_run` always generates and returns
its own internal `run_id` (see `evalite/storage/base.py`) — it has no
way to honor a `run_id` that has already been handed to a client before
the run has even started, and changing that Protocol's signature is an
architecture change out of scope here. So `app.state.runs` is this API
server's own source of truth for `run_id` identity, status, and results.
Completed runs are still persisted via `storage.save_run` on a
best-effort basis for durability, under storage's own (different,
internal-only) id — this route's `run_id` is never storage's id, and a
storage failure never loses the in-memory result the client will see via
this API.
"""

import asyncio
import importlib
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from evalite.agent.protocol import AgentAdapter
from evalite.runner.result import RunResult
from evalite.runner.runner import Runner
from evalite.scorer.default import DefaultScorer
from evalite.server.auth import require_api_key
from evalite.server.models import RunSummary, StartRunRequest
from evalite.testcase.loader import load_test_set

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


def _load_agent_class(agent_class: str) -> AgentAdapter:
    """Instantiate an `AgentAdapter` from a dotted import path.

    Unlike `evalite.cli.load_adapter`, this raises `HTTPException(422)`
    on failure rather than calling `typer.Exit` (which terminates the
    whole process) — a request handler must fail only the one request,
    never the server process. Only dotted-path loading is supported here
    (not the CLI's `.py`-file convenience), matching `StartRunRequest
    .agent_class`'s field name and docstring.
    """
    module_path, _, class_name = agent_class.rpartition(".")
    if not module_path:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid agent_class '{agent_class}': expected a dotted "
                "import path, e.g. mypackage.MyAgent"
            ),
        )
    try:
        module = importlib.import_module(module_path)
        agent_cls = getattr(module, class_name)
        instance = agent_cls()
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Failed to load agent_class '{agent_class}': {e}"
        )

    if not isinstance(instance, AgentAdapter):
        raise HTTPException(
            status_code=422,
            detail=(
                f"agent_class '{agent_class}' does not implement the AgentAdapter "
                "protocol — missing async send(messages) method"
            ),
        )
    return instance


async def _execute_run(app_state: Any, run_id: str, body: StartRunRequest) -> None:
    """Background task: run the test set, update the registry, persist to storage.

    Never raises — any failure (bad test set, bad agent, adapter error)
    is caught, recorded on the registry entry as `status="failed"`, and
    published as a `run_failed` event, so a background-task exception
    never surfaces as an unhandled `asyncio` task exception.
    """
    entry = app_state.runs[run_id]
    bus = app_state.progress_bus

    async def _progress_callback(event: dict) -> None:
        await bus.publish(run_id, event)

    try:
        test_set = load_test_set(body.test_set_path)
        adapter = _load_agent_class(body.agent_class)
        entry["test_set_name"] = test_set.name
        entry["status"] = "running"

        runner = Runner(
            adapter=adapter,
            scorer=DefaultScorer(),
            max_workers=body.max_workers,
            progress_callback=_progress_callback,
        )
        result = await runner.run(test_set)

        entry["status"] = "complete"
        entry["result"] = result

        try:
            await app_state.storage.save_run(result)
        except Exception:
            # Best-effort persistence — the in-memory registry entry
            # above is already this API's source of truth for the
            # client-visible run_id, so a storage failure here must not
            # lose the result the client is about to see.
            pass

        await bus.publish(
            run_id,
            {
                "event": "run_completed",
                "run_id": run_id,
                "passed": result.passed,
                "failed": result.failed,
                "pass_rate": result.pass_rate,
            },
        )
    except HTTPException as e:
        entry["status"] = "failed"
        entry["error"] = str(e.detail)
        await bus.publish(run_id, {"event": "run_failed", "run_id": run_id, "error": str(e.detail)})
    except Exception as e:
        entry["status"] = "failed"
        entry["error"] = str(e)
        await bus.publish(run_id, {"event": "run_failed", "run_id": run_id, "error": str(e)})


@router.post("/runs", status_code=202)
async def start_run(body: StartRunRequest, request: Request) -> dict:
    """Validate the request, register a run_id, and start the run in the background."""
    if not os.path.exists(body.test_set_path):
        raise HTTPException(
            status_code=422, detail=f"test_set_path not found: {body.test_set_path}"
        )

    run_id = str(uuid.uuid4())
    request.app.state.runs[run_id] = {
        "run_id": run_id,
        "test_set_name": None,
        "status": "started",
        "timestamp": datetime.now(UTC).isoformat(),
        "result": None,
        "error": None,
    }

    # asyncio only keeps a *weak* reference to a task created via
    # create_task — a task with no other strong reference can be
    # garbage-collected mid-run with no error surfaced, silently
    # abandoning the run (registry stuck at "running", WebSocket
    # subscriber hangs forever waiting for a terminal event that never
    # comes). Retaining it in app.state.background_tasks until it
    # finishes prevents that.
    background_tasks = request.app.state.background_tasks
    task = asyncio.create_task(_execute_run(request.app.state, run_id, body))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

    return {"run_id": run_id, "status": "started"}


class RunListResponse(BaseModel):
    """Response body of `GET /api/v1/runs`: `{"runs": [RunSummary, ...]}`."""

    runs: list[RunSummary]


@router.get("/runs", response_model=RunListResponse)
async def list_runs(request: Request, limit: int = 20, offset: int = 0) -> RunListResponse:
    """List runs known to this server process, most recent first."""
    entries = sorted(
        request.app.state.runs.values(), key=lambda e: e["timestamp"], reverse=True
    )
    page = entries[offset : offset + limit]
    summaries = [
        RunSummary(
            run_id=e["run_id"],
            test_set_name=e["result"].test_set_name if e["result"] else e["test_set_name"],
            passed=e["result"].passed if e["result"] else 0,
            failed=e["result"].failed if e["result"] else 0,
            timestamp=e["timestamp"],
            status=e["status"],
        )
        for e in page
    ]
    return RunListResponse(runs=summaries)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> RunResult:
    """Fetch the full `RunResult` for a completed run."""
    entry = request.app.state.runs.get(run_id)
    if entry is None or entry["result"] is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return entry["result"]


@router.get("/runs/{run_id}/results")
async def get_run_results(run_id: str, request: Request) -> dict:
    """Fetch just the case-level results for a completed run."""
    entry = request.app.state.runs.get(run_id)
    if entry is None or entry["result"] is None:
        raise HTTPException(status_code=404, detail="Run not found")
    result: RunResult = entry["result"]
    return {"run_id": run_id, "case_results": [cr.model_dump() for cr in result.case_results]}
