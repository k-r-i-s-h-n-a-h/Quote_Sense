/**
 * F0 — TypeScript mirror of the backend MatrixV1 payload.
 *
 * Backend source of truth: backend/docs/plan/00-contracts.md
 * See frontend/docs/plan/00-contracts.md for why this file exists.
 *
 * Every tier field is optional so the frontend can be deployed ahead of the
 * backend: a payload carrying only the legacy flat `tableData` still renders.
 */

import type { VendorMeta } from "./format";

export type Vendor = string;

/** How a vendor's zero should be read for one cell. */
export type CoverageStatus = "quoted" | "incl_in_bundle" | "not_quoted";

/** How a vendor's figure in a bundle row was arrived at. */
export type PriceBasis = "bundle" | "itemized" | "none";

export interface Breakdown {
  vendor?: string;
  item?: string;
  amount?: number;
}

export interface SpaceRow {
  category?: string;
  space_id?: string;
  space?: string;
  space_raw?: string;
  work_key?: string;
  sub_service?: string;
  item_name?: string;
  room?: string;
  pricing_method?: string;
  breakdown?: Breakdown[];
  /** Per-vendor cell status, e.g. "quoted" or "incl_in_bundle:Hardware". */
  coverage?: Record<Vendor, string>;
  work_confidence?: number;
  space_confidence?: number;
  /** Vendor names are dynamic column keys, hence the index signature. */
  [key: string]: unknown;
}

export interface BundleRow {
  bundle_id?: string;
  bundle_label?: string;
  bundle_family?: string;
  covered_spaces?: string[];
  covered_items?: string[];
  overlap_flags?: string[];
  basis?: Record<Vendor, PriceBasis>;
  line_counts?: Record<Vendor, number>;
  has_bundle?: boolean;
  [key: string]: unknown;
}

export interface CoverageEntry {
  space_id: string;
  space: string;
  vendor: Vendor;
  status: CoverageStatus;
  bundle_id?: string;
  bundle_label?: string;
  comparable: boolean;
}

export interface MatrixV1 {
  contract_version?: string;
  vendors?: Vendor[];
  vendorMeta?: Record<Vendor, VendorMeta>;
  chartData?: { vendor: string; total: number }[];
  spaceTier?: SpaceRow[];
  bundleTier?: BundleRow[];
  projectTier?: SpaceRow[];
  coverage?: CoverageEntry[];
  /** Legacy flat shape, equal to spaceTier + projectTier. */
  tableData?: SpaceRow[];
  report?: string;
  session_id?: string;
}

/**
 * Read a vendor amount. Every component goes through this rather than indexing
 * inline — direct `row[vendor]` access is what previously let a NaN reach the
 * DOM as a silently blank cell.
 */
export function amountOf(row: SpaceRow | BundleRow, vendor: Vendor): number {
  const n = Number(row[vendor]);
  return Number.isFinite(n) ? n : 0;
}

/** Space-tier rows, falling back to the legacy flat payload. */
export function spaceRowsOf(matrix: MatrixV1): SpaceRow[] {
  if (matrix.spaceTier) return matrix.spaceTier;
  return (matrix.tableData ?? []).filter(
    (row) => String(row.space_id ?? "") !== "project_level"
  );
}

/** Project-level rows, falling back to the legacy flat payload. */
export function projectRowsOf(matrix: MatrixV1): SpaceRow[] {
  if (matrix.projectTier) return matrix.projectTier;
  return (matrix.tableData ?? []).filter(
    (row) => String(row.space_id ?? "") === "project_level"
  );
}

/** Bundle rows. Empty for a legacy payload, which hides the bundle section. */
export function bundleRowsOf(matrix: MatrixV1): BundleRow[] {
  return matrix.bundleTier ?? [];
}

export function coverageOf(matrix: MatrixV1): CoverageEntry[] {
  return matrix.coverage ?? [];
}

/** True when at least one vendor priced this family as a single lumpsum. */
export function isLumpSumBundle(row: BundleRow): boolean {
  if (row.has_bundle) return true;
  return Object.values(row.basis ?? {}).some((b) => b === "bundle");
}

/** Split bundle-tier rows into customer-facing sections. */
export function partitionBundleRows(rows: BundleRow[]): {
  lumpSums: BundleRow[];
  scattered: BundleRow[];
} {
  const lumpSums: BundleRow[] = [];
  const scattered: BundleRow[] = [];
  for (const row of rows) {
    if (isLumpSumBundle(row)) lumpSums.push(row);
    else scattered.push(row);
  }
  return { lumpSums, scattered };
}

/** Short customer-facing note under a bundle amount — no internal jargon. */
export function bundlePriceNote(
  row: BundleRow,
  vendor: Vendor
): string {
  const basis = row.basis?.[vendor] ?? "none";
  const count = row.line_counts?.[vendor] ?? 0;
  if (basis === "bundle") return "Package price";
  if (basis === "itemized") {
    if (count <= 1) return "Itemised";
    return `Itemised · ${count} lines`;
  }
  return "";
}

/**
 * Rebuild each vendor's quote total from the three tiers.
 *
 * Bundle-tier rows with `basis === "itemized"` are already counted in space or
 * project tiers (scattered family lines). Only a true lumpsum (`basis ===
 * "bundle"`) is extra money that was pulled out of the room totals.
 *
 * `quotedTotal`, when provided (the PDF/Mongo grand total from chartData), is
 * the original quote amount the cards show. Any gap vs the tier sum is exposed
 * as `other` — typically GST, round-off, or lines the extractor skipped.
 */
export function reconcileQuoteTotals(
  vendors: Vendor[],
  spaceTier: SpaceRow[],
  bundleTier: BundleRow[],
  projectTier: SpaceRow[],
  quotedTotals?: Record<Vendor, number>
): Record<
  Vendor,
  {
    rooms: number;
    bundles: number;
    project: number;
    matrix: number;
    other: number;
    total: number;
  }
> {
  const out: Record<
    Vendor,
    {
      rooms: number;
      bundles: number;
      project: number;
      matrix: number;
      other: number;
      total: number;
    }
  > = {};
  for (const vendor of vendors) {
    const rooms = spaceTier.reduce((sum, row) => sum + amountOf(row, vendor), 0);
    const bundles = bundleTier.reduce((sum, row) => {
      if ((row.basis?.[vendor] ?? "none") !== "bundle") return sum;
      return sum + amountOf(row, vendor);
    }, 0);
    const project = projectTier.reduce(
      (sum, row) => sum + amountOf(row, vendor),
      0
    );
    const matrix = rooms + bundles + project;
    const quoted = Number(quotedTotals?.[vendor]);
    const total = Number.isFinite(quoted) && quoted > 0 ? quoted : matrix;
    out[vendor] = {
      rooms,
      bundles,
      project,
      matrix,
      other: Math.max(0, Math.round(total) - Math.round(matrix)),
      total: Math.round(total),
    };
  }
  return out;
}

/**
 * Split a cell status into its parts. `"incl_in_bundle:Hardware"` carries the
 * bundle name after the colon so the UI can name it without a second lookup.
 */
export function parseCellStatus(raw: string | undefined): {
  status: CoverageStatus;
  bundleLabel: string;
} {
  const value = String(raw ?? "");
  if (value.startsWith("incl_in_bundle")) {
    const [, label = ""] = value.split(":");
    return { status: "incl_in_bundle", bundleLabel: label.trim() };
  }
  if (value === "quoted") return { status: "quoted", bundleLabel: "" };
  return { status: "not_quoted", bundleLabel: "" };
}
