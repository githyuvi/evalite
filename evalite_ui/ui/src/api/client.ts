/**
 * Typed REST client for the evalite API server (`evalite/server/`).
 *
 * Base URL: same-origin relative paths (`/api/v1/...`) are used unless
 * `VITE_API_BASE_URL` is set at build time, in which case requests go to
 * that origin instead. Same-origin is the default because evalite-ui's
 * built assets are served by the same FastAPI process at `/` in the
 * primary deployment (`evalite serve` style), so relative paths just
 * work with no CORS configuration needed. `VITE_API_BASE_URL` exists as
 * an escape hatch for local dev against a separately-running API server
 * (e.g. `vite dev` on :5173 talking to uvicorn on :8000) or any future
 * deployment where the UI is hosted separately from the API.
 *
 * Auth: every request carries an `X-API-Key` header read from
 * `VITE_API_KEY` (a build-time env var, per Vite convention — see
 * https://vite.dev/guide/env-and-mode). This means the key is baked into
 * the built JS bundle; that's an accepted tradeoff of this single-key
 * auth scheme (see `evalite/server/auth.py`) and matches how the rest of
 * the server is deployed (trusted network / reverse proxy in front),
 * not something this client layer can fix.
 */

import type {
  CaseResult,
  RunListResponse,
  RunResult,
  RunResultsResponse,
  StartRunRequest,
  StartRunResponse,
} from "./types";

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

const API_KEY: string | undefined = import.meta.env.VITE_API_KEY as
  | string
  | undefined;

function buildHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  return headers;
}

/**
 * Perform a `fetch` against the API and return the parsed JSON body.
 *
 * Throws a descriptive `Error` (including the HTTP status and, when
 * available, the response body) on any non-2xx response, rather than
 * returning a malformed/partial object to the caller.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: buildHeaders(init?.headers as Record<string, string> | undefined),
  });

  if (!response.ok) {
    let bodyText = "";
    try {
      bodyText = await response.text();
    } catch {
      // Ignore — body may be unreadable (e.g. already consumed, network cut).
    }
    const suffix = bodyText ? `: ${bodyText}` : "";
    throw new Error(
      `evalite API request failed: ${init?.method ?? "GET"} ${url} -> ${response.status} ${response.statusText}${suffix}`,
    );
  }

  // 202/204 responses may have no body; guard against empty-string JSON parse errors.
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/** `POST /api/v1/runs` — start a new evaluation run. Returns 202 with `{run_id, status}`. */
export async function startRun(
  body: StartRunRequest,
): Promise<StartRunResponse> {
  return request<StartRunResponse>("/api/v1/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** `GET /api/v1/runs?limit=&offset=` — list known runs, most recent first. */
export async function listRuns(
  options: { limit?: number; offset?: number } = {},
): Promise<RunListResponse> {
  const params = new URLSearchParams();
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.offset !== undefined) params.set("offset", String(options.offset));
  const query = params.toString();
  return request<RunListResponse>(
    `/api/v1/runs${query ? `?${query}` : ""}`,
  );
}

/** `GET /api/v1/runs/{run_id}` — fetch the full `RunResult` for a run. Throws on 404. */
export async function getRun(runId: string): Promise<RunResult> {
  return request<RunResult>(`/api/v1/runs/${encodeURIComponent(runId)}`);
}

/** `GET /api/v1/runs/{run_id}/results` — fetch just the case-level results for a run. Throws on 404. */
export async function getRunResults(
  runId: string,
): Promise<RunResultsResponse> {
  return request<RunResultsResponse>(
    `/api/v1/runs/${encodeURIComponent(runId)}/results`,
  );
}

export type { CaseResult, RunResult };
