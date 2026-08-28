# F2 — Grouping

Nest flat matrix rows into the render hierarchy.

**Input:** `MatrixV1`.
**Output:** `CatGroup[]` plus bundle and coverage lookups.

**Module:** `lib/compare-matrix.ts`.

---

## The problem this solves

`groupTableData` keyed its sub-service level on the raw display string:

```ts
const sub = String(item.sub_service || item.item_name || "General");
const subKey = `${spaceKey}||${sub}`;
```

Two consequences. First, it duplicated the identity decision the backend had
already made — badly, because a display label is not an identifier. Second, if
the backend ever merged two vendor labels into one row while the labels still
differed, the frontend would split them again.

Now the backend ships `work_key` and `space_id`. The frontend groups on those and
uses the label only for display.

## Hierarchy

```
category
  └─ space          (keyed on space_id, labelled with space)
       └─ work row  (keyed on work_key, labelled with sub_service)
```

Order is preserved from the payload — the backend already sorted rows into
quote-reading order, so grouping must be insertion-ordered and must not sort.

Spaces are keyed on `space_id` **only**, not `category||space_id`. A living-room
TV unit and living-room wallpaper must land in one section even if their
service category strings differ. Splitting by category was how one room became
four blocks.

## Keying

```ts
const spaceKey = `${category}||${row.space_id || spaceOf(row)}`;
const workKey  = `${spaceKey}||${row.work_key || subLabelOf(row)}`;
```

The `||` fallbacks are the legacy path: an older payload without `space_id` or
`work_key` groups exactly as it used to. That is what lets the frontend deploy
ahead of the backend.

## Space aliases

A space group collects the distinct `space_raw` strings that contributed to it, so
the header can show `Master Bedroom` with `MBR Dressing unit · Used cloth unit ·
MBR Study unit` beneath. This is how a user verifies a merge was correct — without
it, canonicalisation is invisible and untrustworthy.

The header itself is `row.space`, which the backend already picked from the
vendors' own wording for that cluster, so it will not read `GF-Bedroom1` for
quotes that never mention a floor. Render it as given; do not prettify or
re-derive it here, or the header and the aliases beneath it stop agreeing.

## Coverage lookup

```ts
export function coverageIndex(m: MatrixV1): Map<string, CoverageEntry>;
// key: `${space_id}||${vendor}`
```

A `Map` because the matrix UI queries it once per cell. Absent entry means fall
back to the old rule (zero renders as `N/A`), which keeps legacy payloads
rendering correctly.

## Totals

`sumSubServiceRow` is unchanged in behaviour: sum the per-vendor amounts across
the given rows. It now reads through `amountOf` so a malformed value becomes `0`
rather than `NaN`.

Space header totals sum only that space's rows — which, because the backend
excluded bundles from `spaceTier`, automatically excludes bundled amounts. The
frontend does not need to know about that rule; it falls out of the tier split.

`quotedWorkCounts` counts work rows with a positive amount per vendor. The
matrix header and both PDF modes use it as a scope signal (8 items vs 20)
without regrouping. Collapse in F3 is display-only; this helper does not change
`space_id`.

## What this stage must not do

- Sort. The backend's order is meaningful.
- Merge two `work_key`s, however similar their labels look. That is S2's call.
- Compute a bundle allocation across spaces. Deliberately not supported anywhere.

## Tests

`lib/__tests__/project-helpers.test.ts`, `describe("compare-matrix")`:

- rows sharing a `work_key` with different labels land on one row,
- rows sharing a label but differing `work_key` stay apart,
- legacy rows without `work_key` group by label as before,
- space aliases accumulate distinctly,
- insertion order is preserved,
- `coverageIndex` returns the right entry and tolerates absence,
- `quotedWorkCounts` counts positive work rows per vendor on a space group.

---

## What to change if this stage breaks

**Symptom: one work item appears twice in a room.**
Compare the two rows' `work_key`. If they differ, this is S2 in the backend, not
here. If they match, the grouping key is wrong.

**Symptom: rows collapsed that should be separate.**
Check whether `work_key` is empty on both — the fallback then keys on the label,
and two blank labels collide. Ensure the backend never emits an empty `work_key`.

**Symptom: order looks random.**
Something introduced a sort, or a `Map` iteration replaced the insertion-ordered
arrays.

**Symptom: header total disagrees with the rows beneath it.**
`sumSubServiceRow` is summing a different row set than the one rendered. Usually
a `flatMap` over the wrong level.
