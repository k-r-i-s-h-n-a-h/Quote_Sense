# F3 — Matrix UI

Render the comparison table.

**Module:** `components/compare/ComparisonMatrix.tsx`.

---

## The problem this solves

The table's own footnote said:

> N/A means that vendor did not quote this work in this room.

That was false for roughly thirty cells in the golden comparison. A zero could
equally mean the work was named differently by the other vendor, or that its price
was sitting inside a lumpsum elsewhere in the quote. Presenting all three as
`N/A` in identical styling is the single most misleading thing the UI did — it
made a vendor with a bundled scope look like a vendor with a missing scope.

The backend now distinguishes them. The UI's job is to show the difference.

## Cell states

| Coverage status | Render |
| --- | --- |
| `quoted` | the amount |
| `incl_in_bundle` | `incl. in <bundle label>`, muted, not styled as an error |
| `not_quoted` | `N/A`, rose italic — reserved for a genuine gap |
| no coverage entry | legacy rule: zero → `N/A` |

The distinction between the second and third rows is the point. `incl. in
Hardwares` is neutral information; `N/A` is a warning. They must not look alike.

## Space header

Adds a badge when the space is not comparable:

- `comparable: true` → unchanged.
- `comparable: false` → a `scope differs` badge with a tooltip naming the bundle,
  and the totals rendered muted. The numbers are still shown — they are correct
  per vendor — but the visual weight says they are not a like-for-like pair.

Space aliases continue to render under the canonical name, which is how a user
sanity-checks a merge.

## Bundle section

A distinct block after the space tiers, not another space group, because a bundle
is a different kind of thing and nesting it under a room would repeat the original
mistake.

Each bundle row shows:

- the bundle label and the family,
- covered spaces, and the items named in the vendor's description,
- each vendor's figure with a `basis` chip: `lumpsum` or `sum of N items`,
- an overlap warning when `overlap_flags` is non-empty,
- a plain-English takeaway when `takeaway.text` is set (package vs itemised only).

The `basis` chip carries most of the value here. `Rs 1,00,300 (lumpsum)` against
`Rs 37,198 (sum of 5 items)` tells the user both the price gap and that the two
numbers are not the same kind of measurement. Without the chip the row would
imply a clean Rs 63,000 saving, which is not a claim the data supports.

Overlap warnings are phrased as a question to put to the vendor, not as a
detected error — we cannot know whether the lumpsum double-counts the separate
line.

The takeaway names who is higher by how much and what to ask. It does not
accuse, and it does not fire on itemised-vs-itemised recaps.

When one quote itemises the family in rooms and another parks a whole-home
figure, each cell names the quote (company if they differ, quote number if
they are the same company) and says where the rupees already sit. Space
figures are comparison only. A whole-home figure is included in this quote,
not in the space sums. The matrix does not paint a Quote total row; the
chart already shows each quote's full amount.

Column chips `Entered excl. GST` / `Entered incl. GST` come from
`vendorMeta.gst_mode`. A banner above the table fires only when those modes
differ. Cell amounts stay billed totals (GST included).

## Project section

Work with no room, labelled Whole home. Rows whose `bundle_family` is already
compared in a scattered recap are **not painted** here — the recap is the
comparison; painting them again looks like a second add. `reconcileQuoteTotals`
still sums the full `projectTier`.

## Footnote

Replaced. States the three cell meanings explicitly, and that bundled amounts are
excluded from room totals by design.

## Accessibility and layout

Existing conventions kept: sticky header, `min-w-[720px]` with horizontal scroll,
`tabular-nums` on figures, vendor colour dots. Badges and chips use text as well
as colour so they survive greyscale printing and colour-blind viewing.

## Tests

- a `quoted` cell shows the amount,
- an `incl_in_bundle` cell shows the bundle name and not `N/A`,
- a `not_quoted` cell shows `N/A`,
- a legacy payload with no coverage renders zero as `N/A`,
- a non-comparable space shows the badge,
- a bundle row shows both basis chips,
- a mixed recap names each quote and where the rupees already sit,
- an overlap flag renders a warning.

---

## What to change if this stage breaks

**Symptom: every cell shows `N/A` again.**
`coverage` is empty, so the legacy fallback is active. The problem is upstream —
F1 dropped it, or the backend did not emit it.

**Symptom: a bundle amount appears in a room total.**
Not this stage. The backend put a bundle row in `spaceTier`; see backend S4/S5.

**Symptom: the bundle section is empty but bundles exist.**
Check `bundleRowsOf` and the accessor fallback in F0.

**Symptom: totals disagree with the rows.**
F2 grouping, not rendering.

**Do not** compute a corrected figure in the UI to make a comparison look
cleaner — not a bundle allocation, not an overlap subtraction. If a number needs
deriving, it is derived in the backend where it can be tested, or it is not shown.
