# QuoteSense — Full Knowledge Transfer (KT) for Testing

**Audience:** QA / testing team  
**Product:** TatvaOps QuoteSense (quote compare + market-rate guidance)  
**Last updated:** 2026-08-14 (includes OTP env pairing + progress proxy fixes on `test`)

This document is the single handoff for **how the system is connected**, **what to test**, **where to look when something fails**, and **which env must talk to which env**.

---

## 1. What QuoteSense is (one paragraph)

QuoteSense helps procurement teams compare **2–3 vendor quotes of the same tier** (Essential / Mid / Luxury) for a Tatva project, show a cost matrix + AI recommendation, and expose **market base rates** to Tatva vendor quote forms. Auth is WhatsApp OTP / PM SSO via Tatva. Permanent market rates live in Supabase; compare sessions are temporary.

---

## 2. Environment map (memorize this)

| Role | Dev | Test (QA) | Prod |
|------|-----|-----------|------|
| **QuoteSense UI** | `https://devquotesense.withtatva.ai` | `https://testquotesense.withtatva.ai` | `https://quotesense.withtatva.ai` (confirm live domain) |
| **QuoteSense API (Render)** | (often shared / devops backend — confirm Render service) | `https://tatvaops-quotesense-qa.onrender.com` | `https://tatvaops-quotesense-prod.onrender.com` or `https://tatvaops-quotesense.onrender.com` |
| **Tatva Ops API** | `https://devopsapi.withtatva.ai` | `https://testopsapi.withtatva.ai` | `https://opsapi.withtatva.ai` (confirm) |
| **Tatva Admin (OTP records)** | `https://admin.devops.withtatva.ai/otp-records` | `https://admin.testops.withtatva.ai/otp-records` | `https://admin.ops.withtatva.ai/otp-records` (confirm) |
| **Git branch → frontend deploy** | `dev` → Vercel dev | `test` → Vercel QA | `main` → Vercel prod |
| **Supabase** | Dedicated or shared — **never assume same as prod** | Staging project | Prod project |

### Golden rule

> **Never cross-wire environments.**  
> Test QuoteSense UI must use **testopsapi** + **Render QA** + **staging Supabase**.  
> Dev QuoteSense UI must use **devopsapi** + matching backend + matching DB.  
> If OTP lands on phone but does **not** show in the matching admin, the UI is almost always calling the **wrong Tatva API base**.

### Correct pairing diagram

```
DEV
  Browser → devquotesense (Vercel)
              ├─ /api/auth/*        → devopsapi.withtatva.ai  → OTP in admin.devops
              ├─ /api/projects/*    → devopsapi (vendor/projects)
              └─ /api/compare/*, /api/progress/* → BACKEND_URL (Render) → Supabase (dev/staging)

TEST / QA
  Browser → testquotesense (Vercel)
              ├─ /api/auth/*        → testopsapi.withtatva.ai → OTP in admin.testops
              ├─ /api/projects/*    → testopsapi
              └─ /api/compare/*, /api/progress/* → tatvaops-quotesense-qa.onrender.com → Supabase staging

PROD
  Browser → quotesense (Vercel)
              ├─ /api/auth/*        → opsapi (prod Tatva)
              └─ compare/progress   → Render prod → Supabase prod
```

---

## 3. System architecture (all connections)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser                                                                  │
│  QuoteSense Next.js (Vercel)                                              │
│  Routes: /login  /  /project/:code  /compare                              │
└───────────────┬───────────────────────────────┬───────────────────────────┘
                │ Same-origin BFF               │ Same-origin BFF
                ▼                               ▼
     /api/auth/send-otp                  /api/compare/sync-mongodb
     /api/auth/verify-otp                /api/progress/[sessionId]  ← proxy
     /api/auth/profile                   /api/projects/*
     /api/projects/[id]/quotes
                │                               │
                ▼                               ▼
     Tatva Users + Vendor API            QuoteSense FastAPI (Render)
     (OTP, JWT, projects, quotes)        main.py
                                         ├─ JOBS (in-memory progress)
                                         ├─ Gemini extract / recommend / chat
                                         └─ market_rate + tatva_catalog
                                                │
                                                ▼
                                         Supabase Postgres
                                         ├─ market_moving_averages (permanent)
                                         ├─ market_moving_avg_sessions (dedup)
                                         └─ quotes / quote_items (staging)
```

### Important implementation detail (progress)

- Compare **start** goes through Next: `POST /api/compare/sync-mongodb` → Render.  
- Compare **poll** must go through Next: `GET /api/progress/{sessionId}` → Render.  
- If the browser polls Render URL incorrectly (or polls the Vercel host as if it were FastAPI), you get an **HTML 404** and the UI sticks on “Building analysis…”.  
- Fixed on branch `test` (Aug 2026): same-origin progress proxy.

---

## 4. Product rules testers must know

1. **Compare count:** only **2 or 3** quotes at a time (same tier).  
2. **Compare does NOT update market averages.** Display/compare only.  
3. **Market averages update only when a quote is finalized** (`isFinalizeQuote` / similar flags).  
4. **`MARKET_RATE_UPDATES_ENABLED=false`** freezes all MA writes (compare still works).  
5. Service display names were renamed (e.g. **Interiors → Residential Interiors**). APIs and seeds use new names; ObjectIds for main services largely stayed the same.  
6. Progress jobs live in **process memory** on Render (`JOBS`). Cold start / multi-worker can make a session vanish (“No job found”). Retry compare if that happens after idle.

See also: [`COMPARISON_DATA_LIFECYCLE.md`](./COMPARISON_DATA_LIFECYCLE.md).

---

## 5. Auth / OTP — full connection & test script

### Flow

1. User opens QuoteSense `/login`, enters phone.  
2. Browser → `POST /api/auth/send-otp` (Next BFF on Vercel).  
3. Next → `{TATVA_API_BASE}/users/api/auth/send-otp` with JSON `{ phoneNumber }`.  
4. Tatva sends WhatsApp OTP and stores a row for admin OTP Records.  
5. User enters OTP → `POST /api/auth/verify-otp` → tokens in `localStorage`.  
6. Protected pages (`/`, `/project/*`, `/compare`) require auth.

### What “correct” looks like

| Action | Dev expectation | Test expectation |
|--------|-----------------|------------------|
| Login on `devquotesense` | OTP in `admin.devops…/otp-records` | — |
| Login on `testquotesense` | — | OTP in `admin.testops…/otp-records` |
| OTP on phone | Always (if WhatsApp gateway works) | Always |
| Admin empty but phone gets OTP | Wrong Tatva base (UI hitting other env) | Same |

### QA steps — Auth

| # | Step | Pass criteria |
|---|------|----------------|
| A1 | Open correct UI for env | Login page loads |
| A2 | Request OTP | Button succeeds; user gets WhatsApp message |
| A3 | Open matching admin OTP Records + Refresh | Same phone + code appear within ~1 min |
| A4 | Verify OTP | Lands on dashboard / `returnTo` |
| A5 | Logout / protected route | Redirects to `/login?returnTo=…` |
| A6 | (Optional) PM SSO with `jwt_auth` / `token` | Session bootstraps without OTP |

### Failure signatures

| Symptom | Likely cause |
|---------|--------------|
| OTP on phone, **wrong** admin shows it | `TATVA_API_BASE` points at other Tatva env |
| OTP on phone, **no** admin shows it | Wrong admin opened, or Tatva admin API/DB issue on that env |
| “Auth service unreachable” | Bad/missing `TATVA_API_BASE` on Vercel |
| Works on phone, verify fails | Expired OTP, wrong env token issuer |

---

## 6. Project hub → Compare — full connection & test script

### Flow

```
Login
 → /  (ProjectDashboard — list from Tatva via BFF)
 → /project/{publicCode}  (ProjectHub — select 2–3 same-tier quotes)
 → /compare?projectId=…&quotes=id1,id2
 → resolveQuotesForCompare (cache / BFF)
 → POST /api/compare/sync-mongodb?session_id=session_…
 → poll GET /api/progress/session_…  (JSON, not HTML)
 → matrix + chart + insights + recommendation + chat + PDF
```

### Network tab — what you must see on Compare

| Request | Host | Expected status | Body type |
|---------|------|-----------------|-----------|
| `POST /api/compare/sync-mongodb?session_id=…` | QuoteSense UI host (Vercel) | 200 | JSON with `session_id` |
| `GET /api/progress/session_…` | **Same UI host** (proxied) | 200 | **JSON** (`status`, `stage`, `processed`, …) |
| Progress polling repeatedly | Same | 200 | JSON until `status: "done"` |

**Fail if:** progress returns HTML with `<title>404` / “This page could not be found” → proxy/env broken.

### QA steps — Compare

| # | Step | Pass criteria |
|---|------|----------------|
| C1 | Open a project with ≥2 quotes same tier | Quotes list visible |
| C2 | Select 2 quotes → Compare | Navigates to `/compare?…` |
| C3 | Loading panel | Progress moves (processed count / stages) |
| C4 | Network: progress | JSON 200, not HTML 404 |
| C5 | Result | Matrix + vendor totals + recommendation appear |
| C6 | Select 1 quote only | Cannot start / blocked by 2–3 rule |
| C7 | Select 4 quotes | Clamp/block at max 3 |
| C8 | Different tiers mixed | Product should discourage / block same-tier rule (confirm current UI behavior) |
| C9 | Refresh mid-job with `session_id` in URL | Either resumes or cleanly recovers (stale session messaging) |
| C10 | Chat after compare | Answers about the session |
| C11 | Download PDF | PDF downloads with matrix |

### Failure signatures

| Symptom | Likely cause |
|---------|--------------|
| Stuck “Building analysis…”, progress HTML 404 | Progress hit Vercel without proxy / bad deploy |
| Progress JSON `status: "unknown"` / “No job found” | Render restarted / multi-worker / stale `session_id` — retry compare |
| Start fails 502 | `BACKEND_URL` wrong on Vercel or Render down |
| Empty projects list | Tatva API key/base mismatch or auth token for wrong env |

---

## 7. Market-rate API (vendor form / Postman) — connections

### Purpose

Tatva PM vendor quote form calls QuoteSense to show **recommended base rates** per sub-service + pricing method for a main service + quotation type (Essential/Mid/Luxury).

### Primary endpoint

```http
GET {RENDER_BASE}/api/market-rate/by-category
  ?service_id={mainServiceObjectId}
  &category_id={quoteTypeObjectId}
```

| Param | Meaning |
|-------|---------|
| `service_id` | Main service (e.g. Residential Interiors / INTERIORS) |
| `category_id` | Quotation type ObjectId (Essential / Mid / Luxury) — **differs per Tatva env** |
| `service_type` | Optional string `ESSENTIAL` / `MID_SEGMENT` / `LUXURY` |

### How IDs are filled

1. Rates come from Supabase `market_moving_averages` (names + rates).  
2. `sub_service_id` / `pricing_id` are resolved via Tatva live catalog:

```text
GET {TATVA_API_BASE}/admin/api/admin/pricing-methods
GET {TATVA_API_BASE}/admin/api/admin/quote-subservices?serviceId=…
Header: x-api-key: {TATVA_API_KEY}
```

3. Static JSON under `backend/data/tatva_*_ids.json` is **fallback only**.

### Expected healthy response

- `count` > 0 (e.g. ~81 for full Interiors seed × one tier)  
- `service_category`: `Residential Interiors` (new name)  
- Most items have non-null `sub_service_id` and `pricing_id` when Tatva key/base are correct  
- `market_rate` numeric, `suggestion` string  

### Empty `items` / `count: 0`

Means Supabase for **that Render service** has no rows for:

`service_category = 'Residential Interiors' AND service_type = 'ESSENTIAL'` (or Mid/Luxury).

Common causes:

- Truncated MA table and only reseeded the **other** Supabase project  
- Still using old name `Interiors` in DB while API looks for `Residential Interiors`  
- Wrong `SUPABASE_URL` on Render  

### Null ObjectIds but rates present

Rates OK; Tatva catalog lookup failing (wrong/missing `TATVA_API_KEY` or `TATVA_API_BASE` on Render).

### Postman / curl smoke

```bash
# QA Render
curl -sS "https://tatvaops-quotesense-qa.onrender.com/api/health" | jq .

curl -sS "https://tatvaops-quotesense-qa.onrender.com/api/market-rate/by-category?service_id=6926b1978ba6a3cfc5a191ce&category_id=<TEST_ESSENTIAL_QUOTE_TYPE_ID>" | jq '{count, service_category, service_type, first: .items[0]}'
```

Use **test** quote-type IDs from testops (not devops IDs). Confirm IDs with Tatva / env vars:

- `TATVA_QUOTE_TYPE_ESSENTIAL_ID`  
- `TATVA_QUOTE_TYPE_MID_SEGMENT_ID`  
- `TATVA_QUOTE_TYPE_LUXURY_ID`  

### Catalog sync (ops)

```bash
curl -X POST "https://tatvaops-quotesense-qa.onrender.com/api/market-rate/sync-catalog?live=1&service_id=6926b1978ba6a3cfc5a191ce"
```

Expect `has_catalog_auth: true` and registered counts > 0.

Full API contract: [`VENDOR_MARKET_RATE_API_PM.md`](./VENDOR_MARKET_RATE_API_PM.md).

---

## 8. Database (Supabase) — what testers / ops touch

| Table / view | Purpose | Notes for QA |
|--------------|---------|--------------|
| `market_moving_averages` | Permanent base rates | Source of `/by-category` |
| `market_base_rates_by_tier` | View pivoting Essential/Mid/Luxury | Names + rates; often **no ObjectId columns** |
| `market_moving_avg_sessions` | Dedup for finalize / sessions | Cleared when reseeding |
| `quotes` / `quote_items` | Staging for compare | Not the permanent market table |

### After a reseed (healthy)

```sql
SELECT service_type, count(*)
FROM market_moving_averages
GROUP BY 1 ORDER BY 1;
-- expect ~81 each for ESSENTIAL, MID_SEGMENT, LUXURY if full seed applied
```

Seed SQL (ops): `backend/data/seed_market_moving_averages_full.sql`  
**Warning:** seed starts with `DELETE FROM market_moving_averages` — run only on the intended project.

### Truncate impact

Truncating MA **only** clears market rates (and optionally sessions). It does **not** wipe all of Supabase. It **will** make `/by-category` return `count: 0` until reseeded on **that** project.

---

## 9. Frontend BFF routes (Vercel) — quick map

| Next route | Forwards to |
|------------|-------------|
| `POST /api/auth/send-otp` | `{TATVA_API_BASE}/users/api/auth/send-otp` |
| `POST /api/auth/verify-otp` | Tatva users verify |
| `GET /api/auth/profile` | Tatva profile |
| `GET /api/projects` | Tatva vendor/projects |
| `GET /api/projects/[id]/quotes` | Tatva quotes (+ optional MA apply) |
| `POST /api/compare/sync-mongodb` | `{BACKEND_URL}/api/sync-mongodb-quotes` |
| `GET /api/progress/[sessionId]` | `{BACKEND_URL}/api/progress/{id}` |

Env on Vercel (test):

- `TATVA_API_BASE=https://testopsapi.withtatva.ai`  
- `BACKEND_URL=https://tatvaops-quotesense-qa.onrender.com`  
- `NEXT_PUBLIC_BACKEND_URL=` same Render QA URL (legacy client paths)

Env on Render QA:

- `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` → **staging**  
- `TATVA_API_BASE=https://testopsapi.withtatva.ai`  
- `TATVA_API_KEY` = testops `x-api-key`  
- `TATVA_QUOTE_TYPE_*_ID` = **testops** quote-type ObjectIds  
- `GEMINI_API_KEY`  
- `MARKET_RATE_UPDATES_ENABLED` as product requires  

---

## 10. Deploy & branches (what shipping means)

| Branch | Frontend | Typical backend |
|--------|----------|-----------------|
| `dev` | Vercel → `devquotesense` | Dev/devops-aligned Render |
| `test` | Vercel → `testquotesense` (workflow syncs testops + QA Render) | `tatvaops-quotesense-qa` |
| `main` | Vercel prod | Render prod |

Workflows: `.github/workflows/deploy_{dev,test,prod}.yml`.

After a `test` push: wait for GitHub Action **Deploy to Vercel (test)** green before retesting UI.

---

## 11. End-to-end test script (run in order)

Use this as the official QA script per environment (swap hosts from §2).

### Preflight

1. Confirm you are on the correct QuoteSense URL for the env.  
2. Confirm admin OTP URL matches that env.  
3. `GET {RENDER}/api/health` → healthy.  
4. `GET {RENDER}/api/market-rate/by-category?service_id=…&category_id=…` → `count > 0`.  

### Script

| Phase | ID | Action | Pass |
|-------|----|--------|------|
| Auth | A1–A6 | §5 | OTP in **matching** admin; login works |
| Hub | H1 | Dashboard lists projects | Non-empty (or known empty account) |
| Hub | H2 | Open project | Quotes with tiers visible |
| Compare | C1–C11 | §6 | Matrix + JSON progress |
| Market | M1 | Postman by-category Essential | count > 0, rates present |
| Market | M2 | Mid + Luxury | Same |
| Market | M3 | Spot-check ObjectIds | Mostly non-null when Tatva key set |
| Market | M4 | Suggest with entered rate above base | Banner/suggestion text |
| Finalize | F1 | Finalize a quote in Tatva (if in scope) | MA weight/rate can change only if updates enabled |
| Negative | N1 | Progress Network shows HTML 404 | **Fail** — report as proxy/env bug |
| Negative | N2 | by-category count 0 | **Fail** — wrong/empty Supabase for that Render |

---

## 12. Known pitfalls (from recent incidents)

| Issue | Root cause | Fix / check |
|-------|------------|-------------|
| Test OTP not in testops admin | Vercel test `TATVA_API_BASE` pointed at devops | Set `testopsapi`; deploy_test.yml updated |
| Compare stuck; progress HTML 404 | Browser polled Vercel `/api/progress` without proxy | Same-origin progress proxy on `test` |
| Prod/QA by-category `count: 0` | MA truncated/reseeded on **other** Supabase | Reseed the Supabase bound to that Render `SUPABASE_URL` |
| Null `pricing_id` / `sub_service_id` | Live catalog not loading | Render `TATVA_API_BASE` + `TATVA_API_KEY` for that Tatva env |
| “Session not found” JSON | In-memory `JOBS` lost after restart | Retry compare; keep Render warm |
| Old names in UI/API | Catalog rename incomplete | Expect `Residential Interiors`, `Area – Direct Entry (sq ft)`, `Per Unit / Each` |

---

## 13. Quick diagnostic cheatsheet

```bash
# 1) Backend alive?
curl -sS "$RENDER/api/health"

# 2) Rates present?
curl -sS "$RENDER/api/market-rate/by-category?service_id=6926b1978ba6a3cfc5a191ce&category_id=$QUOTE_TYPE_ID" \
  | jq '{count, service_category, service_type, null_ids:(.items|map(select(.pricing_id==null))|length)}'

# 3) Catalog auth?
curl -sS -X POST "$RENDER/api/market-rate/sync-catalog?live=1&service_id=6926b1978ba6a3cfc5a191ce" | jq .
```

In browser DevTools on Compare:

- Progress URL host = QuoteSense UI host  
- Response = JSON  
- If HTML 404 → frontend deploy/proxy issue  

In admin OTP:

- Phone must match the QuoteSense env’s Tatva admin  

In Supabase (correct project):

```sql
SELECT service_category, service_type, count(*)
FROM market_moving_averages
GROUP BY 1, 2
ORDER BY 1, 2;
```

---

## 14. Local run (optional for deep debugging)

```bash
# Terminal 1
cd backend && ./run_dev.sh          # http://127.0.0.1:8001

# Terminal 2
cd frontend && ./run_dev.sh         # http://localhost:3000
```

Backend `.env`: Supabase + Gemini + Tatva base/key for the env you want to mimic.  
Frontend `.env.local`: `NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8001`, `TATVA_API_BASE=…`.

Swagger: `http://127.0.0.1:8001/docs`.

---

## 15. Related docs (deeper detail)

| Doc | Use when |
|-----|----------|
| [`../README.md`](../README.md) | Full eng setup + file map |
| [`COMPARISON_DATA_LIFECYCLE.md`](./COMPARISON_DATA_LIFECYCLE.md) | Finalize vs compare vs cleanup |
| [`VENDOR_MARKET_RATE_API_PM.md`](./VENDOR_MARKET_RATE_API_PM.md) | PM vendor-form API contract |
| [`VENDOR_MARKET_RATE_API.md`](./VENDOR_MARKET_RATE_API.md) | Longer market-rate reference |

---

## 16. Smoke script

Run from repo root (requires `curl` + `jq`):

```bash
./scripts/qa_env_smoke.sh test
# or: ./scripts/qa_env_smoke.sh prod
# or: ./scripts/qa_env_smoke.sh dev
```

It prints health + by-category count for the mapped Render host. It does **not** replace UI OTP/compare testing.

---

## 17. How to report a bug (please include)

1. **Environment:** dev / test / prod  
2. **Exact URLs:** QuoteSense UI + admin + Render API used  
3. **Steps** + phone / project code / quote ids  
4. **Network screenshot:** failing request URL, status, response preview (JSON vs HTML)  
5. **Whether OTP appeared in which admin**  
6. **Time (IST)** and whether Render might have been cold  

---

**End of KT.** Prefer this document as the testing source of truth; update §2 hosts if Tatva renames domains.
