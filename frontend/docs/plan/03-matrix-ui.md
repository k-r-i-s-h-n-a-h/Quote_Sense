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
| `incl_in_parent` | `incl. in <parent space>`, same treatment as a package — not a miss |
| `not_quoted` | `N/A`, rose italic — reserved for a genuine gap |
| no coverage entry | legacy rule: zero → `N/A` |

The distinction between the second and third rows is the point. `incl. in
Hardwares` is neutral information; `N/A` is a warning. They must not look alike.

## Space header

The header is the decision row: **vendor space totals first**, with a per-vendor
**item count** (`N items`) so a cheap total with few lines is visible next to a
deeper quote. Work rows start **collapsed**. A chevron on the heading toggles
that `space_id`; **Expand all work** / **Collapse to space totals** apply to
every space. Grouping stays on `space_id` — the accordion is presentation
([ACTION.md](../../../ACTION.md) §7).

Adds a badge when the space is not comparable:

- `comparable: true` → unchanged.
- `comparable: false` → a `scopes differ` badge with a tooltip naming the bundle,
  and the totals rendered muted. The numbers are still shown — they are correct
  per vendor — but the visual weight says they are not a like-for-like pair.
  Collapse must not hide this badge.

A last sticky **Comparison Summary** column explains the row (quantity vs rate
vs named finish vs parent/package vs true N/A). Space headers show a header
summary while work is collapsed. The header sentence is amount plus why: item
counts (`3 items vs 5 — charged more for fewer lines`), exclusive work names
(capped at three), and `scopes differ (package vs itemised)` when the space is
not like-for-like. Work rows (every sub-service) lead with the rupee gap, then
qty and rate when both quoted those figures, then `specified …` only if the
vendor wrote a finish or brand in `description`. Qty/rate clauses name both
vendors rather than relying on column order; two quotes from the same company
are called `Vendor Q1` and `Vendor Q2`. True N/A and `incl. in …` stay as they
are. When S5 sets `named_in` / a description-cover `summary`, render that
sentence instead of “did not quote this line” — the cell can stay `N/A`. The
column does not regroup and does not change totals
([ACTION.md](../../../ACTION.md) §8). Refreshing a compare URL reuses the
saved `session_id`; qty/rate notes need a matrix that includes `measures`, so
the page starts a new compare once if that field is missing.

Space aliases continue to render under the canonical name, which is how a user
sanity-checks a merge.

## Bundle section

A distinct block after the space tiers, not another space group, because a bundle
is a different kind of thing and nesting it under a room would repeat the original
mistake.

Each bundle is two rows, like a construction BOQ remark:

1. **Amount row** — label and covered spaces on the left; each vendor's figure
   with a basis chip (`Package price` / `Itemised - N lines`) on the right.
2. **Full-width note band** under that row — overlap warning, package takeaway,
   and recap placement. Notes never sit only in the left cell, because on a wide
   screen that leaves a blank gap before the amounts and the customer misses the
   sentence.

The `basis` chip carries most of the value here. `₹1,00,300 (Package price)`
against `₹37,198 (Itemised - 5 lines)` tells the user both the price gap and that
the two numbers are not the same kind of measurement. Without the chip the row
would imply a clean ₹63,000 saving, which is not a claim the data supports.

Overlap warnings are phrased as a question to put to the vendor, not as a
detected error — we cannot know whether the lumpsum double-counts the separate
line.

The takeaway names who is higher by how much and what to ask. It does not
accuse, and it does not fire on itemised-vs-itemised recaps. It is shown once, in
the note band — not duplicated as a separate "Key takeaways" block.

When one quote itemises the family in spaces and another parks a whole-home
figure, the note band names the quote (company if they differ, quote number if
they are the same company) and says where the rupees already sit. Space
figures are comparison only. A whole-home figure is included in this quote,
not in the space sums. The matrix does not paint a Quote total row; the
chart already shows each quote's full amount.

Column chips `Entered excl. GST` / `Entered incl. GST` come from
`vendorMeta.gst_mode`. A banner above the table fires only when those modes
differ. Cell amounts stay billed totals (GST included).

## Vendor totals

`VendorSummary` is the only total-at-a-glance section. Do not add a separate
Cost comparison chart: it repeats the same two grand totals and pushes the
comparison matrix farther down the page.

## Ask the vendors

Space insights (cheapest overall / cheapest by room) is gone. That board
invited a "lowest bar wins" reading of rooms that are not like-for-like.

In its place, `AskVendors` (`components/compare/AskVendors.tsx`) lists
questions the comparison cannot settle:

- UNASSIGNED rooms — which numbered room?
- bundled zones — please break out
- possible cross-scope matches — same work or not?
- pricing-method unit mismatches
- GST entered excl vs incl
- two standing asks: N/A vs bundled, and lumpsum contents

Two quotes from the **same company** → one checklist, headed with that
name and both quote numbers.

Two **different companies** → two checklists, one after the other, each
headed `Ask {company}` with that quote number. A bundled zone or unassigned
room that belongs to one vendor is only on that vendor's list.

The customer ticks what to send, writes notes **on that vendor's card**, then
**Copy questions** / **Email {company}** / **WhatsApp {company}** at the **end
of that card**. The first checklist never goes to the second vendor.

**Email {company}** POSTs that card only to `/api/ask-vendors/email` → Tatva
`POST {TATVA_API_BASE}/notification/api/notifications/send` with
`type: "generic"`, vendor `to`, and HTML/plain `data`. No MSG91 email
template. From is PM’s `info@withtatva.ai`. The body is the full ticked list
plus notes as an `<ol>` of `{{text}}` only (no extra `{{number}}`). The
payload’s `quote_number` is **one** quote id — the other comparison quote is
never in the subject or body. Same-company UI still shows both numbers on the
card subtitle for the customer.

**WhatsApp {company}** POSTs that card only to `/api/ask-vendors/whatsapp` → MSG91. WhatsApp does not
allow newlines inside a variable, so the approved v2 template
(`tatvaops_quotesense_ask_vendor_v2_en`) puts each question on its own
static line (`{{4}}`–`{{6}}`) and notes in `{{7}}`. Until that template is
approved, the original 5-variable template packs questions as
`1) … | 2) …`. Empty notes send as `—`. Notes are flattened to one line
(Meta rejects line breaks in a placeholder). Questions in the packed
template are clipped to 400 characters, each v2 slot to 220, notes to 200.
Copy questions still holds the full text.

Outbound text is vendor-private. A card may name that vendor's own quote,
space and scope, but must never contain the other vendor's company, quote
number, space label, price or contact. Cross-scope findings therefore become
one question per vendor about that vendor's own container. The customer-facing
matrix may still show both sides.

Email sends this same vendor-specific clarification brief, not the comparison
report. `vendorMeta.email` comes from `quotes.vendor_email` (Tatva
`vendorDetail` or a printed PDF header). Empty when the source had none.

Ticks and notes persist in `sessionStorage` for the comparison session.

## Letterhead

The matrix card repeats the document identity the PDF uses: Tatva Ops logo,
project title and code, and each quote number. Vendor column headers wrap the
full company name (no ellipsis) and show `Quote {number}` in the column.

## Project section

Work with no room, labelled Whole home. A row is **not painted** here only
when one of its own `source_line_ids` already sits in a scattered recap — the
recap is that line's comparison. Sharing a family name (`hardware`,
`lighting`) with a recap is not enough; a Whole-home hinges line must still
show when the recap is some other hardware in two rooms.
When a Whole-home line really is absorbed, the recap names it and its amount
from `project_items`; a family total alone is not proof to the reader that the
line survived. A merged row is kept if any of its source lines is not recapped.
`reconcileQuoteTotals` still sums the full `projectTier`.

## Abstention tiers and notes

Three tiers do not render as ordinary rows, because for each of them a plain
number or a plain `N/A` would state something false.

- **`UNASSIGNED`** — the vendor named a room kind without a number. Rendered as
  its own space group headed `UNASSIGNED — "<the vendor's exact label>"`, with
  the confirm-before-allocating note above its rows. Never folded into a
  numbered room, never blanked.
- **`BUNDLE_NOT_DECOMPOSABLE`** — the vendor priced a multi-trade zone as one
  scope. `bundleZoneSpaceIds` suppresses that space's line rows; the zone total
  and the bundle note render instead. Painting the lines would invite the reader
  to compare pairings the pipeline explicitly refused to make.
- **`POSSIBLE_CROSS_SCOPE_MATCH`** — its own flagged section below the tiers,
  both figures side by side with the confirm-with-vendor note. The totals are
  not merged and the section is not added to anything.

## The export gate

When `reconciliationBlockReason(reconciliation)` returns a reason, both PDF
buttons are disabled and the reason is shown in a banner naming the vendor and
the unaccounted lines. The comparison stays fully readable on screen — the
block is on turning an incomplete comparison into a document.

## Footnote

Replaced. States the three cell meanings explicitly, and that bundled amounts are
excluded from room totals by design.

## Accessibility and layout

Document look rather than a spreadsheet: charcoal sticky header with an orange
rule, hairline row dividers (no vertical grid), `min-w-[800px]` with horizontal
scroll, `tabular-nums` on figures, vendor colour dots. Vendor column **headers
and amounts are centered**; space/work labels stay left-aligned. Amounts use `₹` via
`formatInrFull`. Badges and chips use text as well as colour so they survive
greyscale printing and colour-blind viewing.

## Tests

- a `quoted` cell shows the amount,
- an `incl_in_bundle` cell shows the bundle name and not `N/A`,
- a `not_quoted` cell shows `N/A`,
- a legacy payload with no coverage renders zero as `N/A`,
- a non-comparable space shows the badge,
- space work rows start collapsed and expand on the heading,
- the header shows item counts per vendor,
- a Comparison Summary column explains quantity/rate/coverage gaps,
- an `incl_in_parent` cell shows the parent name and not `N/A`,
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
