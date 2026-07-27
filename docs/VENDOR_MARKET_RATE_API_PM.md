# Vendor Market Rate API — PM quote form (updated)

**Base URL (prod):** `https://tatvaops-quotesense.onrender.com`  
**Local:** `http://127.0.0.1:8001`

## Preferred call — rate blur / change

`POST /api/market-rate/suggest`

```http
POST /api/market-rate/suggest
Content-Type: application/json

{
  "quote_type_id": "<Tatva quotation-type ObjectId>",
  "category_id": "<Tatva main-service ObjectId>",
  "sub_service": "Wardrobe",
  "pricing_method": "Area (sqft)",
  "entered_rate": 1401
}
```

You may send `service_type` instead of (or as well as) `quote_type_id`:

| `service_type` | Meaning |
|----------------|---------|
| `ESSENTIAL` | Essential / affordable |
| `MID_SEGMENT` | Mid-segment |
| `LUXURY` | Luxury |

`quote_type_id` is mapped on the server from env (`TATVA_QUOTE_TYPE_*_ID`) — do not hardcode mapping on the client beyond sending the ObjectId from your quotation-type dropdown.

`category_id` = Main Service ObjectId (e.g. Interiors). `service_id` is accepted as an alias.

---

## When to show UI

| Condition | Response | UI |
|-----------|----------|-----|
| Rate **>** base (even ₹1) | `"recommend": true` | Show **only** `message` |
| Rate **≤** base | `"recommend": false` | **Hide** banner (intended) |
| No `entered_rate` | `"recommend": false` | Hide banner |
| Missing quotation type | `"recommend": false` | Hide / ask user to pick type |

---

## Response — above base (show banner)

```json
{
  "recommend": true,
  "service_type": "ESSENTIAL",
  "service_category": "Interiors",
  "sub_service": "Wardrobe",
  "pricing_method": "Area (sqft)",
  "market_rate": 1400,
  "entered_rate": 1401,
  "verdict": "high",
  "message": "Current rates exceed the market average of ₹1,400.00. Kindly review your pricing to improve closure rates."
}
```

Use **`message` only** for the banner. There is no separate `suggestion` for this flow.

---

## Response — at or below base (silent)

```json
{
  "recommend": false,
  "service_type": "ESSENTIAL",
  "service_category": "Interiors",
  "sub_service": "Wardrobe",
  "pricing_method": "Area (sqft)",
  "market_rate": 1400,
  "entered_rate": 1400
}
```

---

## JS example

```javascript
async function checkMarketRate({ quoteTypeId, categoryId, subService, pricingMethod, rate }) {
  const res = await fetch("https://tatvaops-quotesense.onrender.com/api/market-rate/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quote_type_id: quoteTypeId,   // from quotation-type dropdown ObjectId
      category_id: categoryId,       // main service ObjectId
      sub_service: subService,
      pricing_method: pricingMethod,
      entered_rate: Number(rate),
    }),
  });
  const data = await res.json();
  if (data.recommend === true && data.message) {
    showBanner(data.message); // red / warning
  } else {
    hideBanner();
  }
}
```

Also available: `GET /api/market-rate/suggest` with the same query params, and `POST /api/market-rate/recommend` (same body).
