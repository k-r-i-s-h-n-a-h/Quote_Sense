# ACTION_RECOMMENDATIONS.md — invariants agents must not reverse

This file is the lock on **vendor market-rate recommendations** that already
work. Comparison has its own lock in [ACTION.md](ACTION.md). Do not mix them.

If a later change looks like an improvement but violates one of these rules,
**do not ship it**. Update the owning step in
[PLAN_RECOMMENDATIONS.md](PLAN_RECOMMENDATIONS.md) to honour the rule; do not
weaken the rule to make a catalog fetch or a heuristic easier.

Do **not** keep editing `backend/services/market_rate.py`,
`backend/services/tatva_catalog.py`, or `/api/market-rate/*` because a new
task "needs IDs" or "needs live catalog names". That path is done.

---

## 1. Response ObjectIds come from Supabase only (R3 / R4)

`/api/market-rate/by-category` and `/api/market-rate/suggest` (and `/lookup`,
`/recommend`) return `service_id`, `sub_service_id`, and `pricing_id` from
`market_moving_averages` columns (`service_id`, `sub_service_id`,
`pricing_method_id`).

**What the vendor form must see:** the ObjectId stored on that MA row for this
environment.

**What they must not see:** an id taken from the live Tatva catalog, from
deleted static JSON maps, or from an alias overlay. That path swapped active
**Area – Direct Entry (sq ft)** for inactive **Square Feet**.

`list_market_rates_by_category` and `recommend_rate` must not call
`ensure_live_catalog()`. `_label_ids` / `_slim_bulk_item` copy MA columns
only.

Inbound `/suggest` may reverse-map ObjectIds → labels (MA columns plus
`_PM_STALE_ID_ALIASES`) so lookup can stay label-based. That reverse map is
for **finding** the row. It must not rewrite the ids on the way out.

---

## 2. Never copy ObjectIds across environments

Residential Interiors `service_id` is the same on staging / test / prod:
`6926b1978ba6a3cfc5a191ce`.

Pricing-method and sub-service ObjectIds **differ by env**. Area on DEV is
not Area on TEST is not Area on prod. Loft is not Loft & Door Type.

Do not UPDATE test or prod MA from a DEV CSV. Do not bake env ObjectIds into
`backend/data/seed_market_moving_averages_full.sql` — that seed is labels +
rates only. Fill ids in the env's own `market_moving_averages` table from
that env's Tatva admin catalogs.

---

## 3. Suggestion only when the entered rate is above the base (R4)

The recommended base is a single number (`rate_moving_average`). There is no
±% band.

- No `entered_rate` → `recommend: false` (preload; no banner).
- `entered_rate` ≤ base → `recommend: false` (silent).
- `entered_rate` > base (even ₹1) → `recommend: true`.

Do not reintroduce interval logic. Do not show a suggestion because the
catalog "has a nicer name". `/by-category` may list bases; the banner still
follows this rule.

---

## 4. Change protocol

If `/by-category` returns the wrong ObjectId, fix **R3** (stop overlaying
catalog). If `/suggest` cannot find a row, fix **R2** (inbound reverse-map).
If the banner fires at or below base, fix **R4**.

Do not "fix" a wrong id by fetching live Tatva catalogs on the list/suggest
path. Do not fold two MA rows into one because comparison S2 aliases `Loft`
and `Loft & Door Type` for the matrix. That alias is comparison-only.

When a rule here is already satisfied, **do not touch the modules**. Append
a new section if product adds a new rule. Never rewrite §1–4.

---

## 5. Distinct catalog rows stay distinct

Each MA row is one bundle: `service_type` + `service_category` +
`sub_service` + `pricing_method`.

Wardrobe and Wardrobes, Loft and Loft & Door Type, Area and Square Feet, Per
Visit and Per Visit / Service Call are different rows when the env catalog
treats them as different. Response ids and labels must stay that row's
values.

Comparison `work_catalog` / S2 filler-word collapsing must not be applied to
market-rate list or suggest output.

---

## 6. Writes vs reads

Recommendations **read** `market_moving_averages`. Compare sessions do not
write MA. Only finalized-quote apply may update rates, and only when
`MARKET_RATE_UPDATES_ENABLED` is not frozen.

Do not harvest ids or rewrite MA from a comparison run "to keep catalogs
fresh". Seed / env UPDATE is the id source for **existing** rows.
`sync-catalog` is an explicit ops endpoint, not part of list/suggest.

---

## 7. Finalize may insert a new combo for that tier only

A finalized quote either **blends** an existing MA bundle or **inserts one
new row** for `service_type` + `service_category` + `sub_service` +
`pricing_method`.

- Known combo (Wardrobe + Area – Direct Entry sq ft, Essential) → update
  that row's rate and weight. Do not change the blend formula.
- New combo (Wardrobe + Area in sq mm, Essential) → INSERT Essential only.
- Mid and Luxury of that new combo stay **absent** until a vendor finalizes
  that tier. Do not copy Essential's rate across tiers. Do not insert
  placeholder null-rate siblings.
- Insert only when the quote line has Tatva `sub_service_id` and
  `pricing_method_id`. Label-only junk does not create MA rows. Copy those
  ids (and `service_id` when present) onto the new row — never from
  `ensure_live_catalog()`.
- Compare still does not write MA. `MARKET_RATE_UPDATES_ENABLED=false`
  still freezes all writes.
