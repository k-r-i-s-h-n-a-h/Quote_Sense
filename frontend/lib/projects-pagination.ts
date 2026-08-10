/** Pure helpers for Tatva user-projects list pagination (unit-tested). */

export type JsonRecord = Record<string, unknown>;

export const LIST_KEYS = [
  "data",
  "projects",
  "projectRequests",
  "items",
  "results",
  "quotes",
  "docs",
] as const;

export function findList(
  payload: unknown
): { items: JsonRecord[]; path: string[] } | null {
  if (Array.isArray(payload)) {
    return { items: payload as JsonRecord[], path: [] };
  }
  if (!payload || typeof payload !== "object") return null;
  const root = payload as JsonRecord;

  for (const key of LIST_KEYS) {
    const val = root[key];
    if (Array.isArray(val)) return { items: val as JsonRecord[], path: [key] };
  }
  for (const key of LIST_KEYS) {
    const nested = root[key];
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      const nestedRecord = nested as JsonRecord;
      for (const nestedKey of LIST_KEYS) {
        const val = nestedRecord[nestedKey];
        if (Array.isArray(val)) {
          return { items: val as JsonRecord[], path: [key, nestedKey] };
        }
      }
    }
  }
  return null;
}

export function idsOf(items: JsonRecord[]): string[] {
  return items.map((it) => String(it._id ?? it.id ?? ""));
}

export function sameIds(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((id, i) => id === b[i]);
}

export function dedupeById(items: JsonRecord[]): JsonRecord[] {
  const seen = new Set<string>();
  const out: JsonRecord[] = [];
  for (const it of items) {
    const id = String(it._id ?? it.id ?? "");
    if (!id) {
      out.push(it);
      continue;
    }
    if (seen.has(id)) continue;
    seen.add(id);
    out.push(it);
  }
  return out;
}

export function readTotalHint(payload: unknown): number | null {
  if (!payload || typeof payload !== "object") return null;
  const root = payload as JsonRecord;
  const nested =
    root.data && typeof root.data === "object" && !Array.isArray(root.data)
      ? (root.data as JsonRecord)
      : null;
  const pagination =
    root.pagination && typeof root.pagination === "object"
      ? (root.pagination as JsonRecord)
      : nested?.pagination && typeof nested.pagination === "object"
        ? (nested.pagination as JsonRecord)
        : null;
  const meta =
    root.meta && typeof root.meta === "object"
      ? (root.meta as JsonRecord)
      : null;

  const candidates = [
    root.total,
    root.totalDocs,
    root.totalCount,
    root.count,
    nested?.total,
    nested?.totalDocs,
    nested?.totalCount,
    pagination?.total,
    pagination?.totalDocs,
    meta?.total,
  ];
  for (const c of candidates) {
    if (typeof c === "number" && Number.isFinite(c) && c >= 0) return c;
    if (typeof c === "string" && /^\d+$/.test(c)) return Number(c);
  }
  return null;
}

/** Whether we should request another page after receiving `lastPageCount` items.
 *
 * Do NOT stop on Tatva's `pagination.total` alone — it has been observed to
 * under-report (e.g. total/pages say 81/1 while later pages still return rows).
 * Only empty pages, duplicate pages, or MAX_PAGES end the loop in the route.
 */
export function shouldFetchNextPage(opts: {
  page: number;
  maxPages: number;
  lastPageCount: number;
  mergedCount: number;
  totalHint: number | null;
}): boolean {
  void opts.mergedCount;
  void opts.totalHint;
  if (opts.page >= opts.maxPages) return false;
  if (opts.lastPageCount === 0) return false;
  return true;
}
