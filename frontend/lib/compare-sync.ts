/**
 * MongoDB / Tatva quote payload → QuoteSense comparison engine (async).
 */

import {
  cacheSelectedComparePayloads,
  getCachedQuotesByIds,
} from "./compare-payload-cache";
import {
  MAX_COMPARE_QUOTES,
  MIN_COMPARE_QUOTES,
  clampQuoteIds,
  isValidCompareCount,
} from "./compare-limits";
import { unwrapApiList } from "./project-mappers";
import { getAuthToken } from "./auth";

type RawQuote = Record<string, unknown>;

export type StartCompareJobResult =
  | { ok: true; session_id: string }
  | { ok: false; message: string };

function backendUrl(): string {
  return process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";
}

function syncMongoUrl(sessionId: string): string {
  return `/api/compare/sync-mongodb?session_id=${encodeURIComponent(sessionId)}`;
}

export function newComparisonSessionId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `session_${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;
  }
  return `session_${Date.now().toString(36)}`;
}

export function filterQuotesByIds(
  quotes: RawQuote[],
  quoteIds: string[]
): RawQuote[] {
  const wanted = new Set(clampQuoteIds(quoteIds).map(String));
  const seen = new Set<string>();
  const out: RawQuote[] = [];
  for (const q of quotes) {
    const id = String(q._id || q.id);
    if (!wanted.has(id) || seen.has(id)) continue;
    seen.add(id);
    out.push(q);
  }
  return out;
}

/** Prefer selected cache → full project cache → single API fetch. */
export async function resolveQuotesForCompare(
  projectId: string,
  quoteIds: string[]
): Promise<{ ok: true; quotes: RawQuote[] } | { ok: false; message: string }> {
  const cached = getCachedQuotesByIds(projectId, quoteIds);
  if (cached && isValidCompareCount(cached.length)) {
    return { ok: true, quotes: cached };
  }

  const token = getAuthToken();
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/quotes`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} }
  );

  let data: unknown;
  try {
    data = await res.json();
  } catch {
    return { ok: false, message: "Invalid response when loading quotes." };
  }

  if (!res.ok) {
    return {
      ok: false,
      message:
        (data as { message?: string })?.message ||
        `Failed to load quotes (${res.status})`,
    };
  }

  const selected = filterQuotesByIds(unwrapApiList(data), quoteIds);
  if (!isValidCompareCount(selected.length)) {
    return {
      ok: false,
      message: `Select ${MIN_COMPARE_QUOTES}–${MAX_COMPARE_QUOTES} quotes to compare.`,
    };
  }

  cacheSelectedComparePayloads(projectId, selected);
  return { ok: true, quotes: selected };
}

/** Kick off async MongoDB lane — poll /api/progress/{session_id} for results. */
export async function startMongoCompareJob(
  quotes: RawQuote[],
  sessionId?: string
): Promise<StartCompareJobResult> {
  if (!isValidCompareCount(quotes.length)) {
    return {
      ok: false,
      message: `You can compare ${MIN_COMPARE_QUOTES}–${MAX_COMPARE_QUOTES} quotes at a time.`,
    };
  }

  const sid = sessionId || newComparisonSessionId();

  try {
    const res = await fetch(syncMongoUrl(sid), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(quotes),
    });

    const data = await res.json();

    if (!res.ok || data.status === "error") {
      return {
        ok: false,
        message: data.message || `Failed to start comparison (${res.status})`,
      };
    }

    if (!data.session_id) {
      return { ok: false, message: "Backend did not return a session id." };
    }

    return { ok: true, session_id: data.session_id };
  } catch {
    return {
      ok: false,
      message: `Cannot reach comparison backend at ${backendUrl()}. Start it on port 8001.`,
    };
  }
}
