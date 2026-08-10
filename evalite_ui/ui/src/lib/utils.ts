/**
 * Small shared utilities, in the spot shadcn/ui conventions expect
 * (`src/lib/utils.ts`) — see ADR-004 ("React + Vite + TailwindCSS +
 * shadcn/ui").
 */

type ClassValue = string | number | null | undefined | false | ClassDictionary | ClassValue[];
type ClassDictionary = Record<string, boolean | null | undefined>;

/**
 * Merges class name inputs into a single string, à la `clsx`.
 *
 * Accepts strings, numbers, arrays (recursively), and `{ className:
 * boolean }` dictionaries; falsy values (`null`, `undefined`, `false`,
 * `""`) are skipped.
 *
 * This is a hand-written `clsx`-equivalent only — deliberately no
 * `tailwind-merge`-style Tailwind class *conflict* resolution (e.g.
 * de-duping `"p-2 p-4"` down to `"p-4"`), since that would require adding
 * the `tailwind-merge` npm package, which needs lead approval per the
 * frontend hard constraints. Callers should avoid passing conflicting
 * Tailwind utility classes for the same property.
 */
export function cn(...inputs: ClassValue[]): string {
  const classes: string[] = [];

  for (const input of inputs) {
    if (!input) continue;

    if (typeof input === "string" || typeof input === "number") {
      classes.push(String(input));
      continue;
    }

    if (Array.isArray(input)) {
      const nested = cn(...input);
      if (nested) classes.push(nested);
      continue;
    }

    if (typeof input === "object") {
      for (const key in input) {
        if (Object.prototype.hasOwnProperty.call(input, key) && input[key]) {
          classes.push(key);
        }
      }
    }
  }

  return classes.join(" ");
}

/** Formats a millisecond duration as e.g. "123ms" or "1.2s". */
export function formatDuration(durationMs: number): string {
  if (durationMs < 1000) return `${Math.round(durationMs)}ms`;
  return `${(durationMs / 1000).toFixed(1)}s`;
}
