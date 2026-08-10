import { useEffect, useRef } from "react";
import type { WsEvent } from "../api/types";

export interface LiveFeedProps {
  events: WsEvent[];
}

/** Renders an icon distinguishing each WsEvent variant. */
function EventIcon({ event }: { event: WsEvent }) {
  switch (event.event) {
    case "case_started":
      return (
        <span
          className="text-gray-400 dark:text-gray-500"
          title="Case started"
          aria-hidden="true"
        >
          ▶
        </span>
      );
    case "case_completed":
      return event.passed ? (
        <span
          className="text-green-500"
          title="Case passed"
          aria-hidden="true"
        >
          ✓
        </span>
      ) : (
        <span className="text-red-500" title="Case failed" aria-hidden="true">
          ✗
        </span>
      );
    case "run_completed":
      return (
        <span
          className="text-green-500"
          title="Run completed"
          aria-hidden="true"
        >
          ●
        </span>
      );
    case "run_failed":
      return (
        <span className="text-red-500" title="Run failed" aria-hidden="true">
          ⚠
        </span>
      );
  }
}

/** Renders a single row's label text for a WsEvent. */
function EventLabel({ event }: { event: WsEvent }) {
  switch (event.event) {
    case "case_started":
      return (
        <span className="text-gray-900 dark:text-gray-100">
          {event.case_id}{" "}
          <span className="text-gray-500 dark:text-gray-400">
            (iteration {event.iteration}) started
          </span>
        </span>
      );
    case "case_completed":
      return (
        <span className="text-gray-900 dark:text-gray-100">
          {event.case_id}{" "}
          <span className="text-gray-500 dark:text-gray-400">
            (iteration {event.iteration}) — score {event.score.toFixed(2)}
          </span>
        </span>
      );
    case "run_completed":
      return (
        <span className="text-gray-900 dark:text-gray-100">
          Run completed —{" "}
          <span className="text-gray-500 dark:text-gray-400">
            {event.passed} passed, {event.failed} failed (
            {Math.round(event.pass_rate * 100)}%)
          </span>
        </span>
      );
    case "run_failed":
      return (
        <span className="text-gray-900 dark:text-gray-100">
          Run failed —{" "}
          <span className="text-red-500">{event.error}</span>
        </span>
      );
  }
}

/** Builds a stable-ish key for a WsEvent row. */
function eventKey(event: WsEvent, index: number): string {
  switch (event.event) {
    case "case_started":
      return `case_started-${event.case_id}-${event.iteration}-${index}`;
    case "case_completed":
      return `case_completed-${event.case_id}-${event.iteration}-${index}`;
    case "run_completed":
      return `run_completed-${event.run_id}-${index}`;
    case "run_failed":
      return `run_failed-${event.run_id}-${index}`;
  }
}

/**
 * Scrolling list of WsEvents, newest at the bottom, auto-scrolled into view
 * whenever a new event arrives.
 */
function LiveFeed({ events }: LiveFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [events]);

  return (
    <div
      ref={containerRef}
      className="h-full max-h-96 overflow-y-auto rounded border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900"
    >
      {events.length === 0 ? (
        <div className="p-4 text-sm text-gray-500 dark:text-gray-400">
          Waiting for events…
        </div>
      ) : (
        <ul>
          {events.map((event, index) => (
            <li
              key={eventKey(event, index)}
              className="flex items-center gap-2 border-b border-gray-100 px-3 py-1.5 text-sm last:border-b-0 dark:border-gray-800"
            >
              <EventIcon event={event} />
              <EventLabel event={event} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default LiveFeed;
