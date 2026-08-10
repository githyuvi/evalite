import type { CaseResult } from "../api/types";
import ScoreBar from "./ScoreBar";
import StatusBadge from "./StatusBadge";

export interface CaseResultRowProps {
  result: CaseResult;
}

/** Formats a millisecond duration as e.g. "123ms" or "1.2s". */
function formatDuration(durationMs: number): string {
  if (durationMs < 1000) return `${Math.round(durationMs)}ms`;
  return `${(durationMs / 1000).toFixed(1)}s`;
}

/** One `<tr>` of a case-results table. Intended for use inside a `<table>`. */
function CaseResultRow({ result }: CaseResultRowProps) {
  return (
    <tr className="border-b border-gray-200 dark:border-gray-700">
      <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
        {result.case_id}
      </td>
      <td className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
        {result.iteration}
      </td>
      <td className="px-4 py-2">
        <StatusBadge status={result.passed ? "passed" : "failed"} />
      </td>
      <td className="px-4 py-2">
        <ScoreBar value={result.score.value} />
      </td>
      <td className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
        {formatDuration(result.duration_ms)}
      </td>
    </tr>
  );
}

export default CaseResultRow;
