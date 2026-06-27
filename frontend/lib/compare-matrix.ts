/** Comparison matrix grouping + sub-service totals (line items stay visible). */

export type CompareTableRow = Record<string, unknown>;

export type SubGroup = { sub: string; rows: CompareTableRow[] };
export type CatGroup = { category: string; subs: SubGroup[] };

export type SubServiceTotals = {
  moving_average: number;
  moving_weight: number;
  [vendor: string]: number;
};

function roundInr(value: number): number {
  const n = Math.round(Number(value));
  return Number.isFinite(n) ? n : 0;
}

/** Sum line-item amounts under one sub-service for the sub-service header row. */
export function sumSubServiceRow(
  rows: CompareTableRow[],
  vendors: string[]
): SubServiceTotals {
  let movingSum = 0;
  let movingWeight = 0;

  const totals: SubServiceTotals = {
    moving_average: 0,
    moving_weight: 0,
  };

  for (const v of vendors) totals[v] = 0;

  for (const row of rows) {
    movingSum += Number(row.moving_average ?? row.market_average) || 0;
    movingWeight = Math.max(movingWeight, Number(row.moving_weight) || 0);
    for (const v of vendors) {
      totals[v] += Number(row[v]) || 0;
    }
  }

  totals.moving_average = movingSum > 0 ? roundInr(movingSum) : 0;
  totals.moving_weight = movingWeight;

  for (const v of vendors) {
    totals[v] = totals[v] > 0 ? roundInr(totals[v]) : 0;
  }

  return totals;
}

export function groupTableData(rows: CompareTableRow[]): CatGroup[] {
  const cats: CatGroup[] = [];
  const catIdx = new Map<string, number>();
  const subIdx = new Map<string, number>();

  for (const item of rows) {
    const category = String(item.category || "Other");
    const sub = String(item.sub_service || "General");

    if (!catIdx.has(category)) {
      catIdx.set(category, cats.length);
      cats.push({ category, subs: [] });
    }
    const cat = cats[catIdx.get(category)!];

    const subKey = `${category}||${sub}`;
    if (!subIdx.has(subKey)) {
      subIdx.set(subKey, cat.subs.length);
      cat.subs.push({ sub, rows: [] });
    }
    cat.subs[subIdx.get(subKey)!].rows.push(item);
  }
  return cats;
}

export function lineItemDescription(row: CompareTableRow): {
  title: string;
  room: string;
} {
  const title = String(row.item_name || row.work_item || row.sub_service || "").trim();
  const room = String(row.room || "").trim();
  if (!room || room.toLowerCase() === title.toLowerCase()) {
    return { title, room: "" };
  }
  return { title, room };
}
