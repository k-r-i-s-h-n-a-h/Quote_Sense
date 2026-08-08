/**
 * Push user-finalized Tatva quote payloads into market_moving_averages.
 * Best-effort: never blocks project load / compare UI.
 */

import { isFinalizeFlagFromRecord } from "./finalize-flags";

function unwrapQuote(entry: unknown): Record<string, unknown> | null {
  if (!entry || typeof entry !== "object") return null;
  const rec = entry as Record<string, unknown>;
  const inner = rec.data ?? rec.quote;
  if (
    inner &&
    typeof inner === "object" &&
    ("quoteNumber" in (inner as object) ||
      "workSummary" in (inner as object) ||
      "isFinalizeQuote" in (inner as object) ||
      "is_finalized" in (inner as object))
  ) {
    return inner as Record<string, unknown>;
  }
  return rec;
}

/** Extract full payload objects that carry the user-finalize flag. */
export function filterFinalizedQuotePayloads(quotes: unknown[]): unknown[] {
  return quotes.filter((q) => {
    const raw = unwrapQuote(q);
    return raw ? isFinalizeFlagFromRecord(raw) : false;
  });
}

/**
 * Fire-and-forget apply when a project loads quote lists that may include
 * isFinalizeQuote=true. Safe to call repeatedly (backend is idempotent).
 * Primary path is server-side apply in /api/projects/.../quotes.
 */
export function applyFinalizedQuotesInBackground(quotes: unknown[]): void {
  const finalized = filterFinalizedQuotePayloads(quotes);
  if (finalized.length === 0) return;

  void fetch("/api/market-rate/apply-finalized", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quotes: finalized }),
  }).catch(() => {
    /* non-blocking */
  });
}
