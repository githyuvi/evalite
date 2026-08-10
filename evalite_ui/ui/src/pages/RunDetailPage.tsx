import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { getRun } from "../api/client";
import type { CaseResult, RunResult } from "../api/types";
import CaseResultRow from "../components/CaseResultRow";

/**
 * Formats a millisecond duration as e.g. "123ms" or "1.2s".
 *
 * Duplicated from `CaseResultRow`'s local `formatDuration` (not exported
 * from that module) to keep the same formatting convention for the
 * run-level `duration_ms` header stat.
 */
function formatDuration(durationMs: number): string {
  if (durationMs < 1000) return `${Math.round(durationMs)}ms`;
  return `${(durationMs / 1000).toFixed(1)}s`;
}

type PassFilter = "all" | "passed" | "failed";

/**
 * Detail view of a single run: fetches the full `RunResult` and renders a
 * header summary plus a filterable table of `CaseResult`s.
 *
 * API contract notes (see this file's task output for the full list):
 * - `RunResult` has no `status` field and no whole-run error-message
 *   field, so there is no "View live" affordance here and no dedicated
 *   whole-run-failure banner beyond the fetch-error state below. In the
 *   current backend (`evalite/server/routes/runs.py`), `GET
 *   /api/v1/runs/{run_id}` 404s until the run finishes *successfully*
 *   (a failed run never populates `entry["result"]`), so a fully-failed
 *   run is expected to surface as this page's fetch-error state, not as
 *   a successfully-fetched `RunResult`.
 * - `RunResult`/`CaseResult` carry no tag data, so there is no
 *   filter-by-tag control here (see output notes).
 */
function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();

  const [run, setRun] = useState<RunResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [passFilter, setPassFilter] = useState<PassFilter>("all");

  useEffect(() => {
    if (!runId) {
      setError("No run id in URL.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    getRun(runId)
      .then((result) => {
        if (cancelled) return;
        setRun(result);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  const filteredCaseResults = useMemo<CaseResult[]>(() => {
    if (!run) return [];
    if (passFilter === "all") return run.case_results;
    const wantPassed = passFilter === "passed";
    return run.case_results.filter((c) => c.passed === wantPassed);
  }, [run, passFilter]);

  if (loading) {
    return (
      <div className="p-6 text-gray-900 dark:text-gray-100">
        <h1 className="text-xl font-semibold">Run Detail</h1>
        <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
          Loading run…
        </p>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="p-6 text-gray-900 dark:text-gray-100">
        <h1 className="text-xl font-semibold">Run Detail</h1>
        <p className="mt-4 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
          Failed to load run{runId ? ` "${runId}"` : ""}: {error ?? "Unknown error"}
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 text-gray-900 dark:text-gray-100">
      <h1 className="text-xl font-semibold">{run.test_set_name}</h1>
      <p className="mt-1 font-mono text-sm text-gray-500 dark:text-gray-400">
        {runId}
      </p>

      <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded border border-gray-200 p-3 dark:border-gray-700">
          <dt className="text-xs text-gray-500 dark:text-gray-400">Pass Rate</dt>
          <dd className="text-lg font-semibold">
            {Math.round(run.pass_rate * 100)}%
          </dd>
        </div>
        <div className="rounded border border-gray-200 p-3 dark:border-gray-700">
          <dt className="text-xs text-gray-500 dark:text-gray-400">Passed</dt>
          <dd className="text-lg font-semibold">{run.passed}</dd>
        </div>
        <div className="rounded border border-gray-200 p-3 dark:border-gray-700">
          <dt className="text-xs text-gray-500 dark:text-gray-400">Failed</dt>
          <dd className="text-lg font-semibold">{run.failed}</dd>
        </div>
        <div className="rounded border border-gray-200 p-3 dark:border-gray-700">
          <dt className="text-xs text-gray-500 dark:text-gray-400">Duration</dt>
          <dd className="text-lg font-semibold">
            {formatDuration(run.duration_ms)}
          </dd>
        </div>
      </dl>

      <div className="mt-6 flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">
          Case Results ({filteredCaseResults.length} of {run.case_results.length})
        </h2>

        <label className="flex items-center gap-2 text-sm">
          <span className="text-gray-500 dark:text-gray-400">Status</span>
          <select
            value={passFilter}
            onChange={(e) => setPassFilter(e.target.value as PassFilter)}
            className="rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
          >
            <option value="all">All</option>
            <option value="passed">Passed</option>
            <option value="failed">Failed</option>
          </select>
        </label>
      </div>

      <div className="mt-2 overflow-x-auto">
        {run.case_results.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
            No case results for this run.
          </p>
        ) : filteredCaseResults.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
            No case results match the current filter.
          </p>
        ) : (
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Case ID
                </th>
                <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Iteration
                </th>
                <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Status
                </th>
                <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Score
                </th>
                <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Duration
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredCaseResults.map((result) => (
                <CaseResultRow
                  key={`${result.case_id}-${result.iteration}`}
                  result={result}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default RunDetailPage;
