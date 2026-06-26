/** Cache Tatva quote JSON on the project page so compare does not re-fetch. */

import {
  clampQuoteIds,
  MAX_COMPARE_QUOTES,
  MIN_COMPARE_QUOTES,
} from "./compare-limits";

type RawQuote = Record<string, unknown>;

export type CompareProjectMeta = {
  title: string;
  projectCode: string;
  mongoId?: string;
};

type CacheEntry = {
  quotes: RawQuote[];
  meta?: CompareProjectMeta;
  cachedAt: number;
};

const KEY = (projectId: string) => `qs-compare-payload-${projectId}`;
const SELECTED_KEY = (projectId: string) => `qs-compare-selected-${projectId}`;
const TTL_MS = 30 * 60 * 1000;

export function cacheProjectQuotePayloads(
  projectId: string,
  quotes: RawQuote[],
  meta?: CompareProjectMeta
): void {
  if (typeof window === "undefined" || !projectId || quotes.length === 0) return;
  try {
    const entry: CacheEntry = { quotes, meta, cachedAt: Date.now() };
    sessionStorage.setItem(KEY(projectId), JSON.stringify(entry));
  } catch {
    /* quota — compare will fall back to API fetch */
  }
}

export function readCachedProjectQuotePayloads(
  projectRef: string
): CacheEntry | null {
  if (typeof window === "undefined" || !projectRef) return null;
  try {
    const raw =
      sessionStorage.getItem(KEY(projectRef)) ||
      sessionStorage.getItem(KEY(projectRef.toUpperCase()));
    if (!raw) return null;
    const entry = JSON.parse(raw) as CacheEntry;
    if (!entry?.quotes?.length) return null;
    if (Date.now() - (entry.cachedAt || 0) > TTL_MS) {
      sessionStorage.removeItem(KEY(projectRef));
      return null;
    }
    return entry;
  } catch {
    return null;
  }
}

export function cacheSelectedComparePayloads(
  projectId: string,
  quotes: RawQuote[],
  meta?: CompareProjectMeta
): void {
  if (typeof window === "undefined" || !projectId || quotes.length < MIN_COMPARE_QUOTES) return;
  if (quotes.length > MAX_COMPARE_QUOTES) return;
  try {
    const entry: CacheEntry = {
      quotes: quotes.slice(0, MAX_COMPARE_QUOTES),
      meta,
      cachedAt: Date.now(),
    };
    sessionStorage.setItem(SELECTED_KEY(projectId), JSON.stringify(entry));
  } catch {
    /* quota */
  }
}

export function readSelectedComparePayloads(projectId: string): CacheEntry | null {
  if (typeof window === "undefined" || !projectId) return null;
  try {
    const raw = sessionStorage.getItem(SELECTED_KEY(projectId));
    if (!raw) return null;
    const entry = JSON.parse(raw) as CacheEntry;
    if (!entry?.quotes?.length) return null;
    if (Date.now() - (entry.cachedAt || 0) > TTL_MS) {
      sessionStorage.removeItem(SELECTED_KEY(projectId));
      return null;
    }
    return entry;
  } catch {
    return null;
  }
}

export function getCachedQuotesByIds(
  projectId: string,
  quoteIds: string[]
): RawQuote[] | null {
  const wantedIds = clampQuoteIds(quoteIds);
  if (wantedIds.length < MIN_COMPARE_QUOTES) return null;

  const selected = readSelectedComparePayloads(projectId);
  if (selected && selected.quotes.length >= MIN_COMPARE_QUOTES) {
    const wanted = new Set(wantedIds);
    const match = selected.quotes.filter((q) =>
      wanted.has(String(q._id || q.id))
    );
    if (match.length >= MIN_COMPARE_QUOTES && match.length <= MAX_COMPARE_QUOTES) {
      return match.slice(0, MAX_COMPARE_QUOTES);
    }
  }

  const entry = readCachedProjectQuotePayloads(projectId);
  if (!entry) return null;
  const wanted = new Set(wantedIds);
  const filtered = entry.quotes.filter((q) =>
    wanted.has(String(q._id || q.id))
  );
  if (filtered.length < MIN_COMPARE_QUOTES) return null;
  return filtered.slice(0, MAX_COMPARE_QUOTES);
}
