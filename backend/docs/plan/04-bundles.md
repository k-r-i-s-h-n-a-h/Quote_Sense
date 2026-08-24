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

---

## Kill switches

None. S4 is fully deterministic: regex on `pricing_method`, token matching on
`description`, and set arithmetic. No LLM, no network.

## Tests

`tests/test_bundles.py`:

- `Hardwares` with a six-item description is detected as a bundle,
- a lump-priced single item (`Wall Decor`, Rs 8,850) is **not**,
- the hardware bundle pairs against Rs 37,198 with the right `basis` values,
- the lighting family emits a row with both vendors non-zero, proving the
  two-vendor guard is gone,
- `overlap_flags` contains the rolling-shutter key,
- a bundle's amount never appears in any space total,
- `tests/test_space_compare.py::test_wardrobe_does_not_roll_into_lighting` — a
  non-family line is untouched.

---

## What to change if this stage breaks

**Symptom: an ordinary fixed-price line was treated as a bundle.**
Condition 2 over-fired. Tighten the enumeration parser — it should need genuine
separators (commas, `&`, `+`) and two or more recognised work tokens, not just a
long sentence.

**Symptom: a real bundle was missed.**
Check `pricing_method` first; vendors invent new wording for lump pricing
constantly, and the regex is the usual culprit. Then check whether the
description's items are recognised — an unrecognised item token is really an S2
alias gap.

**Symptom: the wrong counterpart lines were summed.**
The `FAMILY` map is too coarse. Split the family rather than special-casing the
pair.

**Symptom: room totals changed after a bundle appeared.**
A real bug — bundle amounts must never reach the space tier. Check the `scope`
filter in S5, not this stage.

**Do not** allocate a bundle across rooms to make a room total comparable. That
decision was made deliberately; if it is ever revisited, it goes in as a clearly
labelled secondary view, never as the headline number.
