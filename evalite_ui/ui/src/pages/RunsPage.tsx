import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns } from "../api/client";
import type { RunSummary } from "../api/types";
import RunsTable from "../components/RunsTable";

const POLL_INTERVAL_MS = 30_000;

function RunsPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const hasLoadedOnce = useRef(false);

  const fetchRuns = useCallback(async () => {
    try {
      const response = await listRuns();
      setRuns(response.runs);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setRuns(null);
    } finally {
      if (!hasLoadedOnce.current) {
        hasLoadedOnce.current = true;
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void fetchRuns();
    const intervalId = setInterval(() => {
      void fetchRuns();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, [fetchRuns]);

  const handleRowClick = (runId: string) => {
    navigate(`/runs/${runId}`);
  };

  return (
    <div className="p-6 text-gray-900 dark:text-gray-100">
      <h1 className="mb-4 text-xl font-semibold">Runs</h1>

      {loading && (
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading runs…</p>
      )}

      {!loading && error && (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      {!loading && !error && runs !== null && runs.length === 0 && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No runs yet. Run{" "}
          <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-sm dark:bg-gray-800">
            evalite run &lt;test-set.yaml&gt;
          </code>{" "}
          to get started.
        </p>
      )}

      {!loading && !error && runs !== null && runs.length > 0 && (
        <RunsTable runs={runs} onRowClick={handleRowClick} />
      )}
    </div>
  );
}

export default RunsPage;
