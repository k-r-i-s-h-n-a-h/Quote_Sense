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
export type CoverageStatus =
  | "quoted"
  | "incl_in_bundle"
  | "incl_in_parent"
  | "not_quoted";

export type VendorMeasures = {
  quantity?: number;
  rate?: number;
  pricing_method?: string;
  description?: string;
};

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
  contained_in?: string;
  measures?: Record<Vendor, VendorMeasures>;
  /** Deterministic row-wise why-this-gap sentence from S5. */
  summary?: string;
  /** Other vendor named this ancillary work in a Civil/other description. */
  named_in?: Record<
    Vendor,
    {
      label?: string;
      amount?: number;
      space?: string;
      intent?: string;
      also_names?: string[];
    }
  >;
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
  parent_space_id?: string;
  parent_space?: string;
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
  if (value.startsWith("incl_in_parent")) {
    const [, label = ""] = value.split(":");
    return { status: "incl_in_parent", bundleLabel: label.trim() };
  }
  if (value === "quoted") return { status: "quoted", bundleLabel: "" };
  return { status: "not_quoted", bundleLabel: "" };
}

function whoOf(vendor: Vendor): string {
  return vendor.split(" (")[0].trim() || vendor;
}

function vendorRefs(vendors: Vendor[]): Record<Vendor, string> {
  const bases = vendors.map((vendor) => whoOf(vendor));
  const counts = new Map<string, number>();
  for (const name of bases) {
    const key = name.toLowerCase();
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return Object.fromEntries(
    vendors.map((vendor, index) => {
      const name = bases[index];
      const duplicate = (counts.get(name.toLowerCase()) || 0) > 1;
      return [vendor, duplicate ? `${name} Q${index + 1}` : name];
    })
  );
}

function qtyUnit(pricingMethod: string): string {
  const pm = pricingMethod.toLowerCase();
  if (pm.includes("sq ft") || pm.includes("sqft") || pm.includes("sq.ft")) {
    return "sqft";
  }
  if (pm.includes("sq m") || pm.includes("sqm")) return "sqm";
  if (pm.includes("rft") || pm.includes("running")) return "rft";
  return "units";
}

function inrDelta(amount: number): string {
  const n = Math.round(Number(amount) || 0);
  return `₹${n.toLocaleString("en-IN")}`;
}

const SPEC_TERMS: [string, string][] = [
  ["hi-gloss", "hi-gloss"],
  ["hi gloss", "hi-gloss"],
  ["high gloss", "hi-gloss"],
  ["hdhmr", "HDHMR"],
  ["greenply", "Greenply"],
  ["century", "Century"],
  ["merino", "Merino"],
  ["hettich", "Hettich"],
  ["hafele", "Hafele"],
  ["laminates", "laminates"],
  ["laminate", "laminate"],
  ["louvers", "louvers"],
  ["louver", "louver"],
  ["louvres", "louvers"],
  ["louvre", "louver"],
  ["plywood", "plywood"],
  ["beeding", "beeding"],
  ["beading", "beading"],
  ["membrane", "membrane"],
  ["veneer", "veneer"],
  ["acrylic", "acrylic"],
  ["premium", "premium"],
  ["mirror", "mirror"],
  ["glass", "glass"],
  ["walnut", "walnut"],
  ["blum", "Blum"],
  ["matt", "matt"],
  ["matte", "matte"],
  ["teak", "teak"],
  ["oak", "oak"],
  ["pvc", "PVC"],
  ["mdf", "MDF"],
  ["pu finish", "PU finish"],
];

function specTokens(description: string): string[] {
  const text = String(description || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return [];
  const folded = text.toLowerCase();
  const found: string[] = [];
  const seen = new Set<string>();
  for (const [term, label] of SPEC_TERMS) {
    if (seen.has(label.toLowerCase())) continue;
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (!new RegExp(`(?<![a-z0-9])${escaped}(?![a-z0-9])`, "i").test(folded)) {
      continue;
    }
    found.push(label);
    seen.add(label.toLowerCase());
    if (found.length >= 4) break;
  }
  return found;
}

function specClause(
  ma: VendorMeasures,
  mb: VendorMeasures,
  a: Vendor,
  b: Vendor
): string {
  const ta = specTokens(String(ma.description || ""));
  const tb = specTokens(String(mb.description || ""));
  if (!ta.length && !tb.length) return "";
  const same =
    ta.length &&
    tb.length &&
    ta.map((x) => x.toLowerCase()).sort().join("|") ===
      tb.map((x) => x.toLowerCase()).sort().join("|");
  if (same) return "";
  const bits: string[] = [];
  if (ta.length) bits.push(`${whoOf(a)} specified ${ta.join(", ")}`);
  if (tb.length) bits.push(`${whoOf(b)} specified ${tb.join(", ")}`);
  return bits.join("; ");
}

function qtyRateParts(
  qtyA: number,
  qtyB: number,
  rateA: number,
  rateB: number,
  unit: string,
  a: Vendor,
  b: Vendor
): string[] {
  const parts: string[] = [];
  let qtyGap = false;
  if (qtyA > 0 && qtyB > 0) {
    const mid = (qtyA + qtyB) / 2;
    qtyGap = Boolean(mid && Math.abs(qtyA - qtyB) / mid >= 0.1);
    if (qtyGap) {
      const more = qtyA > qtyB ? a : b;
      parts.push(
        `${whoOf(a)}: ${qtyA} ${unit}; ${whoOf(b)}: ${qtyB} ${unit} ` +
          `(${whoOf(more)} billed more area)`
      );
    }
  }
  if (rateA > 0 && rateB > 0) {
    const rmid = (rateA + rateB) / 2;
    if (rmid && Math.abs(rateA - rateB) / rmid >= 0.1) {
      const higher = rateA > rateB ? a : b;
      const rates =
        `${whoOf(a)}: ${inrDelta(rateA)}/${unit}; ` +
        `${whoOf(b)}: ${inrDelta(rateB)}/${unit}`;
      if (qtyGap) {
        parts.push(rates);
      } else if (qtyA > 0 && qtyB > 0) {
        parts.push(`same area, ${whoOf(higher)}'s rate is higher (${rates})`);
      } else {
        parts.push(`${whoOf(higher)}'s rate is higher (${rates})`);
      }
    }
  }
  return parts;
}

function measureOf(row: SpaceRow, vendor: Vendor): VendorMeasures {
  const bag = row.measures;
  if (!bag) return {};
  if (bag[vendor]) return bag[vendor];
  const who = vendor.split(" (")[0].trim().toLowerCase();
  for (const [key, value] of Object.entries(bag)) {
    if (key.split(" (")[0].trim().toLowerCase() === who) return value || {};
  }
  return {};
}

/**
 * Row-wise Comparison Summary. Prefers S5 `row.summary` when it already
 * names a qty/rate/spec reason; otherwise composes from amounts, measures,
 * and coverage so every work row can show why, not only the money gap.
 */
export function rowComparisonSummary(
  row: SpaceRow,
  vendors: Vendor[]
): string {
  if (vendors.length < 2) return "";

  const refs = vendorRefs(vendors);
  const elsewhere: string[] = [];
  const gaps: Vendor[] = [];
  const quoted: Vendor[] = [];
  for (const vendor of vendors) {
    const { status, bundleLabel } = parseCellStatus(row.coverage?.[vendor]);
    if (status === "incl_in_parent") {
      elsewhere.push(
        `${refs[vendor]}'s figure is inside ${bundleLabel || "another space"}`
      );
    } else if (status === "incl_in_bundle") {
      elsewhere.push(
        `${refs[vendor]}'s figure is inside ${bundleLabel || "a package"}`
      );
    } else if (amountOf(row, vendor) > 0 || status === "quoted") {
      quoted.push(vendor);
    } else {
      gaps.push(vendor);
    }
  }
  if (elsewhere.length) return elsewhere.join("; ");
  if (quoted.length === 1 && gaps.length) {
    const shipped = String(row.summary || "").trim();
    if (shipped) return shipped;
    return `${refs[gaps[0]]} did not quote this line`;
  }
  if (quoted.length < 2) return "";

  const a = quoted[0];
  const b = quoted[1];
  const amtA = amountOf(row, a);
  const amtB = amountOf(row, b);
  const ma = measureOf(row, a);
  const mb = measureOf(row, b);
  const qtyA = Number(ma.quantity) || 0;
  const qtyB = Number(mb.quantity) || 0;
  const rateA = Number(ma.rate) || 0;
  const rateB = Number(mb.rate) || 0;
  const unit = qtyUnit(String(ma.pricing_method || mb.pricing_method || ""));

  const amountClause =
    Math.abs(amtA - amtB) < 1
      ? "Same amount"
      : `${refs[amtA > amtB ? a : b]} is ${inrDelta(Math.abs(amtA - amtB))} higher`;

  const reasons = qtyRateParts(
    qtyA,
    qtyB,
    rateA,
    rateB,
    unit,
    refs[a],
    refs[b]
  );
  const spec = specClause(ma, mb, refs[a], refs[b]);
  if (spec) reasons.push(spec);
  if (!reasons.length) {
    const shipped = String(row.summary || "").trim();
    return shipped || amountClause;
  }
  return `${amountClause} — ${reasons.join(" · ")}`;
}

export type SpaceHeaderSummaryOpts = {
  itemCounts?: Record<string, number>;
  exclusiveLabels?: Record<string, string[]>;
  comparable?: boolean;
};

function amountDeltaClause(
  totals: Record<Vendor, number>,
  vendors: Vendor[],
  skipGap: boolean,
  refs: Record<Vendor, string>
): string {
  if (vendors.length < 2) return "";
  const quoted = vendors.filter((v) => (Number(totals[v]) || 0) > 0);
  const gaps = vendors.filter((v) => (Number(totals[v]) || 0) <= 0);
  if (quoted.length === 1 && gaps.length) {
    return skipGap ? "" : `${refs[gaps[0]]} did not quote this line`;
  }
  if (quoted.length < 2) return "";
  const a = quoted[0];
  const b = quoted[1];
  const amtA = Number(totals[a]) || 0;
  const amtB = Number(totals[b]) || 0;
  if (Math.abs(amtA - amtB) < 1) return "Same amount";
  const higher = amtA > amtB ? a : b;
  return `${refs[higher]} is ${inrDelta(Math.abs(amtA - amtB))} higher`;
}

function itemCountReason(
  totals: Record<Vendor, number>,
  vendors: Vendor[],
  itemCounts: Record<string, number> | undefined,
  refs: Record<Vendor, string>
): string {
  if (!itemCounts || vendors.length < 2) return "";
  const quoted = vendors.filter((v) => (Number(totals[v]) || 0) > 0);
  if (quoted.length < 2) return "";
  const a = quoted[0];
  const b = quoted[1];
  const nA = Number(itemCounts[a]) || 0;
  const nB = Number(itemCounts[b]) || 0;
  if (nA === nB || (nA === 0 && nB === 0)) return "";
  const amtA = Number(totals[a]) || 0;
  const amtB = Number(totals[b]) || 0;
  const higher = amtA >= amtB ? a : b;
  const higherN = higher === a ? nA : nB;
  const otherN = higher === a ? nB : nA;
  let text = `${nA} items vs ${nB}`;
  if (higherN < otherN) {
    text += ` — ${refs[higher]} charged more for fewer lines`;
  }
  return text;
}

function exclusiveReason(
  vendors: Vendor[],
  exclusiveLabels: Record<string, string[]> | undefined,
  refs: Record<Vendor, string>
): string[] {
  if (!exclusiveLabels) return [];
  const parts: string[] = [];
  for (const vendor of vendors) {
    const labels = (exclusiveLabels[vendor] || []).filter(Boolean).slice(0, 3);
    if (!labels.length) continue;
    parts.push(`${refs[vendor]} also quoted ${labels.join(", ")}`);
  }
  return parts;
}

/** Space-header summary: amount plus why (counts, exclusives, scopes). */
export function spaceHeaderSummary(
  totals: Record<Vendor, number>,
  vendors: Vendor[],
  coverageForSpace: CoverageEntry[],
  opts?: SpaceHeaderSummaryOpts
): string {
  const refs = vendorRefs(vendors);
  const parentNotes = coverageForSpace
    .filter((e) => e.status === "incl_in_parent")
    .map(
      (e) =>
        `${refs[e.vendor] || whoOf(e.vendor)}'s figure is inside ${e.parent_space || "another space"}`
    );
  const bundleNotes = coverageForSpace
    .filter((e) => e.status === "incl_in_bundle")
    .map(
      (e) =>
        `${refs[e.vendor] || whoOf(e.vendor)}'s figure is inside ${e.bundle_label || "a package"}`
    );
  const hasBundle = coverageForSpace.some((e) => e.status === "incl_in_bundle");
  const skipGap = parentNotes.length > 0 || bundleNotes.length > 0;

  const parts: string[] = [];
  const amount = amountDeltaClause(totals, vendors, skipGap, refs);
  if (amount) parts.push(amount);

  if (opts?.comparable === false) {
    parts.push(
      hasBundle ? "scopes differ (package vs itemised)" : "scopes differ"
    );
  }

  const counts = itemCountReason(totals, vendors, opts?.itemCounts, refs);
  if (counts) parts.push(counts);

  parts.push(...exclusiveReason(vendors, opts?.exclusiveLabels, refs));
  parts.push(...parentNotes);
  if (opts?.comparable !== false) parts.push(...bundleNotes);

  return parts.join(" · ");
}
