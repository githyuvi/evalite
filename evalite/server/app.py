"""FastAPI app factory for the evalite API server.

`create_app` wires up the shared plumbing (API key auth, app-scoped
storage/progress-bus state) that every route depends on. FastAPI itself
is only ever imported from within `evalite/server/` — nothing reachable
from a bare `import evalite` touches this package, so the core install
(no `[server]` extra) never pulls in FastAPI. See `evalite/cli.py` for
the same lazy-import principle applied to optional storage deps.
"""

from fastapi import Depends, FastAPI

from evalite.server.auth import require_api_key
from evalite.server.progress import ProgressBus
from evalite.storage.base import StorageBackend


def create_app(storage: StorageBackend) -> FastAPI:
    """Return a configured FastAPI app. Called by `evalite serve`.

    Args:
        storage: the `StorageBackend` route handlers will read/write runs
            through, exposed to them via `request.app.state.storage`.

    Returns:
        A `FastAPI` app with the API key dependency applied globally
        (`Depends(require_api_key)` at the app level, so it gates every
        route registered on this app — including ones added by later
        tasks — without each route needing to redeclare it) and
        `app.state.storage` / `app.state.progress_bus` populated for
        route handlers to use.
    """
    app = FastAPI(dependencies=[Depends(require_api_key)])
    app.state.storage = storage
    app.state.progress_bus = ProgressBus()

    # EXTENSION POINT for later tasks: routers are registered here once
    # they exist (evalite/server/routes/runs.py, evalite/server/routes/ws.py) —
    # not yet built as of this task. A later task will add:
    #     from evalite.server.routes import runs, ws
    #     app.include_router(runs.router)
    #     app.include_router(ws.router)

    return app
