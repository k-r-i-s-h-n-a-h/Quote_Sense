# S4 — Bundles (price scope)

Decide **how wide** each line's price reaches: one room, several rooms, or the
whole project.

**Input:** `LineItemV1` + S2 + S3 fields.
**Output:** `+ scope, bundle_id, bundle_label, bundle_family, covered_space_ids,
covered_work_keys, overlap_flags`.

**Module:** `services/bundles.py` (absorbs the old `work_rollup.py`).

---

## The problem this solves

This is the hard one, and it is the reason the matrix cannot be a single
space-grouped table.

One vendor prices all electrical as a single lumpsum. Another itemises lighting
per room — living, kitchen, sofa, kids bedroom. A strictly space-grouped matrix
has **nowhere correct** to put the lumpsum. The old code dumped it in
`Project-level`, which quietly removed it from every room total and made the two
vendors' room subtotals non-comparable without saying so.

### The old rollup almost never fired

`apply_work_rollup` required at least two vendors to have candidate rows:

```python
if len(vendors) < 2:
    return df
```

A candidate had to be lighting-family **and** either on `Project-level` or
lump-priced. In the golden comparison:

- Vendor B had five electrical lines, three of which reached `Project-level`.
- Vendor A had exactly one electrical line — `CO light provision`, priced by
  running length, sitting in `Modular Kitchen`. Not `Project-level`, not lump, so
  **not a candidate at all**.

The candidate subset therefore contained one vendor, the guard tripped, and the
function returned the frame untouched. Output read `PROJECT-LEVEL Rs 83,544` for
B against `N/A` for A — stating that A quoted no electrical, when A had quoted
Rs 17,700 of it under the kitchen.

### And it only knew about lighting

The actual lumpsum in the golden comparison is not lighting at all:

| Vendor A | Vendor B |
| --- | --- |
| `Hardwares` Rs 1,00,300, Fixed Amount / Lump Sum, description lists *5 tandem, 1 bottle unit, Rolling shutter, Gola handles, Cutlery tray, Anti skid mat* | `Bottle Pullouts` 6,353 + `Tandem Drawers` 20,709 + `Pvc Cutlery tray` 1,929 + `Soft closing hinges` 6,814 + `Soft closing channels` 1,392 = **Rs 37,198** |

`work_rollup` had no concept of a hardware family, so these never met. A
Rs 63,000 scope difference was invisible.

### An undetected overlap

Vendor A's `Hardwares` description names *Rolling shutter*, and vendor A **also**
bills `Rolling Shutter` separately at Rs 27,258. Either the lumpsum
double-counts it or the separate line does. Nothing detected this.

---

## Design

### Per-line bundle detection

A line is a bundle when **both** hold:

1. `pricing_method` matches lump / fixed amount / per project, **and**
2. the description enumerates two or more distinct work items or rooms.

Condition 2 is what distinguishes a genuine bundle from an ordinary
single-item fixed price. `Wall Decor` at a lump Rs 8,850 for one room is not a
bundle; `Hardwares` listing six accessories is.

Detection is **per line**, with no cross-vendor precondition. The old
two-vendor guard is gone. A bundle is a property of how one vendor priced one
line, and it stays true whether or not anyone else itemised.

Enumeration of the description is S2-backed: each comma-separated fragment is
resolved with `work_slug_for` (aliases + taxonomy), then a small substring
fallback for phrases like `5 tandem` that never match as a whole label. Adding
a sub-service to the taxonomy (or an alias) teaches the detector the new word.
Unknown fragments do **not** count: slugifying leftover prose is what turned
TCS wall décor + blinds + tissue into a fake `Mixed (Wall decor)` package.

`&` is not a list separator. `Greenply & Century` is a brand pair.

Mixed leftover packages are emitted **one vendor line per row**. Summing every
`bundle_family == mixed` line invents a figure no vendor quoted. Hardware and
lighting families still pair as one family row.

### Families

`FAMILY` maps work keys to a coarse family so a bundle can find its counterpart
without an exact key match:

`lighting` (light, electrical, adaptor, spot, profile, strip, point creation),
`hardware` (tandem, hinge, channel, pullout, cutlery, handle, shutter mechanism,
accessories), `painting`, `ceiling`, `civil`.

Family matching is what lets one `Hardwares` lumpsum pair with five differently
named accessory lines.

### Always emit the comparison

For every family present in **any** vendor's quote, emit a bundle-tier row.
Both sides get a figure:

- the bundling vendor contributes its lumpsum, `basis = "bundle"`,
- an itemising vendor contributes the sum of its lines in that family,
  `basis = "itemized"`,
- a vendor with nothing in the family gets `0` and `basis = "none"`.

So the electrical case now reads `A Rs 17,700 (itemized)` against
`B Rs 83,544 (itemized)` instead of `N/A` against `Rs 83,544`. The gap becomes a
visible scope difference rather than a silent hole.

`basis` matters. A number reached by summing five lines is not the same kind of
number as a single lumpsum, and the UI is required to say which is which.

Each vendor also gets `placement`: `space` (figure already in room rows),
`project` (one whole-home figure), `bundle` (package), or `mixed`. The UI names
the quote and says where the rupees already sit. It does not change the addition.

### Overlap detection

When a bundle's description names a work item the same vendor also bills on its
own line, record that work key in `overlap_flags`.

**Flag, never correct.** We cannot know whether the lumpsum includes the separate
line or duplicates it — only the vendor knows. Auto-subtracting would invent a
number. The UI shows a warning and the user asks the vendor.

### Bundles never enter space totals

The rule that keeps the matrix honest. A bundle's `amount` contributes to the
bundle tier only. For each room the bundle covers, the coverage entry for that
vendor becomes `incl_in_bundle` and the room is marked `comparable = false`.

The alternative — pro-rata allocating the lumpsum across rooms — was considered
and rejected. It produces a per-room figure the vendor never quoted, and once
that number is in a table someone will treat it as real.

### Bundled zones: a whole space priced as one scope

The section above is about one bundled *line*. A vendor can also bundle a whole
*zone*: INT360's `Common` space carried plumbing, electrical, grill, window and
false ceiling as five generic lines, while the other quote scoped the same work
per room in detail. Line-matching those against each other can only produce
invented pairings — `Plumbing` (whole house) against a bathroom's plumbing
labour is not a comparison.

`bundle_zone_map` marks a space `BUNDLE_NOT_DECOMPOSABLE` when all of:

- the space label is generic (`Common`, `Miscellaneous`, `Others`, …) rather
  than a room. A generic word plus a room-type noun (`Common Washroom`,
  `Common Bathroom`) is a room, not a catch-all; bare `Common` still is,
- its lines span ≥ `BUNDLE_ZONE_MIN_CATEGORIES` distinct trades from the fixed
  `TRADE_CATEGORIES` list, and
- it holds ≥ `BUNDLE_ZONE_MIN_LINES` lines.

The trade list is fixed on purpose. Deriving categories from the vendor's words
would let a detailed quote look "multi-trade" and suppress comparisons that are
perfectly valid — a bedroom legitimately holds carpentry, electrical and civil
work, and must never be treated as a bundled zone. Requiring a generic label is
what keeps real rooms out.

Effect: `bundle_zone_rows` emits one zone-level row per bundled zone, and the
matching `SpaceNote` carries `suppress_line_matching = true`, so the UI and the
PDF print the zone total and the note instead of its line rows. The rupees are
untouched — only the pairing is refused.

### Cross-scope possible matches (S4b)

`services/cross_scope.py` handles the opposite failure. One vendor put a whole
washroom fit-out inside `Walkin Closet Area 1st Floor`; the other quoted the
same work as `First Floor Bathroom`. The containment guard is right to keep
those spaces apart — but with disjoint `space_id`s, no space-tier row can ever
pair them, so both printed as unrelated N/A blocks, which told the client
"nobody else quoted this". That was false.

`cross_scope_candidates` classifies lines into `FUNCTIONAL_GROUPS` (bathroom
fit-out, wardrobe/storage, structural walls, and washroom civil / tiling)
and emits a `POSSIBLE_CROSS_SCOPE_MATCH`
when, for one group, the two vendors' spaces are entirely disjoint and both
sides exceed `CROSS_SCOPE_MIN_INR`. If any space already holds both vendors,
nothing is flagged: the space tier is comparing that work honestly.
`washroom_civil` also requires a wet-area container signal (`bath` / `wash` /
`toilet` / `wc` on the space label or description) so kitchen or living-room
tiling is not flagged.

Abstain and flag, in both directions:

- the totals are **never** merged, so no tier total moves and reconciliation is
  unaffected;
- the affected rows stop saying "did not quote this line" and instead name the
  other vendor's space with a confirm-with-vendor note
  (`apply_cross_scope_notes`).

---

## Kill switches

None. S4 is fully deterministic: regex on `pricing_method`, token matching on
`description`, and set arithmetic. No LLM, no network.

## Tests

`tests/test_bundles.py`:

- `Hardwares` with a six-item description is detected as a bundle,
- a lump-priced single item (`Wall Decor`, Rs 8,850) is **not**, even when the
  description mentions a brand pair with `&`,
- unrelated leftover lumpsums (wall décor + blinds + tissue) are never one
  Mixed package,
- two mixed packages from the same vendor stay two rows,
- the hardware bundle pairs against Rs 37,198 with the right `basis` values,
- the lighting family emits a row with both vendors non-zero, proving the
  two-vendor guard is gone,
- lighting `placement` is `space` for the kitchen line and `mixed` when the
  counterpart spans rooms and Whole home,
- `overlap_flags` contains the rolling-shutter key,
- a bundle's amount never appears in any space total,
- `tests/test_space_compare.py::test_wardrobe_does_not_roll_into_lighting` — a
  non-family line is untouched.

---

## What to change if this stage breaks

**Symptom: an ordinary fixed-price line was treated as a bundle.**
Condition 2 over-fired. Tighten the enumeration parser — it should need genuine
separators (commas, `and`, `+`, `/`) and two or more recognised work tokens, not
just a long sentence or a brand name joined with `&`.

**Symptom: a real bundle was missed.**
Check `pricing_method` first; vendors invent new wording for lump pricing
constantly, and the regex is the usual culprit. Then check whether the
description's items are recognised — enumeration goes through S2
(`work_slug_for`), so an unrecognised fragment is really an alias or taxonomy
gap. A comma-separated residential list (false ceiling, TV units, sofa) must
still count as a bundle once those words are in the catalog; do not bring back
slugify-unknown.

**Symptom: unrelated lumpsums appeared as one Mixed package.**
`bundle_comparison_rows` summed leftover `mixed` bundles. Emit one row per
mixed `bundle_id` instead.

**Symptom: the wrong counterpart lines were summed.**
The `FAMILY` map is too coarse. Split the family rather than special-casing the
pair.

**Symptom: room totals changed after a bundle appeared.**
A real bug — bundle amounts must never reach the space tier. Check the `scope`
filter in S5, not this stage.

**Do not** allocate a bundle across rooms to make a room total comparable. That
decision was made deliberately; if it is ever revisited, it goes in as a clearly
labelled secondary view, never as the headline number.
