# Vendor Market Rate API — PM quote form (updated)

**Base URL (prod):** `https://tatvaops-quotesense.onrender.com`  
**Local:** `http://127.0.0.1:8001`

## Naming (PM contract)

| Param / field | Meaning | Example |
|---------------|---------|---------|
| `service_id` | Main service ObjectId (Interiors, Painting, …) | `6926b1978ba6a3cfc5a191ce` |
| `category_id` | Quotation-type ObjectId (Essential / Mid / Luxury) | `6a633163fb8e13eb4eeaa2e4` |
| `quote_type_id` | Legacy alias for `category_id` | same as above |
| `service_type` | Optional string instead of ObjectId | `ESSENTIAL` |

Item rows:

| Field | Meaning |
|-------|---------|
| `sub_service_id` | Tatva sub-service ObjectId (null if not in catalog yet) |
| `sub_service_label` | Display / match name |
| `pricing_id` | Tatva pricing-method ObjectId (null if not in catalog yet) |
| `pricing_method_label` | Display / match name |

---

## Bulk load (preferred when vendor picks service + quote type)

`GET /api/market-rate/by-category`

```http
GET /api/market-rate/by-category?service_id=6926b1978ba6a3cfc5a191ce&category_id=6a633163fb8e13eb4eeaa2e4
```

Auth: none.

### Example response

```json
{
  "service_category": "Interiors",
  "service_type": "ESSENTIAL",
  "service_id": "6926b1978ba6a3cfc5a191ce",
  "category_id": "6a633163fb8e13eb4eeaa2e4",
  "service_code": "INTERIORS",
  "count": 20,
  "items": [
    {
      "sub_service_id": "69957e7625ccc8cecd1ddc14",
      "sub_service_label": "2D Floor Planning",
      "pricing_id": "69940c25c0baa8c50cb4d73f",
      "pricing_method_label": "Per Unit",
      "market_rate": 999.0,
      "weight": 2,
      "suggestion": "Recommended base rate: ₹999.00/Per Unit. Suggestion appears only when the entered rate is above this base."
    },
    {
      "sub_service_id": null,
      "sub_service_label": "Wardrobe",
      "pricing_id": null,
      "pricing_method_label": "Area (sqft)",
      "market_rate": 1400.0,
      "weight": 0,
      "suggestion": "Recommended base rate: ₹1,400.00/Area (sqft). Suggestion appears only when the entered rate is above this base."
    }
  ]
}
```

Match locally with `sub_service_id` + `pricing_id` when present; otherwise `sub_service_label` + `pricing_method_label`.

### Filling ObjectIds (live Tatva catalogs — preferred)

QuoteSense resolves `sub_service_id` / `pricing_id` from Tatva admin APIs
(cached ~1h), so new items added tomorrow appear after the next refresh
**without** editing static JSON or redeploying.

Set on Render / local `.env`:

```bash
TATVA_API_BASE=https://devopsapi.withtatva.ai
TATVA_API_KEY=<PM service key>
```

APIs used automatically on `/by-category`:

```text
GET {TATVA_API_BASE}/admin/api/admin/quote-subservices?serviceId={service_id}
GET {TATVA_API_BASE}/admin/api/admin/pricing-methods
x-api-key: {TATVA_API_KEY}
```

Force refresh + persist to disk:

```bash
curl -X POST "https://tatvaops-quotesense.onrender.com/api/market-rate/sync-catalog?live=1&service_id=6926b1978ba6a3cfc5a191ce"
```

Static JSON (`backend/data/tatva_*_ids.json`) remains a **fallback** when the
API key is missing or Tatva is down.

**Aliases:** seed labels like `Wardrobe` / `Area (sqft)` map to Tatva names
`Wardrobes` / `Area (in sqft)` when the live catalog uses those spellings.

**Still null?** Only when Tatva has no matching catalog row for that seed label
(e.g. a spreadsheet item not in PM’s quote-subservices list).

### Filling ObjectIds (manual / quotes harvest)

**Preferred when quotes API returns empty — ask PM for a label→id map, then:**

```bash
curl -X POST http://127.0.0.1:8001/api/market-rate/sync-catalog \
  -H "Content-Type: application/json" \
  -d '{
    "sub_services": {
      "Wardrobe": "REPLACE_WITH_REAL_OID",
      "Base Unit": "REPLACE_WITH_REAL_OID",
      "TV Units": "REPLACE_WITH_REAL_OID"
    },
    "pricing_methods": {
      "Area (sqft)": "REPLACE_WITH_REAL_OID",
      "Per Unit": "69940c25c0baa8c50cb4d73f"
    }
  }'
```

Interiors labels we need ids for (seeded rates):  
Base Unit, Middle unit, Wall Unit, Loft, TV Units, Crockery Units, Wardrobe, Dressing Unit, Vanity Units, Study Table, Wall Panels, Bottle Pullouts, Tandem channels, Rolling Shutter, PVC Tray and Thali, Shoe Rack, Pooja Unit, False Ceiling, Wallpaper  
Pricing methods: `Area (sqft)`, `Area (sqft)/Per Unit`, `Per Unit`

**Or harvest from quotes** (only works when Tatva returns non-empty `data`):

```bash
# POST Tatva project-quotes JSON
curl -X POST http://127.0.0.1:8001/api/market-rate/sync-catalog \
  -H "Content-Type: application/json" \
  -d @project_quotes.json

# Or fetch by project
curl -X POST "http://127.0.0.1:8001/api/market-rate/sync-catalog?project_id=YOUR_PROJECT_MONGO_ID" \
  -H "Authorization: Bearer YOUR_JWT"
```

Opening a project / compare sync also auto-harvests when quote payloads include workItems.

On rate blur: if `entered_rate > market_rate` (recommended base from the sheet), show the above-base banner (or call `/suggest`). At or below base → no suggestion.

---

## Single-item suggest (optional)

`GET /api/market-rate/suggest`

```
?service_id=6926b1978ba6a3cfc5a191ce
&category_id=6a633163fb8e13eb4eeaa2e4
&sub_service=Wardrobe
&pricing_method=Area%20(sqft)
&entered_rate=1401
```

| Condition | Response | UI |
|-----------|----------|-----|
| Rate **>** recommended base (`market_rate`) — even ₹1 above | `"recommend": true` + `message` | Show banner |
| Rate **≤** recommended base | `"recommend": false` | Hide banner |

No ±% interval / band — compare to the single spreadsheet base rate only.

### Freezing base rates (ops)

Set `MARKET_RATE_UPDATES_ENABLED=false` on the backend (Render + local `.env`) so
compare/finalize **do not** rewrite `market_moving_averages` / session logs.
Recommendations still read the seeded bases. Set back to `true` when you want
finalized/compare rates to update the moving average again.

Prefer `sub_service_id` + `pricing_id` when the form has ObjectIds; labels still work.

---

## Quote type ObjectIds

| Tier | ObjectId |
|------|----------|
| Essential | `6a633163fb8e13eb4eeaa2e4` |
| Mid-segment | `6a63316dfb8e13eb4eeaa2e9` |
| Luxury | `6a633174fb8e13eb4eeaa2ee` |

---

## JS example

```javascript
async function loadInteriorsRates(quoteTypeId) {
  const url = new URL("https://tatvaops-quotesense.onrender.com/api/market-rate/by-category");
  url.searchParams.set("service_id", "6926b1978ba6a3cfc5a191ce");
  url.searchParams.set("category_id", quoteTypeId); // Essential / Mid / Luxury ObjectId
  const res = await fetch(url);
  return res.json(); // cache .items
}

function findRate(items, subServiceId, pricingId, subLabel, pricingLabel) {
  return items.find(
    (i) =>
      (subServiceId && i.sub_service_id === subServiceId) ||
      (i.sub_service_label === subLabel && i.pricing_method_label === pricingLabel)
  );
}
```
