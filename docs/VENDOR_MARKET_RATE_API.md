# Vendor Market Rate API — withtatva.ai Quote Form Integration

QuoteSense exposes market-rate guidance for the **vendor quote form** on `withtatva.ai/quote` (Work Summary → Work Item).

**Base URL (staging):** your deployed QuoteSense backend, e.g. `https://quotesense-api.example.com`  
**Local dev:** `http://127.0.0.1:8001`

CORS is open (`*`) — callable directly from `withtatva.ai`.

---

## Form field mapping

| Tatva PM form field | API parameter | Example |
|---------------------|---------------|---------|
| Main Service dropdown | `service_category` | `Residential Construction` |
| Item / SKU / Feature dropdown | `sub_service` | `Site Clearing & Excavation` |
| Pricing Method dropdown | `pricing_method` | `Per Visit` |
| Work item type (if available) | `service_type` | `ESSENTIAL` (default) |
| **Rate (₹)** input | `entered_rate` | `122222` |

**Important:** Send the **Rate (₹)** value, not Amount or Total. Amount includes quantity × rate; market data is per-unit rate for the pricing method.

---

## When to call the API

| User action | Call | `entered_rate` |
|-------------|------|----------------|
| Selects **Item / SKU** | suggest | omit |
| Changes **Pricing Method** | suggest | omit |
| Types / blurs **Rate (₹)** | suggest | include |

**Do not show anything** if response has `"recommend": false`.

---

## Recommended endpoint (single integration point)

### `POST /api/market-rate/suggest`

**Trigger 1 — Pricing Method selected (show market hint only):**

```http
POST /api/market-rate/suggest
Content-Type: application/json

{
  "service_type": "ESSENTIAL",
  "service_category": "Residential Construction",
  "sub_service": "Site Clearing & Excavation",
  "pricing_method": "Per Visit"
}
```

**Trigger 2 — Rate field changed (show market + low/fair/high verdict):**

```http
POST /api/market-rate/suggest
Content-Type: application/json

{
  "service_type": "ESSENTIAL",
  "service_category": "Residential Construction",
  "sub_service": "Site Clearing & Excavation",
  "pricing_method": "Per Visit",
  "entered_rate": 122222
}
```

### Response — market data found

```json
{
  "recommend": true,
  "service_type": "ESSENTIAL",
  "service_category": "Residential Construction",
  "sub_service": "Site Clearing & Excavation",
  "pricing_method": "Per Visit",
  "market_rate": 8500,
  "weight": 12,
  "band_low": 7225,
  "band_high": 9775,
  "entered_rate": 122222,
  "verdict": "high",
  "suggestion": "Current rates exceed the market average of ₹8,500.00. Kindly review your pricing to improve closure rates.",
  "message": "Current rates exceed the market average of ₹8,500.00/Per Visit (12 quotes). Kindly review your pricing to improve closure rates."
}
```

### Response — no market data (hide panel)

```json
{
  "recommend": false,
  "message": "No market data for this item and pricing method yet."
}
```

---

## Verdict values (UI styling)

| `verdict` | Meaning | Suggested UI |
|-----------|---------|--------------|
| `low` | Below ~85% of market | Amber — underpricing risk |
| `fair` | Within market band | Green — OK |
| `high` | Above ~115% of market | Red — overcharging risk |

When `verdict` is `"high"`, `suggestion` reads:

> Current rates exceed the market average of ₹{market_rate}. Kindly review your pricing to improve closure rates.

This applies for **all three quote tiers** (`ESSENTIAL`, `MID_SEGMENT`, `LUXURY`) — the amount shown is that tier's own market average, not a shared one.

When `entered_rate` is omitted, `verdict` is not returned — show market hint only:

> Market rate: ~₹8,500/Per Visit (12 quotes)

---

## JavaScript example (withtatva.ai quote form)

```javascript
const QUOTESENSE_API = "https://YOUR-QUOTESENSE-BACKEND";

async function fetchMarketSuggestion(workItem) {
  const body = {
    service_type: workItem.serviceType || "ESSENTIAL",
    service_category: workItem.mainService,       // Main Service dropdown
    sub_service: workItem.subService,             // Item / SKU dropdown
    pricing_method: workItem.pricingMethod,       // Pricing Method dropdown
  };
  const rate = parseFloat(workItem.rate);
  if (Number.isFinite(rate) && rate > 0) {
    body.entered_rate = rate;
  }

  const res = await fetch(`${QUOTESENSE_API}/api/market-rate/suggest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// On Pricing Method change:
pricingMethodSelect.addEventListener("change", async () => {
  const data = await fetchMarketSuggestion(getWorkItemFields());
  renderMarketPanel(data); // hide if !data.recommend
});

// On Rate blur:
rateInput.addEventListener("blur", async () => {
  const data = await fetchMarketSuggestion(getWorkItemFields());
  renderMarketPanel(data);
});
```

---

## Bulk load by service category (recommended for withtatva.ai)

Call **once** when the user selects **Main Service**. Cache the response and match locally on Item + Pricing Method — no API call on every field change.

### `GET /api/market-rate/by-category`

**Preferred — by Tatva PM service ObjectId:**

```http
GET /api/market-rate/by-category?service_id=6926b1978ba6a3cfc5a191ce
```

**Alternate — by category name:**

```http
GET /api/market-rate/by-category?service_category=Residential%20Construction
```

Provide **either** `service_id` **or** `service_category` (not both required).

Optional: `service_type=ESSENTIAL` (default)

`service_id` is resolved via Tatva services API (`/admin/api/services`) to the category name stored in market data. If the API is unreachable (e.g. on Render), the backend falls back to `backend/data/tatva_service_ids.json` — all 11 Tatva main services are pre-mapped.

### Quote tiers — Essential / Mid-segment / Luxury

`service_type` selects which quote tier's market data to return. Market rates are tracked **separately per tier**, so call this endpoint once per tier the vendor form supports:

```http
GET /api/market-rate/by-category?service_id=6926b1978ba6a3cfc5a191ce&service_type=ESSENTIAL
GET /api/market-rate/by-category?service_id=6926b1978ba6a3cfc5a191ce&service_type=MID_SEGMENT
GET /api/market-rate/by-category?service_id=6926b1978ba6a3cfc5a191ce&service_type=LUXURY
```

| `service_type` value | Tier |
|-----------------------|------|
| `ESSENTIAL` (default) | Essential |
| `MID_SEGMENT` | Mid-segment / Mid-level |
| `LUXURY` | Luxury |

Aliases like `midlevel`, `mid_level`, `mid-segment`, `premium`, `standard`, `budget` are also normalized server-side, but sending the canonical values above is recommended.

Cache each tier's response separately (e.g. keyed by `service_id + service_type`) and re-match locally when the vendor switches the quote type — no need to call the API again just because the tier changed if you've already cached all three.

If a tier has no submitted quotes yet for a bundle, that item is simply omitted from `items` (or `recommend: false` for the single-row endpoints) — it isn't an error, it just means there isn't enough real market data for that tier yet.

**HTTP caching**

| Request | Headers | Effect |
|---------|---------|--------|
| Bulk (`service_id` only) | `Cache-Control: private, max-age=7200` + `CDN-Cache-Control: no-store` | PM app/browser may cache 2h; **Cloudflare edge stays `DYNAMIC`** (no CDN cache) |
| With `entered_rate` | `Cache-Control: private, max-age=300` | 5 min private cache per user/rate |
| Error / missing params | `Cache-Control: no-store` | Do not cache |

`cf-cache-status` is set by **Cloudflare**, not this API. We use `private` + `CDN-Cache-Control: no-store` so edge caches do not serve stale market data (`HIT`). Yash's app should cache the bulk response locally after the first call.

Verify headers: `curl -I` (HEAD) or `curl -s -D - -o /dev/null "<url>"`

**Example response (by service_id):**

```json
{
  "service_id": "6926b1978ba6a3cfc5a191ce",
  "service_code": "INTERIORS",
  "service_category": "Interiors",
  "service_type": "ESSENTIAL",
  "count": 109,
  "items": [
    {
      "sub_service": "Wardrobes",
      "pricing_method": "Area (in sqft)",
      "market_rate": 1429.11,
      "weight": 506,
      "band_low": 1214.74,
      "band_high": 1643.48,
      "suggestion": "Fair market range: ₹1,214.74 – ₹1,643.48/Area (in sqft). Enter your rate to see if it's low, fair, or high."
    }
  ]
}
```

**With rate entered** — add optional query params for verdict on the active row:

```http
GET /api/market-rate/by-category?service_id=6926b1978ba6a3cfc5a191ce&sub_service=Wardrobes&pricing_method=Area%20(in%20sqft)&entered_rate=2000
```

Returns `selected_recommendation` for the active row only (items stay flat):

```json
{
  "selected_recommendation": {
    "sub_service": "Wardrobes",
    "pricing_method": "Area (in sqft)",
    "market_rate": 1429.11,
    "weight": 506,
    "band_low": 1214.74,
    "band_high": 1643.48,
    "entered_rate": 2000,
    "verdict": "high",
    "verdict_label": "Above Market",
    "suggestion": "Current rates exceed the market average of ₹1,429.11. Kindly review your pricing to improve closure rates."
  }
}
```

**Client-side match** (no further API calls):

```javascript
const match = items.find(
  (r) => r.sub_service === subService && r.pricing_method === pricingMethod
);
if (!match) hidePanel();

const verdict =
  enteredRate < match.market_rate * 0.85 ? "low"
  : enteredRate > match.market_rate * 1.15 ? "high"
  : "fair";
```

---

## Alternate endpoints

| Endpoint | Use |
|----------|-----|
| `GET /api/market-rate/by-category?...` | **Bulk** — all bundles for one Main Service |
| `GET /api/market-rate/suggest?...` | Single-row lookup; query params instead of POST body |
| `GET /api/market-rate/lookup?...` | Lookup only (no `entered_rate`) |
| `POST /api/market-rate/recommend` | Same as suggest POST (legacy alias) |

---

## Match rules

Recommendations only appear when **all four** match a row in `market_moving_averages`:

```
service_type + service_category + sub_service + pricing_method
```

Example bundle: `ESSENTIAL | Interiors | Wardrobes | Area (in sqft)`

No partial/fallback matching — if no row exists, `recommend: false`.

---

## Health check

```http
GET /api/health
```

---

## Questions

Contact QuoteSense / comparator team for staging backend URL and Supabase environment alignment.
