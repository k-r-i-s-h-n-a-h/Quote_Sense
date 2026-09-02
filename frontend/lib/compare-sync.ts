/**
 * MongoDB / Tatva quote payload → QuoteSense comparison engine (async).
 */

import {
  cacheSelectedComparePayloads,
  getCachedQuotesByIds,
} from "./compare-payload-cache";
import {
  clampQuoteIds,
  compareCountPhrase,
  isValidCompareCount,
} from "./compare-limits";
import { unwrapApiList } from "./project-mappers";
import { getAuthToken, getAuthUserId } from "./auth";
import { resolveProjectRefForCompare } from "./project-api";

type RawQuote = Record<string, unknown>;

export type StartCompareJobResult =
  | { ok: true; session_id: string }
  | { ok: false; message: string };

function backendUrl(): string {
  return process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";
}

function syncMongoUrl(sessionId: string, projectMongoId?: string): string {
  const params = new URLSearchParams({ session_id: sessionId });
  if (projectMongoId) {
    params.set("project_id", projectMongoId);
  }
  return `/api/compare/sync-mongodb?${params.toString()}`;
}

export function newComparisonSessionId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `session_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
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

/** Prefer selected cache → full project cache → Tatva API fetch. */
export async function resolveQuotesForCompare(
  projectRef: string,
  quoteIds: string[],
  userId?: string | null
): Promise<
  | { ok: true; quotes: RawQuote[]; mongoId: string }
  | { ok: false; message: string }
> {
  const resolved = await resolveProjectRefForCompare(
    projectRef,
    userId ?? getAuthUserId(null)
  );
  if (!resolved) {
    return {
      ok: false,
      message: "Project not found. Open the project from your dashboard first.",
    };
  }

  const { mongoId, publicRef } = resolved;
  const cacheKey = publicRef;

  const cached =
    getCachedQuotesByIds(cacheKey, quoteIds) ||
    getCachedQuotesByIds(mongoId, quoteIds);
  if (cached && isValidCompareCount(cached.length)) {
    return { ok: true, quotes: cached, mongoId };
  }

  const token = getAuthToken();
  const res = await fetch(
    `/api/projects/${encodeURIComponent(mongoId)}/quotes`,
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
      message: `Select ${compareCountPhrase()} quotes to compare.`,
    };
  }

  cacheSelectedComparePayloads(cacheKey, selected, {
    title: "",
    projectCode: publicRef,
    mongoId,
  });
  return { ok: true, quotes: selected, mongoId };
}

/** Kick off async MongoDB lane — poll /api/progress/{session_id} for results. */
export async function startMongoCompareJob(
  quotes: RawQuote[],
  sessionId?: string,
  projectMongoId?: string
): Promise<StartCompareJobResult> {
  if (!isValidCompareCount(quotes.length)) {
    return {
      ok: false,
      message: `You can compare ${compareCountPhrase()} quotes at a time.`,
    };
  }

  const sid = sessionId || newComparisonSessionId();
  const token = getAuthToken();

  try {
    const res = await fetch(syncMongoUrl(sid, projectMongoId), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
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
