/**
 * Horizontal bar visualizing a normalized score in [0.0, 1.0].
 *
 * Color thresholds: 0–0.5 = red, 0.5–0.8 = yellow, 0.8–1.0 = green.
 *
 * Percentage-text heuristic: measuring actual rendered pixel width would
 * require a ref + ResizeObserver, which is real complexity for a cosmetic
 * detail. Instead we show the label once `value >= 0.15`, which roughly
 * corresponds to the bar exceeding ~40px in a typical ~250-300px-wide
 * container. This is an approximation, not a pixel-accurate measurement.
 */
export interface ScoreBarProps {
  /** Normalized score in [0.0, 1.0]. */
  value: number;
}

function barColorClass(value: number): string {
  if (value < 0.5) return "bg-red-500";
  if (value < 0.8) return "bg-yellow-500";
  return "bg-green-500";
}

function ScoreBar({ value }: ScoreBarProps) {
  const clamped = Math.min(1, Math.max(0, value));
  const widthPercent = clamped * 100;
  const showLabel = clamped >= 0.15;

  return (
    <div
      className="relative h-5 w-full min-w-[80px] overflow-hidden rounded bg-gray-200 dark:bg-gray-700"
      role="progressbar"
      aria-valuenow={Math.round(clamped * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full ${barColorClass(clamped)} transition-[width] duration-300`}
        style={{ width: `${widthPercent}%` }}
      >
        {showLabel && (
          <span className="flex h-full items-center justify-end pr-1 text-xs font-medium text-white">
            {Math.round(widthPercent)}%
          </span>
        )}
      </div>
    </div>
  );
}

export default ScoreBar;
