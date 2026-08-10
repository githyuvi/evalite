import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getRun } from "../api/client";
import { createRunWebSocket } from "../api/ws";
import type { WsEvent } from "../api/types";
import LiveFeed from "../components/LiveFeed";

/**
 * Neutral/blue progress bar tracking `completed` out of `total` cases.
 *
 * Deliberately not `ScoreBar` — that component color-codes by pass/fail
 * quality (red/yellow/green), which doesn't apply to "how far along is
 * this run" progress. This is always rendered in a single neutral blue.
 *
 * `total === null` means the case-set size is unknown (the best-effort
 * initial `getRun` fetch didn't resolve it — see `LiveRunPage` above).
 * In that case there's no percentage to compute, so this renders an
 * indeterminate state instead: just "{completed} cases completed" text
 * over a plain pulsing bar, rather than dividing by an unknown total.
 */
function ProgressBar({
  completed,
  total,
}: {
  completed: number;
  total: number | null;
}) {
  if (total === null) {
    return (
      <div>
        <div className="mb-1 text-sm text-gray-600 dark:text-gray-400">
          {completed} cases completed
        </div>
        <div
          className="h-3 w-full animate-pulse overflow-hidden rounded bg-gray-200 dark:bg-gray-700"
          role="progressbar"
          aria-valuetext={`${completed} cases completed`}
        />
      </div>
    );
  }

  const clampedTotal = Math.max(0, total);
  const clampedCompleted = clampedTotal > 0 ? Math.min(completed, clampedTotal) : 0;
  const widthPercent = clampedTotal > 0 ? (clampedCompleted / clampedTotal) * 100 : 0;

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm text-gray-600 dark:text-gray-400">
        <span>
          {clampedCompleted} / {clampedTotal} cases
        </span>
        <span>{Math.round(widthPercent)}%</span>
      </div>
      <div
        className="h-3 w-full overflow-hidden rounded bg-gray-200 dark:bg-gray-700"
        role="progressbar"
        aria-valuenow={Math.round(widthPercent)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full bg-blue-500 transition-[width] duration-300"
          style={{ width: `${widthPercent}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Live view of an in-progress run: subscribes to `WS /ws/v1/runs/{runId}`
 * for live events, renders a progress bar + `LiveFeed`, and auto-navigates
 * to `/runs/:runId` once a terminal event (`run_completed` or
 * `run_failed`) arrives.
 *
 * `total` (case-set size, for the progress bar's percentage) is fetched
 * best-effort via `getRun(runId)` on mount — but that's *not* a
 * precondition for opening the WebSocket. `GET /api/v1/runs/{id}` 404s
 * "Run not found" for the entire `started`/`running` lifetime of a run
 * (it only succeeds once the run has already finished), so gating the
 * WebSocket on it succeeding meant this page — whose whole purpose is
 * showing a run that's still live — could never actually show one. So:
 * the WebSocket always opens regardless of whether `getRun` succeeds,
 * fails, or is still in flight; a failed/never-resolving `getRun` just
 * leaves `total` at `null` ("unknown"), and `ProgressBar` renders an
 * indeterminate state for that case instead of computing a percentage.
 *
 * The one case where `getRun` *does* succeed here is a run that had
 * already finished by the time this page loaded (e.g. a stale link, or a
 * fast run) — worth keeping fast for. In that case we still open the
 * WebSocket too (simpler than conditionally skipping it): it will just
 * immediately hit a terminal event and navigate away per the existing
 * terminal-event logic below, so there's no meaningful downside to not
 * special-casing it.
 *
 * Navigation-on-failure choice: we navigate away on `run_failed` too, not
 * just `run_completed`. Once either terminal event fires the run is done —
 * the backend WS route closes the connection right after — so there is
 * nothing left for this live page to show. `RunDetailPage` is expected to
 * render the failure state (e.g. via `RunSummary.status === "failed"`)
 * once it's implemented, so redirecting there is consistent with treating
 * "run finished" (success or failure) as this page's exit condition.
 */
function LiveRunPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const [total, setTotal] = useState<number | null>(null);
  const [events, setEvents] = useState<WsEvent[]>([]);

  // Best-effort fetch of the initial RunResult, purely to learn `total`
  // early if possible. Not a precondition for anything else on this page
  // — see the component doc comment above. A failure (expected for a
  // genuinely live run, which 404s until it finishes) just leaves `total`
  // at `null`; it is not surfaced as a page-level error.
  useEffect(() => {
    if (!runId) return;

    let cancelled = false;

    getRun(runId)
      .then((run) => {
        if (cancelled) return;
        setTotal(run.total);
      })
      .catch(() => {
        // Expected for a run that's still `started`/`running` — total
        // stays unknown and ProgressBar renders its indeterminate state.
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  // Subscribe to live events. Opens unconditionally on mount — does not
  // wait on (or depend on the outcome of) the best-effort getRun above.
  useEffect(() => {
    if (!runId) return;

    const cleanup = createRunWebSocket(
      runId,
      (event: WsEvent) => {
        setEvents((prev) => [...prev, event]);
        if (event.event === "run_completed" || event.event === "run_failed") {
          navigate(`/runs/${encodeURIComponent(runId)}`);
        }
      },
      () => {
        // Connection closed — nothing extra to do; navigation (if any) is
        // already handled by the terminal-event branch above.
      },
    );

    return cleanup;
  }, [runId, navigate]);

  const completed = events.filter((event) => event.event === "case_completed").length;

  if (!runId) {
    return (
      <div className="p-6 text-gray-900 dark:text-gray-100">
        <h1 className="text-xl font-semibold">Live Run</h1>
        <p className="mt-4 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
          No run id in URL.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 text-gray-900 dark:text-gray-100">
      <h1 className="text-xl font-semibold">Live Run</h1>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{runId}</p>

      <div className="mt-4">
        <ProgressBar completed={completed} total={total} />
      </div>

      <div className="mt-6">
        <LiveFeed events={events} />
      </div>
    </div>
  );
}

export default LiveRunPage;
