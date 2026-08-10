import type { RunSummary } from "../api/types";
import StatusBadge from "./StatusBadge";

export interface RunsTableProps {
  runs: RunSummary[];
  onRowClick: (runId: string) => void;
}

/** Truncates a run id to its first 8 chars, e.g. "a1b2c3d4…". */
function truncateRunId(runId: string): string {
  return runId.length > 8 ? `${runId.slice(0, 8)}…` : runId;
}

/** Computes passed / (passed + failed), or `null` if there's no data yet. */
function computePassRate(passed: number, failed: number): number | null {
  const total = passed + failed;
  if (total === 0) return null;
  return passed / total;
}

/**
 * Maps a `RunSummary` onto the badge statuses StatusBadge supports
 * ("passed" | "failed" | "running" | "started").
 *
 * "complete" is not a single badge outcome: a "complete" run can still
 * have failed cases (e.g. 2 passed / 8 failed), and showing a blanket
 * green "Passed" pill in that case would contradict the adjacent Pass
 * Rate/Passed/Failed columns — misleading for the dashboard's
 * non-engineer audience scanning for failures. So "complete" is derived
 * from the actual counts: green "passed" only when there are zero
 * failures, red "failed" otherwise. "started"/"running"/"failed" map to
 * their existing badge variants unchanged.
 */
function toBadgeStatus(
  status: RunSummary["status"],
  failed: number,
): "passed" | "failed" | "running" | "started" {
  if (status === "complete") return failed === 0 ? "passed" : "failed";
  return status;
}

function RunsTable({ runs, onRowClick }: RunsTableProps) {
  return (
    <table className="w-full border-collapse text-left">
      <thead>
        <tr className="border-b border-gray-200 dark:border-gray-700">
          <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
            Run ID
          </th>
          <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
            Test Set
          </th>
          <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
            Pass Rate
          </th>
          <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
            Passed
          </th>
          <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
            Failed
          </th>
          <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
            Timestamp
          </th>
          <th className="px-4 py-2 text-sm font-medium text-gray-500 dark:text-gray-400">
            Status
          </th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => {
          const passRate = computePassRate(run.passed, run.failed);
          return (
            <tr
              key={run.run_id}
              onClick={() => onRowClick(run.run_id)}
              className="cursor-pointer border-b border-gray-200 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
            >
              <td className="px-4 py-2 font-mono text-sm text-gray-900 dark:text-gray-100">
                {truncateRunId(run.run_id)}
              </td>
              <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                {run.test_set_name ?? "—"}
              </td>
              <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                {passRate === null ? "—" : `${Math.round(passRate * 100)}%`}
              </td>
              <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                {run.passed}
              </td>
              <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                {run.failed}
              </td>
              <td className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
                {new Date(run.timestamp).toLocaleString()}
              </td>
              <td className="px-4 py-2">
                <StatusBadge status={toBadgeStatus(run.status, run.failed)} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default RunsTable;
