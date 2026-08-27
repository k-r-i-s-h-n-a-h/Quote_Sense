/**
 * F0 — TypeScript mirror of the backend MatrixV1 payload.
 *
 * Backend source of truth: backend/docs/plan/00-contracts.md
 * See frontend/docs/plan/00-contracts.md for why this file exists.
 *
 * Every tier field is optional so the frontend can be deployed ahead of the
 * backend: a payload carrying only the legacy flat `tableData` still renders.
 */

import type { VendorLabel, VendorMeta } from "./format";

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
  /** S4 family, e.g. "lighting" — used to hide Whole-home recap duplicates. */
  bundle_family?: string;
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
  /** Where this vendor's recap amount actually lives: rooms vs whole home. */
  placement?: Record<Vendor, "space" | "project" | "bundle" | "mixed" | "none">;
  /** Plain-English package vs itemised note. Absent on scattered recaps. */
  takeaway?: { kind?: "package_higher" | "package_lower"; text?: string };
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

/**
 * Whole-home rows to paint. Accounting still uses the full project tier.
 *
 * A scattered recap ("Same work, different spaces") already compares a family
 * that one vendor parked in Whole home. Showing those rupees again there looks
 * like a second add. Rows with no family, or a family the recap does not
 * cover (blinds, tissue), stay visible.
 *
 * `bundle_family` is the primary signal. When an older payload omits it, infer
 * lighting/hardware from the work key and labels so Electrical Work / Per Point
 * does not repeat under Whole home after the recap already compared it.
 */
export function familyOfProjectRow(row: SpaceRow): string {
  const explicit = String(row.bundle_family || "").trim();
  if (explicit) return explicit;
  const key = String(row.work_key || "");
  const slug = (key.includes(":") ? key.split(":")[1] : key).replace(/_/g, " ");
  const blob = [slug, row.sub_service, row.item_name, row.work_item]
    .map((v) => String(v || ""))
    .join(" ");
  if (
    /\blight|electrical|adaptor|adapter|spot light|profile light|strip light|point creation/i.test(
      blob
    )
  ) {
    return "lighting";
  }
  if (
    /\bhardware|tandem|soft clos|pullout|pull out|cutlery|gola|skid mat|accessor/i.test(
      blob
    )
  ) {
    return "hardware";
  }
  return "";
}

export function projectRowsForDisplay(
  projectRows: SpaceRow[],
  bundleRows: BundleRow[]
): SpaceRow[] {
  const { scattered } = partitionBundleRows(bundleRows);
  const recapped = new Set(
    scattered
      .map((row) => String(row.bundle_family || "").trim())
      .filter(Boolean)
  );
  if (recapped.size === 0) return projectRows;
  return projectRows.filter((row) => {
    const family = familyOfProjectRow(row);
    return !family || !recapped.has(family);
  });
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

export type RecapPlacement = "space" | "project" | "bundle" | "mixed" | "none";

export function inferRecapPlacement(
  row: BundleRow,
  vendor: Vendor,
  spaceRows: SpaceRow[] = [],
  projectRows: SpaceRow[] = []
): RecapPlacement {
  const explicit = row.placement?.[vendor];
  if (explicit) return explicit;
  if ((row.basis?.[vendor] ?? "none") === "bundle") return "bundle";
  if ((row.basis?.[vendor] ?? "none") === "none" || amountOf(row, vendor) <= 0) {
    return "none";
  }
  const family = String(row.bundle_family || "").trim();
  if (!family) return "none";
  const inFamily = (rows: SpaceRow[]) =>
    rows.some(
      (r) => familyOfProjectRow(r) === family && amountOf(r, vendor) > 0
    );
  const inSpace = inFamily(spaceRows);
  const inProject = inFamily(projectRows);
  if (inSpace && inProject) return "mixed";
  if (inProject) return "project";
  if (inSpace) return "space";
  return "none";
}

export function withInferredPlacement(
  row: BundleRow,
  vendors: Vendor[],
  spaceRows: SpaceRow[] = [],
  projectRows: SpaceRow[] = []
): BundleRow {
  const placement: Record<Vendor, RecapPlacement> = {};
  for (const vendor of vendors) {
    placement[vendor] = inferRecapPlacement(
      row,
      vendor,
      spaceRows,
      projectRows
    );
  }
  return { ...row, placement };
}

export function vendorsShareCompany(
  vendors: Vendor[],
  labels: Record<string, VendorLabel>
): boolean {
  const names = vendors
    .map((v) => (labels[v]?.company || "").trim())
    .filter(Boolean);
  return names.length > 1 && new Set(names).size < names.length;
}

export function recapVendorCallout(
  vendor: Vendor,
  labels: Record<string, VendorLabel>,
  sameCompany: boolean
): string {
  const label = labels[vendor];
  if (sameCompany && label?.quoteNumber) return `#${label.quoteNumber}`;
  return (label?.company || "").trim() || vendor;
}

export type GstMode = "exclusive" | "inclusive" | "mixed";

export function gstModeOf(meta?: VendorMeta): GstMode | "" {
  const mode = String(meta?.gst_mode || "").trim();
  if (mode === "exclusive" || mode === "inclusive" || mode === "mixed") {
    return mode;
  }
  return "";
}

/** Short column chip — how the vendor entered, not what the cell shows. */
export function gstEntryChip(mode: GstMode | ""): string {
  if (mode === "exclusive") return "Entered excl. GST";
  if (mode === "inclusive") return "Entered incl. GST";
  if (mode === "mixed") return "GST mixed in quote";
  return "";
}

export function gstModesDiffer(
  vendors: Vendor[],
  meta: Record<string, VendorMeta> = {}
): boolean {
  const modes = new Set(
    vendors
      .map((v) => gstModeOf(meta[v]))
      .filter((m): m is "exclusive" | "inclusive" => m === "exclusive" || m === "inclusive")
  );
  return modes.has("exclusive") && modes.has("inclusive");
}

/**
 * Top-of-matrix note when one quote was entered excluding GST and another
 * including GST. Amounts themselves stay the billed grandTotal.
 */
export function gstCompareBanner(
  vendors: Vendor[],
  meta: Record<string, VendorMeta> = {},
  labels: Record<string, VendorLabel> = {}
): string {
  if (!gstModesDiffer(vendors, meta)) return "";
  const sameCompany = vendorsShareCompany(vendors, labels);
  const bits = vendors
    .map((vendor) => {
      const mode = gstModeOf(meta[vendor]);
      const who = recapVendorCallout(vendor, labels, sameCompany);
      if (mode === "exclusive") return `${who} was entered excluding GST`;
      if (mode === "inclusive") return `${who} was entered including GST`;
      return "";
    })
    .filter(Boolean);
  if (bits.length === 0) return "";
  return `${bits.join("; ")}. Amounts below include GST so the columns can be compared.`;
}

/** Where this recap amount should be read — spaces vs this quote. */
export function recapPlacementNote(
  row: BundleRow,
  vendor: Vendor,
  labels: Record<string, VendorLabel> = {},
  sameCompany = false
): string {
  const who = recapVendorCallout(vendor, labels, sameCompany);
  const placement = row.placement?.[vendor];
  if (placement === "space") {
    return `${who}: already in the spaces above — comparison only`;
  }
  if (placement === "project") {
    return `${who}: one whole-home figure — included in this quote, not in the space sums`;
  }
  if (placement === "bundle") {
    return `${who}: package price — in Lump sum packages, not in space totals`;
  }
  if (placement === "mixed") {
    return `${who}: split across spaces and Whole home — counted once in this quote`;
  }
  return "";
}

export function recapPlacementNotes(
  row: BundleRow,
  vendors: Vendor[],
  labels: Record<string, VendorLabel> = {}
): string[] {
  const withAmount = vendors.filter((v) => amountOf(row, v) > 0);
  const places = new Set(
    withAmount.map((v) => row.placement?.[v]).filter(Boolean)
  );
  if (places.size < 2) return [];
  const sameCompany = vendorsShareCompany(vendors, labels);
  return withAmount
    .map((v) => recapPlacementNote(row, v, labels, sameCompany))
    .filter(Boolean);
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
