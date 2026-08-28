/**
 * F2 — Comparison matrix grouping: category -> canonical space -> work row.
 *
 * Grouping keys on `space_id` and `work_key`, which the backend already
 * resolved. The previous version keyed the sub-service level on the raw display
 * string, which duplicated the backend's identity decision and did it badly: a
 * label is not an identifier, so `Side table` and `Side Table` were split.
 *
 * The `||` fallbacks keep a legacy payload (no `space_id` / `work_key`) grouping
 * exactly as it used to, which is what lets the frontend deploy independently.
 *
 * See frontend/docs/plan/02-grouping.md.
 */

import {
  amountOf,
  type CoverageEntry,
  type MatrixV1,
  type SpaceRow,
  type Vendor,
} from "./compare-types";

export type CompareTableRow = SpaceRow;

export type SubGroup = {
  /** Display label. */
  sub: string;
  /** Canonical work key, or the label when absent. */
  workKey: string;
  rows: CompareTableRow[];
};

export type SpaceGroup = {
  space: string;
  spaceId: string;
  /** Distinct vendor wordings that folded into this space. */
  spaceRaw: string;
  subs: SubGroup[];
};

export type CatGroup = { category: string; spaces: SpaceGroup[] };

export type AmountTotals = {
  [vendor: string]: number;
};

function roundInr(value: number): number {
  const n = Math.round(Number(value));
  return Number.isFinite(n) ? n : 0;
}

function spaceOf(row: CompareTableRow): string {
  return String(row.space || row.room || "Project-level").trim() || "Project-level";
}

function spaceIdOf(row: CompareTableRow): string {
  const id = String(row.space_id ?? "").trim();
  return id || spaceOf(row);
}

function subLabelOf(row: CompareTableRow): string {
  return String(row.sub_service || row.item_name || "General");
}

function workKeyOf(row: CompareTableRow): string {
  const key = String(row.work_key ?? "").trim();
  return key || subLabelOf(row);
}

/** Sum amounts for vendors across rows (space header or work row). */
export function sumSubServiceRow(
  rows: CompareTableRow[],
  vendors: string[]
): AmountTotals {
  const totals: AmountTotals = {};
  for (const v of vendors) totals[v] = 0;

  for (const row of rows) {
    for (const v of vendors) {
      totals[v] += amountOf(row, v);
    }
  }

  for (const v of vendors) {
    totals[v] = totals[v] > 0 ? roundInr(totals[v]) : 0;
  }

  return totals;
}

/** How many work rows in this space have a positive amount for each vendor. */
export function quotedWorkCounts(
  spaceGroup: SpaceGroup,
  vendors: string[]
): AmountTotals {
  const counts: AmountTotals = {};
  for (const v of vendors) counts[v] = 0;
  for (const sub of spaceGroup.subs) {
    const totals = sumSubServiceRow(sub.rows, vendors);
    for (const v of vendors) {
      if ((totals[v] || 0) > 0) counts[v] += 1;
    }
  }
  return counts;
}

/**
 * Nest rows for rendering. Insertion-ordered throughout: the backend already
 * sorted rows into quote-reading order, so this must never sort.
 */
export function groupTableData(rows: CompareTableRow[]): CatGroup[] {
  const cats: CatGroup[] = [];
  const catIdx = new Map<string, number>();
  const spacesById = new Map<string, SpaceGroup>();
  const subIdx = new Map<string, number>();

  for (const item of rows) {
    const category = String(item.category || "Other");
    const space = spaceOf(item);
    const spaceId = spaceIdOf(item);
    const spaceRaw = String(item.space_raw || "").trim();
    const sub = subLabelOf(item);
    const workKey = workKeyOf(item);

    if (!catIdx.has(category)) {
      catIdx.set(category, cats.length);
      cats.push({ category, spaces: [] });
    }
    const cat = cats[catIdx.get(category)!];

    // Key on space_id only — not category — so Living / L R / LVR cannot split
    // across service categories. Customers need one spend total per room.
    let spaceGroup = spacesById.get(spaceId);
    if (!spaceGroup) {
      spaceGroup = { space, spaceId, spaceRaw, subs: [] };
      cat.spaces.push(spaceGroup);
      spacesById.set(spaceId, spaceGroup);
    }
    if (spaceRaw && !spaceGroup.spaceRaw.includes(spaceRaw)) {
      spaceGroup.spaceRaw = [spaceGroup.spaceRaw, spaceRaw].filter(Boolean).join(" · ");
    }

    const subKey = `${spaceId}||${workKey}`;
    if (!subIdx.has(subKey)) {
      subIdx.set(subKey, spaceGroup.subs.length);
      spaceGroup.subs.push({ sub, workKey, rows: [] });
    }
    spaceGroup.subs[subIdx.get(subKey)!].rows.push(item);
  }
  return cats.filter((c) => c.spaces.length > 0);
}

/**
 * Coverage lookup keyed `${space_id}||${vendor}`. A Map because the matrix
 * queries it once per header cell.
 */
export function coverageIndex(
  entries: CoverageEntry[]
): Map<string, CoverageEntry> {
  const index = new Map<string, CoverageEntry>();
  for (const entry of entries) {
    index.set(`${entry.space_id}||${entry.vendor}`, entry);
  }
  return index;
}

/** True when every vendor's total for this space is a like-for-like figure. */
export function isSpaceComparable(
  index: Map<string, CoverageEntry>,
  spaceId: string,
  vendors: Vendor[]
): boolean {
  for (const vendor of vendors) {
    const entry = index.get(`${spaceId}||${vendor}`);
    if (entry && !entry.comparable) return false;
  }
  return true;
}

export function lineItemDescription(row: CompareTableRow): {
  title: string;
  room: string;
} {
  const title = String(row.item_name || row.sub_service || row.work_item || "").trim();
  const space = spaceOf(row);
  if (!space || space.toLowerCase() === title.toLowerCase()) {
    return { title, room: "" };
  }
  return { title, room: space };
}

/** Convenience for callers holding a whole payload rather than loose rows. */
export function groupMatrix(matrix: MatrixV1): CatGroup[] {
  return groupTableData(matrix.spaceTier ?? matrix.tableData ?? []);
}
