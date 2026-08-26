# F4 — Export

Render the comparison to PDF.

**Module:** `lib/download-comparison-pdf.ts` (jsPDF, client-side only).

---

## Rule

The export mirrors the on-screen matrix. It reuses `groupTableData` and
`sumSubServiceRow` from [02-grouping.md](02-grouping.md) rather than
re-implementing the hierarchy, so the two can never diverge in structure.

## The problem this solves

The exported PDF was a strict subset of the screen: space header, sub-service
name, per-vendor amounts. It dropped `pricing_method` and `breakdown`, and — once
the pipeline gained coverage and bundles — would have dropped every signal that a
comparison is not like-for-like.

That matters more in the export than on screen, because the PDF is the artefact
that gets forwarded to someone who never saw the app and cannot hover a tooltip.
A cell reading `N/A` in a shared PDF, with no indication that the amount is
actually bundled elsewhere, is how a vendor gets wrongly excluded.

## What the export must carry

Everything load-bearing for a decision:

| Element | Reason |
| --- | --- |
| `incl. in <bundle>` cells | otherwise a bundled scope reads as a missing one |
| Non-comparable space marker | otherwise two unlike totals look comparable |
| Bundle section with `basis` | the lumpsum-vs-itemised gap is often the biggest number in the comparison |
| Package takeaway / Key takeaways | the customer-facing ask-the-vendor sentence for that gap |
| Recap placement notes | which quote's figure is already in the spaces vs a whole-home amount in this quote |
| GST entry chips / mixed banner | how each quote was typed (excl vs incl GST); amounts stay billed totals |
| Overlap warnings | a possible double-count the reader should raise with the vendor |
| Footnote explaining the three cell states | the PDF has no tooltips |

Whole-home export uses `projectRowsForDisplay`, the same filter as the screen, so
electrical compared in "Same work, different spaces" is not listed again. The
export does not paint a Quote total row; grand totals stay on the chart.

Since colour and hover are unavailable, every state is expressed in text.

## What it may omit

Long `breakdown` item lists, which are diagnostic rather than decision-relevant
and would overwhelm the page. The bundle section already names the items that
matter, because those are the ones a lumpsum absorbed.

## Pagination

Space groups avoid breaking across a page boundary where possible; the bundle
section starts on a fresh page when it would otherwise split. Each page repeats
the vendor column headers — without them, a continuation page is unreadable.

## Tests

Structural rather than pixel-based, since jsPDF output is not usefully
snapshotted:

- the export uses the same grouping helpers as the screen,
- a bundle in the payload produces a bundle section,
- an `incl_in_bundle` cell does not render as `N/A`,
- a legacy payload without tiers still exports the old layout.

---

## What to change if this stage breaks

**Symptom: the PDF disagrees with the screen.**
Something here re-implemented grouping instead of importing it. That is the
failure mode this stage exists to prevent.

**Symptom: rows are cut off.**
Pagination measurement, local to this module.

**Symptom: the export throws on a large comparison.**
jsPDF memory. Reduce per-row work before adding pagination complexity.

**Do not** let the export carry less decision-relevant information than the
screen. If a signal is important enough to render in the UI, it belongs here —
this is the version that leaves the building.
