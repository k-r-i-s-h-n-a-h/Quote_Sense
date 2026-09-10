# ACTION.md — comparison invariants agents must not reverse

This file is the lock on **comparison** behaviour that customers already
agreed. Vendor market-rate recommendations are a different product — lock
and map are [ACTION_RECOMMENDATIONS.md](ACTION_RECOMMENDATIONS.md) and
[PLAN_RECOMMENDATIONS.md](PLAN_RECOMMENDATIONS.md). Do not mix the two.
`backend/docs/plan/06-recommend.md` is the comparison narrative (S6), not
vendor base rates.

If a later change looks like an improvement but violates one of these rules,
**do not ship it**. Update a stage implementation to honour the rule; do not
weaken the rule to make a model or a heuristic easier.

The comparison pipeline plan stays in [PLAN.md](PLAN.md). This file is the
"why we must not undo that work" list.

---

## 1. One physical space, one customer total (S3)

Vendors name the same room in different words. The matrix must **combine**
those spellings into one space so the customer sees spend per room, not per
vendor nickname.

These are the **same living space** and must be one section:

`Living` · `LIVING` · `Living Room` · `Living area` · `L R` · `LR` · `LVR` ·
`L ROOM` · `Lroom` · `Liv`

The same rule applies to every room type: `DNR` / `Dining` / `Dining area`;
`KIT` / `Kitchen`; `MBR` / `Master Bedroom`; lounge spellings on one floor.

**What the customer must see:** every sub-service the vendors quoted in that
space, under one heading, with one space total.

**What they must not see:** a separate block for each spelling (`LIVING`, then
`L R`, then `LVR`, then `L ROOM`). That is a decomposition by words, not by
rooms, and it hides the living-area total.

How S3 is allowed to do this:

1. Deterministic room tokens and compact abbreviations first
   (`backend/services/space_clusters.py`).
2. LLM overlay only for leftovers the tokens missed — and the prompt must
   treat the living/dining abbreviations above as **mandatory merges**.
3. Display heading comes from the vendors' own wording (prefer the spelled-out
   name). Never invent a floor (`GF-`) nobody wrote.

The frontend **must not** re-split by the heading. It groups on `space_id`.

Do **not** "fix" this by showing every vendor string as its own space. That
was the bug.

---

## 2. Packages vs single-item lumpsums (S4)

A package is lump-priced **and** enumerates two or more **known** work items.
A lump ₹8,850 for one room's wall décor is **not** a package. Hardware listing
six accessories **is**.

Never treat brand prose (`Greenply & Century`) as a work list. Never slugify
unknown fragments to force a package. Never sum unrelated leftover (`mixed`)
packages into one comparison row — one vendor line is one package row.
Brand and finish words in `description` may appear in Comparison Summary as
`specified …`; they still must not become extra work rows.

Window blinds and a tissue holder are whole-home lines, not wall décor.

---

## 3. Expired session → login popup, not an inline button

When the user's Tatva session has expired, tell them with a **modal**.

- Do not put a small "Sign in again" button inside the My projects card.
- The popup states that the session expired and the primary action is
  **Sign in again**.
- Standalone PDF compare may remain available after they dismiss the popup.

Module: `frontend/components/SessionExpiredModal.tsx`, shown from
`ProjectDashboard` on a 401/403 while a stale user is still in memory.

---

## 4. Change protocol

If a matrix looks wrongly grouped, fix **S3** (or S2 for work items, S4 for
lumpsums). Do not invent a new grouping layer on the frontend. Do not drop
abbreviation rules because a new model "will understand it" — keep the
deterministic merge; the LLM is a backup, not a replacement.

---

## 5. Recap vs Whole home, and package takeaways

A "Same work, different spaces" row is a **comparison view**. It must not be
shown again as a Whole home line for that family. Accounting stays in
`projectTier`; only the display is filtered. Quote total still counts those
rupees **once**.

When one vendor priced a family as a package and another listed it line by
line, the customer must see a short plain-English note: who is higher, by how
much, and what to ask. Do not call either side wrong. Do not write that note
for itemised-vs-itemised recaps. Do not change room totals or subtract overlaps.

When one quote itemises that family in rooms and another parks a single
whole-home figure, the recap must name each quote and say where the rupees
already sit. Use the company name when the companies differ; use the quote
number when they are the same company. Space figures are already in the
spaces above (comparison only). A whole-home figure is included in this
quote, not in the space sums. Do not change the addition. Do not paint a
Quote total row on the matrix.

## 6. GST inclusive vs exclusive

Tatva quotes carry `exclusiveGst` / `inclusiveGst` on `workSummary`. Matrix
amounts are always the billed `grandTotal` (GST included). Do not mix a
pre-GST `amount` from one quote with a GST-inclusive `grandTotal` from
another. Name how each quote was entered (company if they differ, quote
number if they are the same company). Do not convert one quote onto the
other's GST basis by applying a homemade rate.

---

## 7. Space totals first; work list on demand

The comparison matrix must show **whole-space spend on the space header**
before any work line. Sub-services start **collapsed**; the customer opens a
space (or Expand all) to see the work list. Item counts on the header show how
much of that space each vendor quoted so a cheap total with few items is not
mistaken for a like-for-like saving.

The frontend still groups only on `space_id`. Collapse is presentation, not a
new grouping layer. Every quoted sub-service remains available under that
heading when the space is opened — do not drop work lines to make the table
shorter.

PDF export offers two artefacts: **spaces** (headers + packages/recaps) and
**detailed** (every work line). Do not ship a space-only PDF that drops lump-sum
packages or recap notes. Do not hide a scope mismatch to make totals look
comparable.

---

## 8. Nested spaces and Comparison Summary

A walk-in closet (or attached bath, dressing, balcony, utility) that one vendor
quoted as its own space, and another folded into a parent room, must stay **two
`space_id`s**. Do not merge the child into the parent. S3 may only add a
containment **edge** (`contained_in`). The child's cell for the vendor who
priced that work in the parent is `incl_in_parent`, not `N/A`.

`N/A` remains for a genuine gap. Do not hide a true miss.

**Comparison Summary** is an explanation column. It must not change space
totals or invent a new grouping key. The frontend still groups on `space_id`.

The column applies to **every work row**, not one example line. Space headers
stay amount · item counts · exclusive work · scopes differ. Work rows lead with
the rupee gap, then quantity, then rate, then a spec note — each only when the
payload actually has it.

### Extraction the summary is allowed to quote (S1)

S1 copies what the vendor wrote. It does not interpret finishes or invent area.

1. `quantity` and `rate` come from the line as billed (`pricingInput` on the
   Tatva lane; the QTY/RATE columns on PDF extract). Missing or zero stays
   missing or zero.
2. `description` is preserved in full. Do not truncate it so S3/S4 still see
   room hints and bundle lists.
3. `pricing_method` is recorded verbatim (so the summary can say sqft vs rft).
4. Do not fill quantity from amount÷rate when the vendor left qty blank. Do
   not guess a finish the description never named.

### How the matrix builds the sentence (S5, then UI/PDF)

1. S5 puts per-vendor `measures` on the `SpaceRow`: quantity, rate,
   pricing_method, description. Amounts are unchanged.
2. Coverage still wins: `incl_in_parent` / `incl_in_bundle` / true `N/A`
   (`did not quote this line`) — same as the cell.
3. When both vendors quoted the line:
   - always the money gap (`TCS is ₹17,464 higher`);
   - if both quantities are > 0 and they differ by 10% or more, name both
     (`12 sqft vs 20 sqft (billed more area)`);
   - if both rates are > 0 and they differ by 10% or more, name both
     (`₹850/sqft vs ₹1,250/sqft`), or `same area, X's rate is higher` when
     qty is similar;
   - if description names a finish, brand, or material (laminate, louver,
     HDHMR, ply brand, glass, …), add `X specified …`. If they did not write
     it, omit. Same tokens on both sides, omit. This is not a claim that the
     spec *caused* the gap.
4. The UI and both PDFs render that sentence. They must not regroup or
   reallocate rupees to make the story tidier.

---

## 9. Exactly two quotes per comparison

A comparison run is **two quotes**, not three. Standalone PDF upload and
project quote pick both stop at two. A third file or checkbox is blocked
until one of the two is removed.

Do not raise the cap back to three to "use empty matrix columns". Do not
allow a one-quote compare. `MIN_COMPARE_QUOTES` and `MAX_COMPARE_QUOTES`
stay 2 (`frontend/lib/compare-limits.ts`, `backend/main.py`).

---

## 10. Compare work intent, not only its catalog title

Two lines called `Wardrobe` are not the same purchase when one is a new
wardrobe and the other explicitly says dismantling, demolition, cleaning, or
shifting. Keep those ancillary lines separate from fabrication/installation so
their quantities and rates are never blended into a false area or unit rate.

Do not move an ancillary amount into another vendor's generic `Civil` row.
Civil and dismantling may be related, but they are not automatically
like-for-like. Keep every rupee on the vendor's original line and let the space
header name the exclusive work.

Comparison Summary quantity and rate clauses must name both vendors. Never rely
on bare `114 sqft vs 45.5 sqft` ordering after naming only the higher vendor.
When both quotes have the same company name, call them `Vendor Q1` and
`Vendor Q2` throughout the summary.

---

## 11. Description can name work the other vendor itemised

When one vendor itemises dismantling, cleaning, or shifting and the other
writes those verbs in a Civil / Other-services (or similar) description, the
Comparison Summary must say the work was **named there**. Do not treat that as
a true omission.

Do not merge those rows. Do not move the ancillary amount into the Civil
lumpsum. The lumpsum is not a like-for-like rate against the itemised line —
it may also name other jobs (cleaning, bench seating, whole-home civil).

S6 must read those descriptions. If `named_in` is set, never write that the
vendor did not quote the work.

---

## 12. Compare from a PM project opens that project

When a user clicks Compare Quotes on a TatvaOps PM project, QuoteSense must
open **that project's hub** (`/project/{code or id}`) so they can pick two
quotes there.

Do not drop them on the My projects list and make them find the same project
again. A `session_id` still goes to `/compare`. A Compare click with no
project ref still goes to the list. Do not auto-run a comparison until they
select two same-tier quotes.

---

## 13. Say nothing rather than something false

From an audit of a real two-vendor comparison, line by line, against both
source quotes. Every rule below is a sentence the document actually printed
that was not true. The pipeline is allowed to abstain; it is not allowed to
assert.

### 13.1 Every rendered row traces back to source lines

Each comparison row carries `source_line_ids`, and `combined_from` when it
merged several lines from one vendor. **No source line may end up in no row.**
A line item worth Rs 29,146 disappeared from a comparison and nothing in the
output could reveal it.

### 13.2 A comparison that loses money is not a document

Per vendor, the rows must add back up to that vendor's own quoted lines (GST,
discount and TatvaOps service charges excluded and documented as out of
scope). When they do not, **the PDF is blocked** and the unaccounted lines are
named. Do not soften this into a warning banner over a downloadable file.

### 13.3 A merged row must name what it merged

When one display row covers several of a vendor's lines, the summary says
`combines: Profile lights, Strip lights`. Never silently relabel. And within
one quote, two different source lines must never print under the same label —
append the space or a short description suffix instead.

### 13.4 An unnumbered room is not room 1

Assigning a vendor's `Ground floor bedroom` to Bedroom 1 requires the vendor's
own number or an explicit catalog alias. Name similarity is not enough. With
no deterministic signal the line goes to `UNASSIGNED — "<the vendor's exact
label>"` with a confirm-before-allocating note. Do not guess it into a room,
and do not blank it. Rs 59,000 was attributed to one bedroom while the other
got nothing, on nothing more than a name being close.

### 13.5 Related work in a different container is flagged, not dropped

When both vendors quoted the same functional scope but in structurally
different containers (embedded in a room vs a standalone space), emit
`POSSIBLE_CROSS_SCOPE_MATCH`: both figures side by side, confirm with vendor,
**totals never merged**. A washroom fit-out inside one vendor's walk-in closet
read as "the other vendor quoted nothing", which was false — they had quoted
it as their own bathroom space.

### 13.6 A bundled zone is compared at zone level only

When one vendor prices a generic zone spanning two or more distinct trades,
that space is `BUNDLE_NOT_DECOMPOSABLE`: zone total plus the note saying why,
and **no line-level pairings into or out of it**. Do not line-match a
whole-house `Plumbing` figure against another quote's per-room plumbing.

A real room is never a bundled zone — bedrooms hold several trades
legitimately. The generic-label requirement is what keeps them out; do not
drop it to catch more zones.

### 13.7 Different physical units are not a quantity difference

Before any sentence comparing quantities, classify each side's pricing-method
label into a coarse physical unit (`area_sqft`, `unit`, `lump`, …). When the
bases differ — unit-count vs sq ft, sq m vs sq ft — name both methods, say it
is not comparable by quantity, and compare the rates only. `1 units vs 8 units`
for a shutter one vendor priced per unit and the other per sq ft implied one of
them quoted eight shutters.

Same physical unit, different catalog id, is still comparable: Direct Entry and
Length × Breadth both mean square feet. Do not suppress quantity language just
because the Tatva ids differ. Fall back to `pricing_method_id` only when a
basis is unknown. This rule gates wording only; IDs-first matching elsewhere
is unchanged.

### 13.8 Abstention tiers do not loosen the structural guards

`match_tier` adds ways to say "unknown"; containment, floor and numbered-room
identity remain **hard overrides** on model confidence (§1). Matching still
happens on `service_id` / `sub_service_id` / `pricing_method_id` first; label
similarity is a fallback and is never the primary signal for placing a line in
a room.

### 13.9 A generic word plus a room noun is still a room

`Common Washroom` / `Common Bathroom` are rooms, not `BUNDLE_NOT_DECOMPOSABLE`
zones. Plumbing plus tiling in a washroom is normal room scope. A catch-all
stays a catch-all only when the label is a generic word without a room-type
noun (`Common`, `General`, `Whole home electrical`). Do not lower the zone
line or trade thresholds to compensate.

### 13.10 Whole-home is hidden only when that line is already in the recap

A scattered "Same work, different spaces" recap must not blank every
Whole-home row of the same coarse family. Hide the Whole-home row only when
its own `source_line_ids` are already in the recap. A whole-home hardware
line that was never in a kitchen-hardware recap must still print.

### 13.11 Washroom civil work is flagged across containers

Tile, plaster, waterproofing and grouting in a washroom-scoped space are a
`POSSIBLE_CROSS_SCOPE_MATCH` group (`washroom_civil`), same rule as fixtures
in §13.5: confirm with vendor, **totals never merged**. Kitchen or living-room
tiling without a wet-area container is not this group.

### 13.12 A recap total does not make its source lines visible

When a Whole-home row is suppressed because its line ids are already in a
scattered recap, that recap must name each suppressed Whole-home line and its
amount. Showing only `Hardware & accessories — 3 lines` is not enough: the
reader cannot verify that a specific quoted line survived. If a merged row has
even one source line outside the recap, keep the row visible.

### 13.13 Vendor outreach never identifies another vendor

WhatsApp, copied questions and any future email are one-vendor clarification
briefs. They may name that vendor's own quote, spaces and scope, but never the
other vendor's identity, quote number, space labels, prices or contact details.
Do not send the comparison report to a vendor. The customer-facing matrix can
show both vendors; outbound vendor communication cannot.

### 13.14 Ask the vendors: email is the full list; WhatsApp stays

Each vendor card has Copy, Email, and WhatsApp. Email sends that vendor's
ticked questions and notes in full (MSG91 Email, variable-length checklist).
WhatsApp remains the existing short-channel send. Neither channel is a
comparison report or a vendor-only page. `quotes.vendor_email` is captured
from Tatva `vendorDetail` the same way as `vendor_phone`; empty means no
send. From address is the verified MSG91 domain (`info@mail.withtatva.ai`);
Reply-To may be `contact@withtatva.ai`.

### 13.15 Vendor email goes through Tatva notification, not MSG91

Ask-the-vendors **Email** POSTs `{TATVA_API_BASE}/notification/api/notifications/send`
(`type: generic`, `to`, `data.subject` / `message` / `html`). PM Nodemailer
sends as `info@withtatva.ai`. Do not add MSG91 Email DNS on Hostinger for that
address. WhatsApp stays on MSG91. The email names one quote number only — never
the other quote in the comparison. Number the checklist with an HTML `<ol>`
only (no doubled `1. 1.`).

### 13.16 A merge always discloses, even when sub-item titles match the heading

When merged lines reuse the row's own title (distinguished only in description,
or not at all), still print a `combines:` note: prefer the lines' own titles,
then a short description snippet, then count and amounts
(`combines: 3 line items (₹70,210 + ₹43,365 + ₹75,048)`). Never skip
disclosure because names matched the heading.
