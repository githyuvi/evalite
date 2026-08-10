"""WebSocket route streaming live run progress.

`WS /ws/v1/runs/{run_id}` subscribes to `app.state.progress_bus` for the
given `run_id` and forwards each event to the connected client as JSON,
closing the connection once a terminal event (`run_completed` or
`run_failed`) has been sent. Progress events are produced by
`Runner`/`ConversationRunner`'s `progress_callback` (case-by-case) and by
`routes/runs.py`'s background task (`run_completed`/`run_failed`) — see
`evalite/server/progress.py` for the full event-shape contract.

Auth is checked manually here rather than via `Depends(require_api_key)`
(the mechanism `routes/runs.py`'s REST routes use): in this FastAPI
version, `Security(APIKeyHeader(...))` raises `TypeError:
APIKeyHeader.__call__() missing 1 required positional argument:
'request'` when FastAPI resolves it for a WebSocket connection instead
of an HTTP request — the scheme's `__call__` is typed against `Request`,
not `WebSocket`. Reading `websocket.headers` directly and comparing
against `EVALITE_API_KEY` avoids that entirely and validates against the
exact same env var `require_api_key` uses.

If a client connects to a `run_id` that was never started via
`POST /api/v1/runs`, the connection is closed immediately with code 4404
rather than left open waiting indefinitely for events that will never
arrive.
"""

import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

RUN_NOT_FOUND_CLOSE_CODE = 4404
UNAUTHORIZED_CLOSE_CODE = 4401


@router.websocket("/ws/v1/runs/{run_id}")
async def stream_run_progress(websocket: WebSocket, run_id: str) -> None:
    expected_key = os.environ.get("EVALITE_API_KEY")
    sent_key = websocket.headers.get("x-api-key")
    if expected_key is None or sent_key != expected_key:
        await websocket.close(code=UNAUTHORIZED_CLOSE_CODE, reason="Invalid or missing API key")
        return

    await websocket.accept()

    if run_id not in websocket.app.state.runs:
        await websocket.close(code=RUN_NOT_FOUND_CLOSE_CODE, reason="Run not found")
        return

    bus = websocket.app.state.progress_bus

    try:
        async for event in bus.subscribe(run_id):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        # Client disconnected early — nothing further to send.
        return

    await websocket.close()
