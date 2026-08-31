# S3 — Spaces (room identity)

Decide **which room** each line item belongs to.

**Input:** `LineItemV1` + S2 fields.
**Output:** `+ space_id, space, space_confidence, space_source`.

**Module:** `services/space_clusters.py`.

---

## The problem this solves

Two failures, both from the golden comparison.

### Phantom spaces

`_NOT_A_SPACE` was a hardcoded set of literal strings. A label only avoided
becoming a fake room if it was already in that set, or if a room name happened to
be a substring:

| Vendor label | Old outcome | Why |
| --- | --- | --- |
| `MBR Dressing unit` | Master-Bedroom | `\bmbr\b` matched — by luck |
| `Kitchen Accessories` | Kitchen | `"kitchen" in n` matched — by luck |
| `Common vanity unit` | Common-Washroom | vanity+common rule matched |
| `Used cloth unit` | **`USED CLOTH UNIT`** | nothing matched |

That last row is the bug. It is an item name, not a room, and its description
says `"MBR Used cloth storages"`. Vendor A's equivalent (`Used cloth storage
unit`, Rs 23,954) sits inside `MASTER-BEDROOM`, so the two never compared —
vendor B's Rs 13,629 was stranded in a room that does not exist.

The general lesson: a literal blocklist cannot keep up with vendor wording. Every
new vendor adds new phantom rooms.

### The room was available and never read

`_fingerprint` only ever looked at `space_raw`. But the room is often stated
plainly in the description of the very same line. Reading the whole row fixes
`Used cloth unit` without any new literal.

---

## Resolution ladder

`resolve_space(row)` stops at the first hit and records which rung fired.

| Order | Source | `space_source` | Confidence |
| --- | --- | --- | --- |
| 1 | A room name in `space_raw` | `space_raw` | 0.95 |
| 2 | `space_raw` is an item, room found in `description` | `description` | 0.7 |
| 3 | `space_raw` is an item, room found in `item_name` | `item_name` | 0.6 |
| 4 | Gemini overlay grouped it with a known room | `llm` | 0.5 |
| 5 | No room anywhere | `project_level` | 0.4 |

After clustering, `_apply_containment` sets `contained_in` (child → parent
`space_id`) for nested rooms: walk-in/dressing → master bedroom, attached /
master bath → that bedroom, balcony → living, utility → kitchen. Floor-aware:
`1f_walkin` attaches to `1f_mbr`, not `gf_mbr`. This is an **edge**, not a
merge. Walk-in closet and Master Bedroom stay two `space_id`s.

The leftover LLM still returns `{"clusters":[{"members","kind"}]}` only. It
must not merge containment.

Rung 5 is a legitimate answer, not a failure. Transport, cleaning and
whole-project electrical genuinely have no room.

## Is-this-a-room predicate

Replaces the literal set. `space_raw` is **not** a room when any of these hold:

1. It resolves to a known work key via S2 (`Window blinds`, `Adaptors`,
   `Tissue paper holder` are all taxonomy/alias hits).
2. Normalised, it equals the line's own `item_name` — the vendor put the item
   name in the Space/Zone column. This single check catches the whole
   `MBR King size bed` / `MBR side table` / `Used cloth unit` family.
3. It matches an item-ish pattern: trailing `required areas`, `provision`,
   `accessories`, `mechanism`, `holder`, `partitions`.

Because rule 1 defers to S2, adding a sub-service to the taxonomy automatically
stops it becoming a phantom room. That is the generalisation the literal set
could not give.

## Room tokens

A small token table maps room words to `space_id`, checked against `space_raw`
first and then the description:

`kitchen`, `living`, `dining`, `foyer`, `utility`, `pooja`, `lounge`,
`mbr`/`master`, `kids`/`children`, `walkin`, `washroom`/`bathroom`/`batroom`,
`bedroom` (+ floor and number qualifiers). A floor plus a bare `room`
(`G F room`, `Third floor room`) is a space too; merge folds it into the unique
bedroom on that floor.

Bathroom is matched **before** master/kid, so "First floor Bathroom (Master
attached)" is a bathroom, not the bedroom it adjoins. An unqualified bathroom
is `bathroom`, never silently `common_washroom` — inventing the ground-floor
common wet room was how a third-floor attached bathroom landed in the
ground-floor row.

A label that names only a floor (`Ground floor`) is not a room. The resolution
ladder falls through to the description, which is how "Tv units for living
room" with Space/Zone `Ground floor` joins Living rather than minting a
phantom floor cluster.

`Whole Home` / `Full House design` are project-wide, not rooms: they resolve
to `project_level` so a lumpsum design package compares against the itemised
2D/3D/BOQ lines instead of sitting in two N/A rows.

Vendors abbreviate heavily on the Space/Zone column, so the table also carries an
abbreviation layer **and a compact form** (spaces stripped): `L R`, `LR`, `LVR`,
`LIV`, `L Room`, `L ROOM`, `Lroom`, `LIVING`, `Living Room`, `Living area` →
`living`; `DNR`, `DR`, `DIN` → `dining`; `KIT`, `KTN` → `kitchen`; `BR n` →
bedroom *n*. Without this each vendor spelling became its own `unique:` cluster
and one living room was listed four times (`LIVING`, `L R`, `LVR`, `L ROOM`),
which hides the space total from the customer.

**Invariant (see [ACTION.md](../../../ACTION.md)):** do not show one matrix
section per spelling. Combine them. The LLM overlay is a backup for leftovers;
it must not be used as an excuse to drop the deterministic merge.

### Floors are never assumed

A floor prefix is only emitted when a floor is actually stated. `Bedroom 1` →
`bedroom1`; `GF Bedroom 1` → `gf_bedroom1`; `First Floor Bedroom 1` →
`1f_bedroom1`. `_merge_floor_variants` then folds the unqualified id into its
floor-qualified twin **when exactly one floor is in play**, so `Bedroom 1` and
`Ground Floor Bedroom 1` still land on one row. If both a GF and a 1F Bedroom 1
were quoted, the unqualified label is genuinely ambiguous and stays its own
cluster rather than being guessed into one of them.

The old code defaulted the floor to `gf`, which is how the matrix came to be
headed `GF-Bedroom1` for two quotes that never mention a floor.

## Naming: the heading belongs to the vendors

`space_id` is the grouping key; `space` is only the heading. They are decided
separately, and the heading is chosen once per cluster — not per row — by
`choose_space_label(members)`:

1. Consider only members that are room labels (an item name is never a heading).
2. Prefer the most spelled-out room words: `Living Room` (2) beats `L R` (0).
3. Reject candidates carrying an item noun — `MBR Study unit`, `Kitchen
   Accessories` place the row but cannot head the column.
4. Break ties on shortest, then alphabetical: `Dining` over `Dining area`.
5. Only if nothing readable survives, fall back to `_CLUSTER_LABELS`
   (`living` → `Living`), so a cluster of pure abbreviations still reads.

Consequences worth stating plainly: a cluster whose members never mention a floor
cannot acquire one, and a row placed by its description borrows the room string a
sibling row supplied. Assertions therefore belong on `space_id`, never on `space`
— the heading legitimately changes with the quotes.

## Merge discipline

Default: **one raw string, one cluster.** Merge only when two labels are clearly
the same physical room. Never merge across room types. `MBR` and `Walk-in closet`
stay separate even though they adjoin, because a wrong merge silently sums two
rooms' costs and is much harder to notice than a missing merge.

## LLM overlay

The prompt receives **row context** (label plus sample item names and
descriptions) rather than bare labels, so it can tell `Used cloth unit` is an MBR
item. Deterministic result computed first; 8s timeout; any failure returns the
heuristic untouched.

The model is a **conservative site surveyor**: leftover Space/Zone labels only.
It proposes clusters; it does not name rooms and it does not override labels
that already have a group id. Level 1 aliases (Living / LVR / L R, Dining /
DNR, Kitchen / KIT, MBR / Master Bedroom — see [ACTION.md](../../../ACTION.md)
§1) are **mandatory**. Level 2 may merge only when the same physical room **and**
comparable scope are both clear; otherwise keep two clusters. Never merge across
floor, instance, or containment (walk-in closet vs master bedroom).

The JSON contract is unchanged: `{"clusters":[{"members","kind"}]}` — **no**
`canonical_space` from the model.

Two rules define what it is allowed to do:

- **It groups, it does not name.** The response carries members only, no
  canonical field. Naming stayed with the model in the first version, and the
  example `{"canonical": "GF-Bedroom1"}` in the prompt was enough for it to coin
  `GF-Living Room` by analogy from labels containing no floor at all.
- **Anchors are immutable.** Every label already placed in a named room is sent
  as context with its group id. The model may attach a loose label to an anchor,
  but a row can never be moved out of one, and a cluster naming two anchors is
  discarded.

Movable labels are `project_level` rows **and** `unique:` rows. Restricting this
to `project_level` is what kept the living-room abbreviations apart: they had
already been parked in their own `unique:` clusters and so were never offered for
merging.

## Kill switches

| Env var | Default | Effect |
| --- | --- | --- |
| `GEMINI_SPACE_LLM` | `1` | `0` disables the overlay. |
| `GEMINI_SPACE_MODEL` | `gemini-3.7-flash` | Override the leftover model (falls back to `GEMINI_COMPARE_MODEL`). |

## Tests

`tests/test_space_compare.py`:

- bedroom aliases merge into one cluster, headed by vendor wording,
- an unqualified bedroom never acquires a floor, and stays separate when both
  floors are quoted,
- `L R` / `LVR` / `Living Room` are one cluster headed `Living Room`,
- kitchen and bedroom stay apart,
- `MBR` and `Walk-in closet` do not merge,
- spot lights / adaptors / electrical → `Project-level`,
- dining and foyer variants fold,
- lounge spellings on the same floor merge,
- a floor-only label is not a room; the description hint wins,
- a third-floor bathroom is never filed as the ground-floor common washroom,
- `Whole Home` / `Full House design` are `project_level`.

New:

- `Used cloth unit` with an MBR description resolves to `Master-Bedroom` via
  `space_source == "description"`,
- `MBR Dressing Mirror` resolves to `Master-Bedroom`,
- a label equal to its own `item_name` never becomes a room,
- `space_confidence` is lower for description-derived rooms than for explicit
  ones.

---

## What to change if this stage breaks

**Symptom: an item name became a room.**
Add the pattern to the is-this-a-room predicate, or — better — make sure S2
recognises it as a work item, which fixes it here for free.

**Symptom: a real room was swallowed into `Project-level`.**
The predicate is too aggressive. Check rule 2: the vendor may legitimately have
a room whose name resembles the item (a room actually called `Pooja` on a pooja
unit line). Tighten the pattern and add a test.

**Symptom: two spellings of one room are still separate.**
Add a room token, an abbreviation pattern, or a qualifier. Do not solve this by
merging in the LLM prompt — deterministic first, always.

**Symptom: the heading names a room or a floor nobody quoted.**
Naming is `choose_space_label`, not the model and not `_room_token`. Either a
`_CLUSTER_LABELS` fallback fired because no member was readable, or an item noun
is missing from `_ITEM_NOUN_RE`. Never add the wording to the prompt.

**Symptom: the heading is an item, like `MBR Study unit`.**
Add its noun to `_ITEM_NOUN_RE`. The row is grouped correctly; only the heading
choice is wrong.

**Symptom: two different rooms merged.**
The serious failure. Find the token that over-matched, narrow it to a word
boundary, and add a "stay apart" test. Prefer under-merging.

**Do not** move a bundle's amount into a room from here. Whether a price reaches
one room or several is S4's decision, and S4 runs after this stage.
