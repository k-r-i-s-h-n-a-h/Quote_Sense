/** Comparison matrix grouping: category → canonical space → sub-service rows. */

export type CompareTableRow = Record<string, unknown>;

export type SubGroup = { sub: string; rows: CompareTableRow[] };
export type SpaceGroup = { space: string; spaceRaw: string; subs: SubGroup[] };
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

/** Sum amounts for vendors across rows (space header or sub-service). */
export function sumSubServiceRow(
  rows: CompareTableRow[],
  vendors: string[]
): AmountTotals {
  const totals: AmountTotals = {};
  for (const v of vendors) totals[v] = 0;

  for (const row of rows) {
    for (const v of vendors) {
      totals[v] += Number(row[v]) || 0;
    }
  }

  for (const v of vendors) {
    totals[v] = totals[v] > 0 ? roundInr(totals[v]) : 0;
  }

  return totals;
}

export function groupTableData(rows: CompareTableRow[]): CatGroup[] {
  const cats: CatGroup[] = [];
  const catIdx = new Map<string, number>();
  const spaceIdx = new Map<string, number>();
  const subIdx = new Map<string, number>();

  for (const item of rows) {
    const category = String(item.category || "Other");
    const space = spaceOf(item);
    const spaceRaw = String(item.space_raw || "").trim();
    const sub = String(item.sub_service || item.item_name || "General");

    if (!catIdx.has(category)) {
      catIdx.set(category, cats.length);
      cats.push({ category, spaces: [] });
    }
    const cat = cats[catIdx.get(category)!];

    const spaceKey = `${category}||${space}`;
    if (!spaceIdx.has(spaceKey)) {
      spaceIdx.set(spaceKey, cat.spaces.length);
      cat.spaces.push({ space, spaceRaw, subs: [] });
    }
    const spaceGroup = cat.spaces[spaceIdx.get(spaceKey)!];
    if (spaceRaw && !spaceGroup.spaceRaw.includes(spaceRaw)) {
      spaceGroup.spaceRaw = [spaceGroup.spaceRaw, spaceRaw].filter(Boolean).join(" · ");
    }

    const subKey = `${spaceKey}||${sub}`;
    if (!subIdx.has(subKey)) {
      subIdx.set(subKey, spaceGroup.subs.length);
      spaceGroup.subs.push({ sub, rows: [] });
    }
    spaceGroup.subs[subIdx.get(subKey)!].rows.push(item);
  }
  return cats;
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
