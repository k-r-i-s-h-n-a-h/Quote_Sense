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
  "message": "Your rate ₹122,222.00/Per Visit is above market (~₹8,500.00, 12 quotes). Consider adjusting to stay competitive."
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

## Alternate endpoints

| Endpoint | Use |
|----------|-----|
| `GET /api/market-rate/suggest?...` | Same as POST; query params instead of body |
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
