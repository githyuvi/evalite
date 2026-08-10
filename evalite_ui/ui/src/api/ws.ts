/**
 * WebSocket client for `WS /ws/v1/runs/{run_id}` (`evalite/server/routes/ws.py`).
 *
 * IMPORTANT — required backend change (flagging for the backend owner):
 * the browser `WebSocket` constructor cannot set arbitrary HTTP headers
 * (unlike `fetch`), so this client cannot literally send `X-API-Key` as a
 * header the way `src/api/client.ts` does for REST calls. Instead it
 * appends the key as a query parameter: `?api_key=<key>`. Today,
 * `evalite/server/routes/ws.py` lines 39-43 only reads the key from the
 * header (`websocket.headers.get("x-api-key")`):
 *
 *     expected_key = os.environ.get("EVALITE_API_KEY")
 *     sent_key = websocket.headers.get("x-api-key")
 *     if expected_key is None or sent_key != expected_key:
 *         await websocket.close(code=UNAUTHORIZED_CLOSE_CODE, reason="Invalid or missing API key")
 *         return
 *
 * For this client to actually authenticate end-to-end, that check needs
 * to also accept the key via `websocket.query_params.get("api_key")`
 * (e.g. `sent_key = websocket.headers.get("x-api-key") or
 * websocket.query_params.get("api_key")`), falling back to the header if
 * present. Out of scope for this file (backend-only, Python) — route to
 * whoever owns `evalite/server/routes/ws.py` next.
 */

import type { WsEvent } from "./types";

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

const API_KEY: string | undefined = import.meta.env.VITE_API_KEY as
  | string
  | undefined;

/**
 * Resolve `VITE_API_BASE_URL` (absolute, relative, or unset — same rules
 * `client.ts` applies to `fetch`) against the current page location to
 * get an absolute `ws(s)://host` origin.
 */
function resolveWsOrigin(): string {
  const httpBase = new URL(API_BASE_URL || "/", window.location.href);
  const wsProtocol = httpBase.protocol === "https:" ? "wss:" : "ws:";
  return `${wsProtocol}//${httpBase.host}`;
}

/** Build the `ws(s)://.../ws/v1/runs/{runId}?api_key=...` URL for a given run. */
function buildWsUrl(runId: string): string {
  const path = `/ws/v1/runs/${encodeURIComponent(runId)}`;
  const wsUrl = new URL(path, resolveWsOrigin());

  if (API_KEY) {
    wsUrl.searchParams.set("api_key", API_KEY);
  }

  return wsUrl.toString();
}

/**
 * Open a live progress WebSocket for `runId`.
 *
 * Calls `onEvent` for each parsed `WsEvent` message and `onClose` when
 * the connection closes (whether cleanly after a terminal event, due to
 * an error, or because the caller invoked the returned cleanup function).
 *
 * Returns a cleanup function that closes the socket. Safe to call
 * multiple times (idempotent) and safe to call before the socket has
 * finished connecting.
 */
export function createRunWebSocket(
  runId: string,
  onEvent: (event: WsEvent) => void,
  onClose: () => void,
): () => void {
  const socket = new WebSocket(buildWsUrl(runId));
  let closed = false;

  socket.addEventListener("message", (message: MessageEvent) => {
    let parsed: WsEvent;
    try {
      parsed = JSON.parse(message.data as string) as WsEvent;
    } catch (err) {
      console.error("evalite ws: failed to parse message as JSON", err, message.data);
      return;
    }
    onEvent(parsed);
  });

  socket.addEventListener("close", () => {
    closed = true;
    onClose();
  });

  socket.addEventListener("error", (err) => {
    // The native "close" event always follows "error" for a WebSocket,
    // so onClose is still invoked from the close listener above — this
    // is purely for diagnostics.
    console.error("evalite ws: connection error", err);
  });

  return () => {
    if (closed) return;
    // CONNECTING or OPEN: close() is safe to call in either state, and a
    // no-op (per the WebSocket spec) if already CLOSING/CLOSED.
    socket.close();
    closed = true;
  };
}
