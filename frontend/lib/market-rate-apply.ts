/**
 * Push user-finalized Tatva quote payloads into market_moving_averages.
 * Best-effort: never blocks project load / compare UI.
 */

function isFinalizeFlag(raw: Record<string, unknown>): boolean {
  const v =
    raw.isFinalizeQuote ??
    raw.isFinalizedQuote ??
    raw.isFinalized ??
    raw.finalizeQuote ??
    raw.is_finalize_quote ??
    raw.is_finalized_quote ??
    raw.is_finalized ??
    raw.finalized;
  return v === true || v === "true" || v === 1 || v === "1";
}

function unwrapQuote(entry: unknown): Record<string, unknown> | null {
  if (!entry || typeof entry !== "object") return null;
  const rec = entry as Record<string, unknown>;
  const inner = rec.data ?? rec.quote;
  if (
    inner &&
    typeof inner === "object" &&
    ("quoteNumber" in (inner as object) ||
      "workSummary" in (inner as object) ||
      "isFinalizeQuote" in (inner as object))
  ) {
    return inner as Record<string, unknown>;
  }
  return rec;
}

/** Extract full payload objects that carry the user-finalize flag. */
export function filterFinalizedQuotePayloads(quotes: unknown[]): unknown[] {
  return quotes.filter((q) => {
    const raw = unwrapQuote(q);
    return raw ? isFinalizeFlag(raw) : false;
  });
}

/**
 * Fire-and-forget apply when a project loads quote lists that may include
 * isFinalizeQuote=true. Safe to call repeatedly (backend is idempotent).
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
