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
 */
function ProgressBar({ completed, total }: { completed: number; total: number }) {
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
 * Live view of an in-progress run: fetches the initial `RunResult` (for
 * `total`), subscribes to `WS /ws/v1/runs/{runId}` for live events, renders
 * a progress bar + `LiveFeed`, and auto-navigates to `/runs/:runId` once a
 * terminal event (`run_completed` or `run_failed`) arrives.
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
  const [loadError, setLoadError] = useState<string | null>(null);
  const [events, setEvents] = useState<WsEvent[]>([]);

  // Fetch the initial RunResult (for `total`). Only once this succeeds do
  // we know the run exists and it's worth opening a WebSocket at all.
  useEffect(() => {
    if (!runId) {
      setLoadError("No run id in URL.");
      return;
    }

    let cancelled = false;

    getRun(runId)
      .then((run) => {
        if (cancelled) return;
        setTotal(run.total);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : String(err);
        setLoadError(message);
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  // Subscribe to live events, but only once the initial fetch above has
  // confirmed the run exists (total !== null) and didn't error.
  useEffect(() => {
    if (!runId || total === null || loadError) return;

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
  }, [runId, total, loadError, navigate]);

  const completed = events.filter((event) => event.event === "case_completed").length;

  if (loadError) {
    return (
      <div className="p-6 text-gray-900 dark:text-gray-100">
        <h1 className="text-xl font-semibold">Live Run</h1>
        <p className="mt-4 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
          Failed to load run{runId ? ` "${runId}"` : ""}: {loadError}
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 text-gray-900 dark:text-gray-100">
      <h1 className="text-xl font-semibold">Live Run</h1>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{runId}</p>

      <div className="mt-4">
        {total === null ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading run…</p>
        ) : (
          <ProgressBar completed={completed} total={total} />
        )}
      </div>

      <div className="mt-6">
        <LiveFeed events={events} />
      </div>
    </div>
  );
}

export default LiveRunPage;
