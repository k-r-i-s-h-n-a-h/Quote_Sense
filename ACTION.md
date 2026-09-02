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
