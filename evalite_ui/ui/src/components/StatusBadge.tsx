/** Lifecycle/outcome states a badge can represent. */
export type BadgeStatus = "passed" | "failed" | "running" | "started";

export interface StatusBadgeProps {
  status: BadgeStatus;
}

const STATUS_CLASSES: Record<BadgeStatus, string> = {
  passed:
    "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  running:
    "bg-yellow-100 text-yellow-800 animate-pulse dark:bg-yellow-900/40 dark:text-yellow-300",
  started: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
};

const STATUS_LABELS: Record<BadgeStatus, string> = {
  passed: "Passed",
  failed: "Failed",
  running: "Running",
  started: "Started",
};

function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_CLASSES[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

export default StatusBadge;
