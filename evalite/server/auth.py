"""API key authentication dependency for the evalite server.

`require_api_key` is a FastAPI dependency that validates the `X-API-Key`
request header against the `EVALITE_API_KEY` environment variable. The
env var is read fresh from `os.environ` on every call (not cached at
import time) so tests can set/unset it per-test via `monkeypatch` and see
the effect immediately, and so a long-running server process picks up an
env var change without a restart (not that we recommend rotating it that
way, but nothing here prevents it).

Per the Phase 4 plan (rule 15), every REST and WebSocket endpoint must
validate this key. REST routes use this dependency directly, declared on
`routes.runs.router` (`Depends(require_api_key)`) rather than at the
FastAPI app level — see `evalite/server/app.py`'s docstring for why (in
short: `Security(APIKeyHeader(...))` doesn't resolve correctly for
WebSocket connections in the installed FastAPI version). The WebSocket
route (`evalite/server/routes/ws.py`) enforces the identical policy
against the same env var via a manual header check instead of reusing
this function directly, for that same reason.

Whether the *server process itself* refuses to start when
`EVALITE_API_KEY` is unset entirely is a separate, CLI-level concern
(`evalite serve`) — this dependency only ever checks the env var at
request time.
"""

import os

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader


# `auto_error=False` is a deliberate deviation from the plan's literal
# `APIKeyHeader(name="X-API-Key")` snippet: with the default
# `auto_error=True`, FastAPI raises its own 403 "Not authenticated"
# HTTPException when the header is absent entirely, before this
# function's body ever runs — which would make a missing header return a
# different status/body (403, generic detail) than a wrong key (401,
# "Invalid or missing API key"). The API contract requires both cases to
# return the same 401 with the same body, so `auto_error=False` is
# required to make FastAPI hand us `None` instead of short-circuiting,
# letting the check below handle "missing" and "wrong" identically.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str | None = Security(api_key_header)) -> str:
    """FastAPI dependency. Raises 401 if key doesn't match EVALITE_API_KEY env var.

    Args:
        key: the value of the `X-API-Key` request header, injected by
            FastAPI via the `APIKeyHeader` security scheme, or `None` if
            the header was not sent at all.

    Returns:
        The validated API key, on success.

    Raises:
        HTTPException: 401, if `EVALITE_API_KEY` is unset in the
            environment, or `key` does not match it.
    """
    expected = os.environ.get("EVALITE_API_KEY")
    if expected is None or key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key
