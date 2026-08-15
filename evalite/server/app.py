"""FastAPI app factory for the evalite API server.

`create_app` wires up the shared plumbing (API key auth, app-scoped
storage/progress-bus/run-registry state) that every route depends on.
FastAPI itself is only ever imported from within `evalite/server/` —
nothing reachable from a bare `import evalite` touches this package, so
the core install (no `[server]` extra) never pulls in FastAPI. See
`evalite/cli.py` for the same lazy-import principle applied to optional
storage deps.
"""

import logging

from fastapi import FastAPI

from evalite.server.progress import ProgressBus
from evalite.server.routes import runs, ws
from evalite.storage.base import StorageBackend

logger = logging.getLogger(__name__)


def create_app(storage: StorageBackend) -> FastAPI:
    """Return a configured FastAPI app. Called by `evalite serve`.

    Args:
        storage: the `StorageBackend` route handlers use for best-effort
            durability once a run completes, exposed to them via
            `request.app.state.storage`. Note: `request.app.state.runs`
            (an in-memory registry), not `storage`, is this API's actual
            source of truth for `run_id` identity/status/results — see
            `evalite/server/routes/runs.py`'s module docstring for why.

    Returns:
        A `FastAPI` app with `app.state.storage` / `app.state.progress_bus`
        / `app.state.runs` populated for route handlers to use, and the
        REST + WebSocket routers registered.

        API key auth (rule 15) is applied per-router rather than at the
        app level: `routes.runs.router` declares
        `Depends(require_api_key)` itself (standard FastAPI `Security`,
        which only supports the HTTP `Request` shape). The WebSocket
        route in `routes.ws` cannot reuse that same dependency — in this
        FastAPI version, `Security(APIKeyHeader(...))` raises
        `TypeError: APIKeyHeader.__call__() missing 1 required
        positional argument: 'request'` when invoked for a WebSocket
        connection instead of an HTTP request, since the scheme's
        `__call__` is typed against `Request`, not `WebSocket`. So
        `routes.ws` does its own manual `X-API-Key` header check before
        accepting the connection (see that module for details) — both
        paths validate against the same `EVALITE_API_KEY` env var.
    """
    app = FastAPI()
    app.state.storage = storage
    app.state.progress_bus = ProgressBus()
    app.state.runs = {}
    # Retains a strong reference to every in-flight run's background task —
    # see routes/runs.py's start_run for why (asyncio only holds a *weak*
    # reference to a task via create_task, so a task with no other
    # reference can be garbage-collected mid-run with no error surfaced).
    app.state.background_tasks = set()

    app.include_router(runs.router)
    app.include_router(ws.router)

    return app
