/**
 * TypeScript types for the evalite REST/WebSocket API.
 *
 * Mirrors the Pydantic models in the Python backend:
 * - `Score`, `CaseResult`, `RunResult` — evalite/runner/result.py
 * - `RunSummary`, `StartRunRequest` — evalite/server/models.py
 * - `{run_id, status}` start-run response, `RunListResponse`,
 *   `{run_id, case_results}` results response — evalite/server/routes/runs.py
 * - WebSocket event shapes — evalite/server/progress.py
 *
 * Field names are kept snake_case to match the wire format exactly (no
 * client-side renaming), since the backend returns Pydantic
 * `model_dump()`/FastAPI JSON as-is.
 */

/** The outcome of scoring a single agent response against a case. */
export interface Score {
  /** Whether the response satisfies the scorer's pass/fail bar. */
  passed: boolean;
  /** A normalized score in [0.0, 1.0], for aggregation across cases. */
  value: number;
  /** Optional human-readable explanation (e.g. from an LLM judge). */
  reasoning: string;
}

/** The outcome of running a single test case (one iteration) through the agent. */
export interface CaseResult {
  /** Identifier of the test case this result belongs to. */
  case_id: string;
  /** Which repetition of the case this is. 0-indexed. */
  iteration: number;
  /** The input given to the agent for this case. */
  input: string;
  /** The agent's actual response/output. */
  actual: string;
  /** The `Score` produced by the scorer for this case. */
  score: Score;
  /** Whether the runner considers this case a pass (set independently of `score.passed`). */
  passed: boolean;
  /** How long this case took to run, in milliseconds. */
  duration_ms: number;
}

/** The aggregate outcome of running an entire test set. */
export interface RunResult {
  /** Name of the test set that was run. */
  test_set_name: string;
  /** Total number of cases run. */
  total: number;
  /** Number of cases that passed. */
  passed: number;
  /** Number of cases that failed. */
  failed: number;
  /** passed / total, in [0.0, 1.0]. */
  pass_rate: number;
  /** The individual `CaseResult` for each case run. */
  case_results: CaseResult[];
  /** Total duration of the run, in milliseconds. */
  duration_ms: number;
  /** Id assigned by a `StorageBackend` when this run was persisted, or `null` if not persisted. */
  run_id: string | null;
}

/** Lifecycle state of a run, as reported by `GET /api/v1/runs`. */
export type RunStatus = "started" | "running" | "complete" | "failed";

/** Lightweight per-run summary, as returned by `GET /api/v1/runs`. */
export interface RunSummary {
  /** UUID string assigned to the run. */
  run_id: string;
  /** Name of the test set that was run, or `null` before it has loaded. */
  test_set_name: string | null;
  /** Number of cases that passed. */
  passed: number;
  /** Number of cases that failed. */
  failed: number;
  /** ISO-8601 timestamp of when the run was recorded. */
  timestamp: string;
  /** Lifecycle state of the run. */
  status: RunStatus;
}

/** Body of `POST /api/v1/runs`. */
export interface StartRunRequest {
  /** Filesystem path to a YAML test set file. */
  test_set_path: string;
  /** Dotted import path to an `AgentAdapter` class. */
  agent_class: string;
  /** Max concurrent agent calls for the run. Defaults to 10 server-side. */
  max_workers?: number;
  /** Optional free-form tags to filter/annotate the run. */
  tags?: string[];
}

/** Response of `POST /api/v1/runs` (202 Accepted). */
export interface StartRunResponse {
  /** UUID string assigned to the newly started run. */
  run_id: string;
  /** Always "started" at creation time. */
  status: "started";
}

/** Response of `GET /api/v1/runs`. */
export interface RunListResponse {
  runs: RunSummary[];
}

/** Response of `GET /api/v1/runs/{run_id}/results`. */
export interface RunResultsResponse {
  run_id: string;
  case_results: CaseResult[];
}

// --- WebSocket events (`WS /ws/v1/runs/{run_id}`) ---
// Discriminated union on the `event` field. See evalite/server/progress.py
// for the authoritative shape contract.

export interface CaseStartedEvent {
  event: "case_started";
  case_id: string;
  iteration: number;
}

export interface CaseCompletedEvent {
  event: "case_completed";
  case_id: string;
  iteration: number;
  passed: boolean;
  score: number;
}

export interface RunCompletedEvent {
  event: "run_completed";
  run_id: string;
  passed: number;
  failed: number;
  pass_rate: number;
}

export interface RunFailedEvent {
  event: "run_failed";
  run_id: string;
  error: string;
}

/** Discriminated union of all events sent over `WS /ws/v1/runs/{run_id}`. */
export type WsEvent =
  | CaseStartedEvent
  | CaseCompletedEvent
  | RunCompletedEvent
  | RunFailedEvent;
