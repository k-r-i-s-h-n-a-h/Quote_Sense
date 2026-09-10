# F4 — Export

Render the comparison to PDF.

**Module:** `lib/download-comparison-pdf.ts` (jsPDF, client-side only).
Font helper: `lib/pdf-unicode-font.ts` (Noto Sans so `₹` prints).

---

## Precondition: the reconciliation gate

Before anything is drawn, `downloadComparisonPdf` checks
`reconciliationBlockReason` and throws `PdfReconciliationError` when a vendor's
rows do not add back up to that vendor's quoted lines. No PDF is produced.

This is the one hard block in the export path. A document is forwarded to people
who never see the app and cannot re-run the comparison, so an incomplete one has
a much longer life than a blocked one.

## Rule

The **detailed** export mirrors the on-screen matrix. It reuses `groupTableData`,
`sumSubServiceRow`, and `quotedWorkCounts` from [02-grouping.md](02-grouping.md)
rather than re-implementing the hierarchy. The **spaces** artefact uses the same
helpers and omits work lines only.

## Document look

The PDF is the artefact a contractor forwards to a client. It is **portrait A4**
so it prints and shares as a standard vertical sheet, and it is a letterhead
document rather than a spreadsheet dump:

- **Every page** repeats the Tatva Ops logo, project title, project code, and
  the quote numbers (`Company · Quote Q2OE1CX`).
- Amounts use **₹** (Noto Sans). Helvetica cannot draw that glyph; if the font
  fails to load, the fallback is `INR`, never a broken box.
- The table uses hairline **horizontal** rules only — no vertical grid.
- Vendor column **headers and rupee amounts are centered** in the cell.
  Space/work labels stay left-aligned.
- Bundle takeaways and recap placement sit in **full-width note bands** under
  the amount row, the same structure as the screen. They are not stuffed into
  the left cell, and they are not duplicated in a second "KEY TAKEAWAYS" block.

`downloadComparisonPdf` takes optional `{ projectTitle, projectCode, detail }`
from the compare page. `detail` is `"spaces"` or `"full"` (default full).

## Two artefacts

| Button | `detail` | Filename suffix | Contents |
| --- | --- | --- | --- |
| PDF: spaces | `spaces` | `-spaces.pdf` | Space headers, item counts, packages, recaps, whole-home as space totals. No work lines. |
| PDF: detailed | `full` | `-detailed.pdf` | The on-screen matrix with every work line. |

Spaces mode must still carry lump-sum packages and recap notes. It must not drop
a `scopes differ` marker. Both stay portrait A4 with centered vendor headers
and amounts. The **detailed** PDF includes the Comparison Summary column; the
spaces artefact keeps one summary line on each space header. Those lines use the
same composition as the matrix: amount plus item-count / exclusive-work /
scopes-differ reasons. Detailed work-row summaries lead with the money gap, then
qty/rate, then a specified-finish clause when the vendor wrote one.

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
| Package takeaway | the customer-facing ask-the-vendor sentence, once, in a note band |
| Recap placement notes | which quote's figure is already in the spaces vs a whole-home amount in this quote |
| GST entry chips / mixed banner | how each quote was typed (excl vs incl GST); amounts stay billed totals |
| Overlap warnings | a possible double-count the reader should raise with the vendor |
| Footnote explaining the three cell states | the PDF has no tooltips |
| `UNASSIGNED` space groups with their confirm note | the vendor did not say which room; the document must not decide for them |
| Bundled-zone note instead of that zone's line rows | line pairings the pipeline refused to make must not appear to have been made |
| Possible cross-scope match section | otherwise a scope one vendor did quote reads as one nobody quoted |
| `combines: …` on a merged row | a relabelled row that traces back to nothing cannot be checked against the quote |

Whole-home export uses `projectRowsForDisplay`, the same filter as the screen, so
a line already in "Same work, different spaces" is not listed again — other
Whole-home lines of that family still print. A suppressed line is named with
its amount beneath that recap from `project_items`; it cannot survive only as
an anonymous share of a family total. The export does not paint a Quote total
row; grand totals stay on the chart.

Since colour and hover are unavailable, every state is expressed in text.

## What it may omit

Long `breakdown` item lists, which are diagnostic rather than decision-relevant
and would overwhelm the page. The bundle section already names the items that
matter, because those are the ones a lumpsum absorbed.

## Pagination

Space groups avoid breaking across a page boundary where possible. Portrait A4
is taller than landscape, so a typical two-vendor comparison uses more pages
and fewer columns of empty space. Each page repeats the letterhead and the
vendor column headers — without them, a continuation page is unreadable. A
footer stamps `Page n of m`.

## Tests

Structural rather than pixel-based, since jsPDF output is not usefully
snapshotted:

- the export uses the same grouping helpers as the screen,
- `detail: "spaces"` omits work lines and still includes packages/recaps,
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
