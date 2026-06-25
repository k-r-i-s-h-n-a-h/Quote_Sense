/** QuoteSense comparison limits (product spec: 2–3 quotes). */

export const MIN_COMPARE_QUOTES = 2;
export const MAX_COMPARE_QUOTES = 3;

export const MAX_COMPARE_MESSAGE = `You can compare at most ${MAX_COMPARE_QUOTES} quotes at a time. Deselect one to add another.`;

export function dedupeQuoteIds(ids: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const id of ids) {
    const key = String(id).trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(key);
  }
  return out;
}

export function clampQuoteIds(ids: string[]): string[] {
  return dedupeQuoteIds(ids).slice(0, MAX_COMPARE_QUOTES);
}

export function isValidCompareCount(count: number): boolean {
  return count >= MIN_COMPARE_QUOTES && count <= MAX_COMPARE_QUOTES;
}
