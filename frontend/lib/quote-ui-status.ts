/**
 * Tatva sends status (lifecycle) and isFinalizeQuote (customer finalize) as
 * independent fields. UI shows dual badges: SUBMITTED + FINALIZED when both apply.
 * Do not rewrite status — that would hide the lifecycle badge.
 */

import { isFinalizeFlagFromRecord } from "./finalize-flags";

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

/** Normalize finalize flag on one quote; leave status as Tatva sent it. */
export function annotateQuoteUiStatus(
  quote: Record<string, unknown>
): Record<string, unknown> {
  if (isFinalizeFlagFromRecord(quote)) {
    quote.isFinalizeQuote = true;
  }
  return quote;
}

/**
 * Walk typical Tatva list envelopes and normalize isFinalizeQuote.
 * Leaves `status` untouched so dual badges stay correct.
 */
export function annotateQuotesPayloadForUi(payload: unknown): unknown {
  if (Array.isArray(payload)) {
    return payload.map((item) =>
      isRecord(item) ? annotateQuoteUiStatus({ ...item }) : item
    );
  }
  if (!isRecord(payload)) return payload;

  const out: Record<string, unknown> = { ...payload };
  const listKeys = [
    "data",
    "quotes",
    "items",
    "results",
    "docs",
    "projectRequests",
  ] as const;

  for (const key of listKeys) {
    const val = out[key];
    if (Array.isArray(val)) {
      out[key] = val.map((item) =>
        isRecord(item) ? annotateQuoteUiStatus({ ...item }) : item
      );
    } else if (isRecord(val) && Array.isArray(val.data)) {
      out[key] = {
        ...val,
        data: val.data.map((item) =>
          isRecord(item) ? annotateQuoteUiStatus({ ...item }) : item
        ),
      };
    }
  }

  return out;
}
