# S0 — Contracts

Single source of truth for the fields that flow between pipeline stages.
See [../../../PLAN.md](../../../PLAN.md) for the stage map and change protocol.

Current versions: **`LineItemV1`**, **`MatrixV1`**.

---

## LineItemV1 — emitted by S1

One row per vendor line item. Both input lanes (PDF extraction and Tatva/Mongo
payload) must produce these fields before S2 runs.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `vendor_name` | str | yes | Unique vendor key, `"{company} ({source})"`. Used as the matrix column name. |
| `company` | str | yes | Display name without the source suffix. |
| `source_filename` | str | yes | PDF filename or quote number. |
| `quote_number` | str | no | `""` when unknown. |
| `quote_date` | str | no | `YYYY-MM-DD` or `""`. |
| `gst_mode` | str | no | Tatva lane: `exclusive` / `inclusive` / `mixed` / `""`. From `workSummary.exclusiveGst` / `inclusiveGst`. PDF lane: `""`. |
| `grand_total` | float | yes | Quote-level total; repeated on every row of that quote. |
| `service_category` | str | yes | Blank becomes `"Other"`. |
| `sub_service` | str | yes | Vendor's own label. Blank becomes `"General"`. **Never trusted as a join key.** |
| `item_name` | str | no | Verbatim line title. |
| `description` | str | no | Free text. Carries room hints and bundle contents. |
| `work_title` | str | no | Tatva field; the fallback source for `space_raw`. |
| `space_raw` | str | yes | Vendor's Space/Zone string, verbatim. May be an item name, not a room. |
| `pricing_method` | str | yes | e.g. `"Area – Direct Entry (sq ft)"`, `"Fixed Amount / Lump Sum"`. |
| `quantity` | float | no | |
| `rate` | float | no | |
| `amount` | float | yes | Line total in rupees. The only figure the matrix sums. Tatva lane uses billed `pricingInput.grandTotal` (GST included), not the pre-GST `amount`. |
| `service_type` | str | no | `essential` / `midlevel` / `luxury`. |
| `sub_service_id` | str | no | Tatva ObjectId when the payload lane supplies one. |
| `pricing_method_id` | str | no | Tatva ObjectId. |
| `line_id` | str | yes | Stable id for this source line. Supabase `quote_items.id`, Tatva workItem `_id`, else `<vendor slug>_<n>`. Every row the client sees must trace back to one of these. |

**Invariants**

- `amount` is numeric and non-negative. NaN becomes `0.0`.
- Every string field is stripped; `None`/`NaN` becomes `""`.
- `space_raw` falls back to `work_title` when empty.
- `line_id` is unique within the comparison and never regenerated mid-run.
  `services/lineage.ensure_line_ids(df)` fills it before S2.

---

## S2 additions — work identity

| Field | Type | Notes |
| --- | --- | --- |
| `work_key` | str | Canonical join key. This, with `space_id`, identifies a matrix row. Never blank. |
| `work_label` | str | Human-readable name for `work_key`, shown in the UI. |
| `work_confidence` | float | `0.0`–`1.0`. |
| `work_source` | str | How the key was decided: `alias`, `taxonomy`, `normalized`, `description`, `llm`, or `fallback`. |

`work_key` formats:

- `tatva:<objectid>` — Tatva ObjectId was present (highest trust).
- `tax:<slug>` — matched a `TATVAOPS_TAXONOMY` sub-service.
- `alias:<slug>` — matched a curated cross-vendor alias.
- `norm:<slug>` — normalised vendor string, no catalog match.

Two lines from different vendors compare **only** when their `work_key` is equal.

---

## S3 additions — space identity

| Field | Type | Notes |
| --- | --- | --- |
| `space_id` | str | Canonical cluster id, e.g. `mbr`, `kitchen`, `project_level`. |
| `space` | str | Display heading, taken from the vendors' own wording for this cluster, e.g. `Master Bedroom`. Cosmetic — group and assert on `space_id`. |
| `space_confidence` | float | `0.0`–`1.0`. |
| `space_source` | str | `space_raw`, `description`, `item_name`, `llm`, or `project_level`. |
| `contained_in` | str | Parent `space_id` when this room is nested. Empty if none. Not a merge. |
| `space_ambiguous` | bool | The vendor named a room kind that exists more than once and gave no number. |
| `space_note` | str | Confirm-before-allocating note for an ambiguous space. Empty otherwise. |
| `qty_scope_note` | str | Set when a per-room line's quantity exceeds the numbered instances of that room. A note, never a block. |

`space_id == "project_level"` means the line is not attributable to a room.
That is a real outcome, not a failure.

`space_id == "unassigned:<vendor's exact label>"` means the vendor's own words
did not name a specific numbered room and no catalog alias did either. The
rupees stay on their own row. Guessing a room invents an allocation the vendor
never made; blanking it hides money.

---

## S4 additions — price scope

| Field | Type | Notes |
| --- | --- | --- |
| `scope` | str | `space`, `bundle`, or `project`. |
| `bundle_id` | str | Set when `scope == "bundle"`, else `""`. |
| `bundle_label` | str | Display name for the bundle. |
| `bundle_family` | str | Family used for counterpart matching, e.g. `lighting`, `hardware`. |
| `covered_space_ids` | list[str] | Spaces the bundle price reaches. Empty means unknown/all. |
| `covered_work_keys` | list[str] | Work keys the bundle price includes, parsed from the description. |
| `overlap_flags` | list[str] | Work keys the same vendor also bills separately. |
| `trade_category` | str | One of the fixed trades in `services/bundles.TRADE_CATEGORIES`, or `""`. |
| `bundle_zone` | bool | True when this line sits in a space that groups ≥2 distinct trades under generic titles. |

**Scope rules**

- `space` — attributable to exactly one room. The default.
- `bundle` — one price covering several work items and/or several rooms.
- `project` — genuinely whole-project (transport, cleaning, service charges).

**Hard rule:** a `bundle` row's `amount` never contributes to a space total.
Allocating a lumpsum across rooms would invent numbers the vendor never quoted.

---

## MatrixV1 — emitted by S5

```jsonc
{
  "vendors": ["Infosys (Q2OE1CX)", "TCS (QGT3A1I)"],
  "vendorMeta": { "<vendor>": { "company": "", "filename": "", "quote_number": "", "quote_date": "", "gst_mode": "", "phone": "" } },
  "chartData": [{ "vendor": "...", "total": 0 }],
  "spaceTier": [ /* SpaceRow */ ],
  "bundleTier": [ /* BundleRow */ ],
  "projectTier": [ /* SpaceRow with space_id project_level */ ],
  "coverage": [ /* CoverageEntry */ ],
  "crossScope": [ /* CrossScopeRow */ ],
  "bundleZones": [ /* BundleZoneRow */ ],
  "spaceNotes": [ /* SpaceNote */ ],
  "reconciliation": { /* Reconciliation */ },
  "tableData": [ /* legacy flat rows, = spaceTier + projectTier */ ],
  "contract_version": "MatrixV1",
  "session_id": "..."
}
```

### Match tiers

Every row carries `match_tier`. The three non-`MATCH` tiers are abstentions:
the pipeline says what it does not know instead of forcing a pairing.

| Tier | Meaning | Effect on the output |
| --- | --- | --- |
| `MATCH` | Same `work_key`, same `space_id`. | Compared normally. |
| `POSSIBLE_CROSS_SCOPE_MATCH` | Same functional purpose, structurally different containers (embedded vs standalone, differently numbered rooms). | Never merged. Both figures shown side by side with a confirm-with-vendor note. |
| `BUNDLE_NOT_DECOMPOSABLE` | The vendor priced a multi-trade zone as one scope. | Line-level matching suppressed; zone total only. |
| `UNASSIGNED` | The vendor's space label names no specific numbered room. | Own row, with a confirm-before-allocating note. |

Structural guards (containment, floor, numbered-room identity) still override
model confidence. These tiers add ways to abstain; they do not loosen a guard.

### SpaceRow

| Field | Type | Notes |
| --- | --- | --- |
| `category` | str | |
| `space_id` | str | |
| `space` | str | Display label. |
| `space_raw` | str | All vendor aliases, joined with ` · `. |
| `work_key` | str | |
| `sub_service` | str | Display label for the work. |
| `pricing_method` | str | |
| `breakdown` | list | `{vendor, item, amount}` per contributing line. |
| `bundle_family` | str | S4 family, or `""`. Lets the UI hide Whole-home rows a scattered recap already compares. |
| `contained_in` | str | Parent `space_id` when this room is nested (walk-in → mbr). Empty if none. Not a merge. |
| `measures` | dict | `{ "<vendor>": { quantity, rate, pricing_method, pricing_method_id, description } }` from the payload. Quantity/rate stay 0 when the vendor left them blank. Description is verbatim, not a work list. `pricing_method_id` is what gates quantity language. |
| `source_line_ids` | list[str] | Every `line_id` this row was built from, both vendors. **Always populated.** |
| `line_ids` | dict | `{ "<vendor>": [line_id, ...] }` — the same lineage, per vendor. |
| `combined_from` | list[str] | Set only when one display row merged several lines from the *same* vendor. |
| `combines` | dict | `{ "<vendor>": ["Profile lights", "Strip lights"] }` — those lines' own titles, for the `combines:` note. |
| `match_tier` | str | See [Match tiers](#match-tiers). |
| `space_note` | str | Carried through from S3 for an `UNASSIGNED` space. |
| `qty_scope_note` | str | Carried through from S3. |
| `cross_scope_note` | str | Set when S4b found this row a possible match in another vendor's space. Replaces the "did not quote this line" sentence, which would be false. |
| `named_in` | dict | Optional. `{ "<vendor>": { label, amount, space, intent, also_names } }` when that vendor named this ancillary work in a Civil/other description. Not a coverage status. |
| `summary` | str | Deterministic Comparison Summary sentence. Empty when there is nothing to say. |
| `<vendor name>` | int | One key per vendor; rupees, `0` when absent. |

### BundleRow

| Field | Type | Notes |
| --- | --- | --- |
| `bundle_id` | str | |
| `bundle_label` | str | |
| `bundle_family` | str | |
| `covered_spaces` | list[str] | Display labels. |
| `covered_items` | list[str] | Work labels named in the bundle description. |
| `overlap_flags` | list[str] | |
| `basis` | dict | `{ "<vendor>": "bundle" \| "itemized" \| "none" }` — how each vendor's figure was arrived at. |
| `placement` | dict | `{ "<vendor>": "space" \| "project" \| "bundle" \| "mixed" \| "none" }` — where those rupees already sit. |
| `takeaway` | dict or omitted | `{ kind, text }` when one vendor is a package and another is itemised with a large gap. Never on scattered recaps. |
| `<vendor name>` | int | Bundler's lumpsum, or the counterpart's summed itemised lines. |

`basis` is what stops the row from lying. A figure produced by summing five
itemised lines is not the same kind of number as a single lumpsum, and the UI
says so.

### CoverageEntry

| Field | Type | Notes |
| --- | --- | --- |
| `space_id` | str | |
| `space` | str | |
| `vendor` | str | |
| `status` | str | `quoted`, `incl_in_bundle`, `incl_in_parent`, or `not_quoted`. |
| `bundle_id` | str | Set when `status == "incl_in_bundle"`. |
| `parent_space` / `parent_space_id` | str | Set when `status == "incl_in_parent"`. |
| `comparable` | bool | `false` when a bundle or nested parent overlaps this space for any vendor. |

This is what turns a misleading `N/A` into `incl. in Hardwares bundle`.

### CrossScopeRow

Emitted by S4b (`services/cross_scope.py`) for one functional group where the
two vendors used **disjoint** `space_id`s, so no space-tier row can ever pair
them.

| Field | Type | Notes |
| --- | --- | --- |
| `group` | str | Functional group slug, e.g. `bathroom_fitout`. |
| `label` | str | Display name for the group. |
| `match_tier` | str | Always `POSSIBLE_CROSS_SCOPE_MATCH`. |
| `vendors` | dict | `{ "<vendor>": { space_id, space, spaces, amount, line_count, container } }`. `container` is `standalone` or `embedded`. |
| `note` | str | The confirm-with-vendor sentence, both figures named. |
| `source_line_ids` | list[str] | Lineage for both sides. |

The totals are **never** merged. This row is a cross-reference, not a
comparison, and it does not enter any tier total.

### BundleZoneRow

| Field | Type | Notes |
| --- | --- | --- |
| `space_id` / `space` | str | The bundled zone. |
| `vendor` | str | The vendor who bundled it. |
| `amount` | int | Zone total — the only figure comparable here. |
| `categories` | list[str] | Trades found in the zone (≥2). |
| `line_count` | int | |
| `match_tier` | str | Always `BUNDLE_NOT_DECOMPOSABLE`. |
| `note` | str | Names the vendor and the trades, and says why it can't be compared line-by-line. |
| `source_line_ids` | list[str] | |

### SpaceNote

One entry per space that needs a caveat printed above its rows.

| Field | Type | Notes |
| --- | --- | --- |
| `space_id` / `space` | str | |
| `match_tier` | str | `UNASSIGNED` or `BUNDLE_NOT_DECOMPOSABLE`. |
| `note` | str | Rendered in the UI and the PDF. |
| `suppress_line_matching` | bool | `true` for a bundled zone: the UI and PDF must not print its line rows. |

### Reconciliation

The gate. Computed in `services/lineage.reconcile_vendor_totals`.

| Field | Type | Notes |
| --- | --- | --- |
| `ok` | bool | `false` blocks PDF export. |
| `tolerance_inr` | float | Rounding allowance per vendor. |
| `vendors` | dict | `{ "<vendor>": { source_total, rows_total, delta, row_count, line_count, ok, unaccounted_line_ids, unaccounted[], unexpected_line_ids } }`. |

`unaccounted[]` entries carry `{ line_id, label, space, amount }` so a blocked
export can name the money it lost. GST, discount and TatvaOps service-charge
lines are excluded from `source_total` as documented out-of-scope.

**Hard rule:** a comparison whose `reconciliation.ok` is `false` never renders
a client PDF. `scripts/check_reconciliation.py` applies the same gate in CI.

---

## Backward compatibility

`tableData` is retained so existing frontend code and the PDF export keep working
before the UI is updated. It equals `spaceTier + projectTier` and carries the same
per-vendor amount keys as before. New consumers should read the tiers directly.

---

## Validation

`backend/services/contracts.py` exposes `validate_line_items(df, stage)` and
`validate_matrix(payload)`. `run_comparison` calls the row validator after every
stage when `QUOTESENSE_VALIDATE_CONTRACTS=1` (always on in tests). A failure
raises `ContractError` naming the stage, field and row — so a broken run points at
one stage instead of the whole pipeline.

---

## What to change if this stage breaks

`00-contracts.md` breaking means a field definition is wrong or missing. Update
the table here first, then the owning stage's doc, then the code. Never the other
way round — the contract is the thing other stages trust.
