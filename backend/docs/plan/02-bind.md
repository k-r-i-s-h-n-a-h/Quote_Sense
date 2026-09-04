# S2 — Bind (work identity)

Decide **what work** each line item is, and give it a `work_key` that is stable
across vendors.

**Input:** `LineItemV1`.
**Output:** `+ work_key, work_label, work_confidence, work_source`.

**Modules**

- `services/work_catalog.py` — new; owns `work_key`.
- `services/tatva_catalog.py` — existing; ObjectId resolution.
- `services/comparator.py::_bind_catalog_ids_from_cache` — existing; fills
  `sub_service_id` / `pricing_method_id` from cached Tatva maps.

---

## The problem this solves

The old join key was the raw vendor string:

```python
df["sub_key"] = sub_service_id if sub_service_id else sub_service
```

On the PDF lane there are no ObjectIds, so the key was free text. Real
consequences from the `Q2OE1CX` vs `QGT3A1I` comparison:

| Vendor A wrote | Vendor B wrote | Result |
| --- | --- | --- |
| `Side table` | `Side Table` | two rows, both half empty |
| `Rolling Shutter` | `Rolling shutters` | two rows |
| `False Ceiling` | `False ceiling with painting` | two rows |
| `Loft` | `Loft unit` | two rows |
| `Crockery Units` | `Crockery Base unit` + `Crockery Wall unit` | three rows |

The first two are pure casing and plural noise. The last three need a synonym
layer. Both are S2's job.

---

## Resolution ladder

`resolve_work(row)` tries each rung in order and stops at the first hit. The rung
that fired is recorded in `work_source`, so a wrong answer is traceable.

| Order | Source | Key format | Confidence |
| --- | --- | --- | --- |
| 1 | Tatva ObjectId already on the row | `tatva:<oid>` | 1.0 |
| 2 | Curated cross-vendor alias | `alias:<slug>` | 0.9 |
| 3 | Exact `TATVAOPS_TAXONOMY` sub-service match | `tax:<slug>` | 0.85 |
| 4 | Description disagrees with `sub_service` | as resolved | 0.6 |
| 5 | Gemini pass over unresolved labels | `alias:<slug>` | 0.5 |
| 6 | Normalised vendor string | `norm:<slug>` | 0.3 |

Rung 6 always succeeds, so `work_key` is never blank. An unmatched label still
compares correctly against an identically-worded label from another vendor — it
just does not benefit from synonym folding.

## Normalisation

`normalize_work_label()` does the cheap, high-value work:

- casefold, strip punctuation and `&`/`and` variance,
- collapse whitespace,
- singularise a trailing `s` (`shutters` → `shutter`),
- drop filler words that never distinguish a work item: `area`, `zone`, `unit`,
  `units`, `provision`, `works`, `work`, `with`, `type`.

This alone collapses `Side table`/`Side Table` and `Rolling Shutter`/`Rolling
shutters` with no alias entry needed.

Careful: filler-word removal is deliberately conservative. `Loft` and `Loft unit`
collapse because `unit` is filler; `Base Unit` and `Wall Unit` do **not**
collapse because `base` and `wall` survive.

## Aliases

`WORK_ALIASES` maps a normalised vendor string to a canonical slug. Many-to-one
is the point:

```python
"false ceiling": "false_ceiling",
"false ceiling with painting": "false_ceiling",
"crockery": "crockery_units",
"crockery base": "crockery_units",
"crockery wall": "crockery_units",
```

**1:N needs no special machinery.** Mapping both `Crockery Base unit` and
`Crockery Wall unit` to `crockery_units` lets the S5 groupby sum them into one
figure opposite vendor A's single `Crockery Units` line. The existing pivot does
the arithmetic; S2 only has to agree on the key.

## Description-wins rule

A vendor sometimes puts the wrong `sub_service` on a line. In the golden fixture,
`QGT3A1I` line 36 has `sub_service = "MBR Used cloth units"` but
`description = "Dressing Mirror"` and `space_raw = "MBR Dressing Mirror"`. Taking
`sub_service` at face value files a mirror under used-cloth storage.

Rule: when `sub_service` resolves to a key that contradicts a confident match
from `item_name`/`description`, and the description is short and specific, prefer
the description. Record `work_source = "description"` and drop confidence to 0.6
so the UI can flag it.

This rule is intentionally narrow. It fires only on contradiction, never to
"improve" an already-consistent row.

## Ancillary intent split

A catalog title is not enough to decide that two lines are the same purchase.
When a line explicitly says **dismantling/demolition**, **cleaning**, or
**shifting/relocation**, S2 appends that intent to its otherwise-normal
`work_key` and display label:

```text
Wardrobe                 → alias:wardrobe
Wardrobe — dismantling   → alias:wardrobe::intent:dismantling
```

This keeps a `70 sqft @ ₹100` wardrobe-dismantling line out of a `40 sqft @
₹1,550` new-wardrobe line. S5 can then compare the fabrication quantities and
rates without summing unlike work. Amounts remain on their original lines and
space totals remain unchanged.

The matcher is deliberately narrow and verb-driven. A generic `Civil` line is
not automatically merged with `Wardrobe — dismantling`; it only becomes
`Civil — dismantling` when its own text explicitly says dismantling. We do not
reallocate civil, cleaning, or shifting charges to make two quotes look
comparable.

## LLM pass

Mirrors the S3 overlay pattern exactly: deterministic result computed first, one
Gemini call for the leftovers, 8s timeout, any failure returns the deterministic
mapping untouched.

The prompt receives only labels that reached rung 6, plus their sample
descriptions for context, and is asked to group them into equivalence classes. It
may **only** merge labels — it cannot split a deterministic alias or invent a
taxonomy node.

## Kill switches

| Env var | Default | Effect |
| --- | --- | --- |
| `GEMINI_WORK_LLM` | `1` | `0` disables rung 5 entirely. |
| `GEMINI_WORK_MODEL` | `gemini-3.7-flash` | Override leftover work merge (falls back to `GEMINI_COMPARE_MODEL`). |

With the switch off, S2 is pure and deterministic. The test suite runs this way.

## Tests

`tests/test_work_catalog.py`:

- casing and plural collapse (`Side table` ≡ `Side Table`),
- alias folding (`False Ceiling` ≡ `False ceiling with painting`),
- 1:N folding (both crockery lines share vendor A's key),
- `Base Unit` and `Wall Unit` stay distinct,
- description-wins fires on the mirror row and nowhere else,
- explicit dismantling/cleaning/shifting stays separate from installation,
- ObjectId beats every heuristic.

---

## What to change if this stage breaks

**Symptom: two lines that should compare are still on separate rows.**
Print both `work_key`s. If they differ only by noise, extend
`normalize_work_label`. If they are genuine synonyms, add a `WORK_ALIASES` entry.
Prefer the alias table over widening the normaliser — widening risks false
merges everywhere.

**Symptom: two different works merged into one row.**
Almost always over-aggressive filler-word removal. Remove the offending word from
the filler list and add a test asserting the two stay apart. This is the more
dangerous failure of the two: a false merge silently adds unrelated amounts.

**Symptom: the taxonomy changed.**
Only this stage. Add alias entries for the new sub-service names. No pipeline
logic changes.

**Symptom: the LLM is producing bad merges.**
Set `GEMINI_WORK_LLM=0`, confirm the deterministic path is correct, then tighten
the prompt. Never fix an LLM merge by hardcoding around it downstream.

**Do not** touch `space_clusters.py` from here. If the room is wrong, that is S3
— even though S3 now calls into this module to recognise item-as-space labels.

## Tatva pricing-method ObjectIds (market-rate, not matrix join)

Owned by [../../../PLAN_RECOMMENDATIONS.md](../../../PLAN_RECOMMENDATIONS.md)
and locked in
[../../../ACTION_RECOMMENDATIONS.md](../../../ACTION_RECOMMENDATIONS.md).
Do not change that flow from this comparison-bind doc.

Vendor `/by-category` and `/suggest` attach `service_id` / `sub_service_id` /
`pricing_id` from `market_moving_averages` columns only. Live Tatva catalog
aliases (e.g. `Square Feet` → Area) must not overwrite those IDs.

Bundle lookup stays label-based (`service_type + category + sub_service +
pricing_method`). Inbound `pricing_id` / `sub_service_id` reverse-map via the
same MA columns (and `_PM_STALE_ID_ALIASES` for pre-reset interiors ids) so
`/suggest` still finds the row after the static JSON maps were removed.

Registering one catalog row must not overwrite another row's label (inactive
`Square Feet` must not steal `Area – Direct Entry (sq ft)`). That rule is for
inbound label resolution and matrix bind only — not for recommend responses.
