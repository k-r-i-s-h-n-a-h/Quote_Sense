# F0 — Frontend contracts

TypeScript mirror of the backend `MatrixV1` payload.
Backend source of truth: [../../../backend/docs/plan/00-contracts.md](../../../backend/docs/plan/00-contracts.md).

**Module:** `lib/compare-types.ts`.

---

## The problem this solves

Comparison data was untyped. `compare-matrix.ts` used
`Record<string, unknown>`, and `app/compare/page.tsx` held it as `useState<any[]>`.
Row field names were string literals scattered across four files, so a backend
field rename was invisible to the type checker and surfaced as a blank cell in the
UI.

With the pipeline now shipping `work_key`, `space_id`, `scope` and coverage, that
was no longer sustainable — these fields carry meaning that the UI must get right
or it will state something false.

## Types

```ts
export type Vendor = string;                  // matrix column key
export type CoverageStatus = "quoted" | "incl_in_bundle" | "incl_in_parent" | "not_quoted";
export type PriceBasis = "bundle" | "itemized" | "none";

export interface SpaceRow {
  category: string;
  space_id: string;
  space: string;
  space_raw: string;
  work_key: string;
  sub_service: string;
  pricing_method?: string;
  breakdown?: { vendor: string; item: string; amount: number }[];
  contained_in?: string;
  measures?: Record<Vendor, { quantity?: number; rate?: number; pricing_method?: string }>;
  summary?: string;
  [vendor: string]: unknown;                  // per-vendor amounts
}

export interface BundleRow {
  bundle_id: string;
  bundle_label: string;
  bundle_family: string;
  covered_spaces: string[];
  covered_items: string[];
  overlap_flags: string[];
  basis: Record<Vendor, PriceBasis>;
  placement?: Record<Vendor, "space" | "project" | "bundle" | "mixed" | "none">;
  takeaway?: { kind?: string; text?: string };
  [vendor: string]: unknown;
}

export interface CoverageEntry {
  space_id: string;
  space: string;
  vendor: Vendor;
  status: CoverageStatus;
  bundle_id?: string;
  comparable: boolean;
  parent_space?: string;
}

export interface MatrixV1 {
  contract_version?: "MatrixV1";
  vendors: Vendor[];
  vendorMeta?: Record<Vendor, VendorMeta>;
  chartData?: { vendor: string; total: number }[];
  spaceTier?: SpaceRow[];
  bundleTier?: BundleRow[];
  projectTier?: SpaceRow[];
  coverage?: CoverageEntry[];
  tableData?: SpaceRow[];                     // legacy flat shape
  report?: string;
  session_id?: string;
}
```

The index signature on the row types is unavoidable: vendor names are dynamic
column keys, not a fixed schema. It is narrowed by always reading amounts through
a helper (`amountOf(row, vendor)`) rather than indexing inline, so the unsafe
access lives in one place.

## Reading amounts

```ts
export function amountOf(row: SpaceRow | BundleRow, vendor: Vendor): number {
  const n = Number(row[vendor]);
  return Number.isFinite(n) ? n : 0;
}
```

Every component uses this. Direct `row[vendor]` indexing is what previously
allowed `NaN` to reach the DOM as a blank cell.

## Optional fields and the fallback path

Every tier field is optional. A payload from an older backend has `tableData`
only, and the accessors below resolve it transparently:

```ts
spaceRowsOf(m)  = m.spaceTier  ?? m.tableData?.filter(notProjectLevel) ?? []
bundleRowsOf(m) = m.bundleTier ?? []
coverageOf(m)   = m.coverage   ?? []
```

An empty `bundleTier` and an empty `coverage` degrade to exactly the old
behaviour: no bundle section, and zero rendered as `N/A`. That is the
compatibility guarantee — a stale backend produces the previous UI, never a
broken one.

## Adding a field

Additive only. Add it optional here, document it in the backend contract file in
the same commit, and give every reader a defined fallback. Do not make a new
field required — the frontend can be deployed ahead of the backend.

---

## What to change if this stage breaks

**Symptom: a cell is blank or `NaN`.**
Something bypassed `amountOf`. Grep for `[vendor]` indexing.

**Symptom: type errors after a backend change.**
Correct behaviour — this is the file doing its job. Update the interface here
first, then fix the readers the compiler points at.

**Symptom: the UI renders nothing at all.**
Check `contract_version` and whether the tier accessors found their fallback. A
payload with neither tiers nor `tableData` is a backend failure, not a UI one.
