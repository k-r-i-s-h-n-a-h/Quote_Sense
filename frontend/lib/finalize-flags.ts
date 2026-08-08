/**
 * Shared Tatva “finalized quote” flag + small string helpers (Sonar-friendly).
 */

export function isTruthyFlag(value: unknown): boolean {
  if (value === true || value === 1) return true;
  if (typeof value === "string") {
    const s = value.trim().toLowerCase();
    return s === "true" || s === "1" || s === "yes" || s === "on";
  }
  return false;
}

/** Case-insensitive finalize keys: isFinalizeQuote, is_finalized, … */
export function isFinalizeFlagFromRecord(
  raw: Record<string, unknown>
): boolean {
  for (const [k, v] of Object.entries(raw)) {
    const key = k.toLowerCase().replaceAll("_", "");
    if (
      key === "isfinalizequote" ||
      key === "isfinalizedquote" ||
      key === "isfinalized" ||
      key === "finalizequote" ||
      key === "finalized"
    ) {
      if (isTruthyFlag(v)) return true;
    }
  }
  return false;
}

export function digitsOnly(value: string): string {
  return value.replaceAll(/\D/g, "");
}

export function parseLooseNumber(value: string): number {
  return Number.parseFloat(value.replaceAll(",", ""));
}
