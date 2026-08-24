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

`kitchen`, `living`, `dining`, `foyer`, `utility`, `pooja`, `mbr`/`master`,
`kids`/`children`, `walkin`, `washroom`/`bathroom`, `bedroom` (+ floor and number
qualifiers).

Bedroom numbering and floor prefixes are preserved: `Bedroom 1`, `Ground Floor
Bedroom 1` and `GF Bedroom 1` all reach `gf_bedroom1`, while `Kids bedroom` stays
`kids_bedroom`.

## Merge discipline

Default: **one raw string, one cluster.** Merge only when two labels are clearly
the same physical room. Never merge across room types. `MBR` and `Walk-in closet`
stay separate even though they adjoin, because a wrong merge silently sums two
rooms' costs and is much harder to notice than a missing merge.

## LLM overlay

Same shape as before, with one change: the prompt now receives **row context**
(label plus sample item names and descriptions) rather than bare labels, so it can
tell `Used cloth unit` is an MBR item. Deterministic result computed first; 8s
timeout; any failure returns the heuristic untouched. The overlay may merge and
relabel, never invent a room that no line mentions.

## Kill switches

| Env var | Default | Effect |
| --- | --- | --- |
| `GEMINI_SPACE_LLM` | `1` | `0` disables the overlay. |
| `GEMINI_SPACE_MODEL` | — | Override the model. |

## Tests

`tests/test_space_compare.py` (existing assertions all still hold):

- bedroom aliases merge to `GF-Bedroom1`,
- kitchen and bedroom stay apart,
- `MBR` and `Walk-in closet` do not merge,
- spot lights / adaptors / electrical → `Project-level`,
- dining and foyer variants fold.

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
Add a room token or a qualifier. Do not solve this by merging in the LLM prompt —
deterministic first, always.

**Symptom: two different rooms merged.**
The serious failure. Find the token that over-matched, narrow it to a word
boundary, and add a "stay apart" test. Prefer under-merging.

**Do not** move a bundle's amount into a room from here. Whether a price reaches
one room or several is S4's decision, and S4 runs after this stage.
