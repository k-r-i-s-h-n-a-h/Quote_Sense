# S5 — Matrix

Pivot the enriched rows into the three-tier `MatrixV1` payload.

**Input:** rows carrying all S1–S4 fields.
**Output:** `MatrixV1` — see [00-contracts.md](00-contracts.md).

**Module:** `services/comparator.py::run_comparison`.

---

## Why three tiers

A single space-grouped table cannot hold a price that spans several rooms.
Forcing it to produces the failure described in [04-bundles.md](04-bundles.md):
the lumpsum lands in `Project-level`, disappears from every room total, and the
two vendors' room subtotals stop being comparable without any indication.

So the matrix separates by scope, which is exactly what S4 computed:

| Tier | Contents | Grouping key |
| --- | --- | --- |
| `spaceTier` | `scope == "space"` | `(space_id, work_key)` |
| `bundleTier` | one row per bundle family | `bundle_family` |
| `projectTier` | `scope == "project"` | `work_key` |

Every rupee appears in exactly one tier. Chart `chartData` is the quote's
billed grand total. The matrix UI and PDF export do **not** paint a Quote
total row.

## Grouping key change

Was `(space, sub_key)` where `sub_key` was raw vendor text. Now
`(space_id, work_key)`. Both halves of the key are canonical, which is what makes
`Side table`/`Side Table` and `Bedroom 1`/`GF Bedroom 1` land on one row.

The displayed label comes from the modal `work_label` among the contributing
lines, so the row reads in human words even though it is keyed on a slug.

## Coverage

For every (space, vendor) pair, emit a `CoverageEntry` with one of:

| Status | Meaning | UI |
| --- | --- | --- |
| `quoted` | vendor has priced lines in this room | the amount |
| `incl_in_bundle` | vendor's price for this room sits inside a bundle | `incl. in <bundle>` |
| `not_quoted` | vendor genuinely quoted nothing here | `N/A` |

This is the single highest-value output of the whole redesign. Previously every
one of these three very different situations rendered as `N/A`, and the old
footnote asserted the third meaning for all of them. Roughly thirty cells in the
golden comparison were mislabelled that way.

A space is `comparable = false` when any vendor's status there is
`incl_in_bundle` — the room's totals cannot be compared like for like, and the
header says so instead of pretending.

## Ordering

Preserved from the original implementation: rows keep first-appearance order via
a `__seq` column, so the matrix reads in roughly the order the quotes do rather
than alphabetically. Space order and sub-row order are both derived from the
minimum sequence number in each group.

## Backward compatibility

`tableData` is still emitted, equal to `spaceTier + projectTier`, with the same
per-vendor amount keys and the same `space` / `sub_service` / `pricing_method` /
`breakdown` fields as before. The existing frontend and PDF export keep rendering
against it until they are updated. New consumers read the tiers.

`contract_version: "MatrixV1"` lets the frontend detect which shape it received.

## Removed

`_line_item_key` — dead code, never called anywhere in the repo.

## Tests

`tests/test_matrix_contract.py`:

- the row contract validates after each stage,
- `MatrixV1` has all required top-level keys,
- tier totals sum to each vendor's line-item total (no rupee lost or duplicated),
- `tableData == spaceTier + projectTier`,
- no bundle amount appears in any space total,
- golden assertions: no `USED CLOTH UNIT` space; `Side table` is one row;
  `Rolling Shutter` is one row; the hardware bundle pairs Rs 1,00,300 against
  Rs 37,198.

---

## What to change if this stage breaks

**Symptom: a rupee total does not reconcile.**
Check the `scope` partition first — a row whose scope is unset would fall out of
all three tiers. The tier-sum test catches this.

**Symptom: rows are in a strange order.**
`__seq` handling, nothing else.

**Symptom: the same work appears twice in one room.**
Not this stage. Two different `work_key`s reached the same room, which is S2.

**Symptom: a room total looks too low.**
Check the coverage entries for that room. If a vendor is `incl_in_bundle`, the
total is correct and intentionally not comparable — that is S4 working, not a
bug.

**Symptom: the frontend broke after a change here.**
`tableData` is a contract, not a convenience. If you must change its shape, bump
the version in `00-contracts.md` and update
[frontend/docs/plan/02-grouping.md](../../../frontend/docs/plan/02-grouping.md)
in the same commit.
