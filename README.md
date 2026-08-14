# QuoteSense Comparator

AI-powered quote extraction, comparison, and market-rate guidance for TatvaOps. FastAPI + Gemini extract and compare vendor quotes; Next.js provides the project hub, compare UI, and Tatva SSO/OTP auth; Supabase stores staging compare data and permanent market moving averages.

**Primary users:** interior design / construction procurement teams selecting among vendor quotes (Essential / Mid / Luxury tiers).

**Primary action:** pick 2–3 same-tier quotes on a project → run AI compare → review matrix, insights, and recommendation.

---

## Table of contents

1. [Overview](#overview)
2. [Features](#features)
3. [Tech stack](#tech-stack)
4. [Architecture](#architecture)
5. [Repository layout](#repository-layout)
6. [Prerequisites](#prerequisites)
7. [Installation & setup](#installation--setup)
8. [Environment configuration](#environment-configuration)
9. [Running locally](#running-locally)
10. [User flows](#user-flows)
11. [Backend API reference](#backend-api-reference)
12. [Backend file reference](#backend-file-reference)
13. [Frontend routes & BFF](#frontend-routes--bff)
14. [Frontend file reference](#frontend-file-reference)
15. [Database (Supabase) reference](#database-supabase-reference)
16. [Infrastructure & ops file reference](#infrastructure--ops-file-reference)
17. [Documentation index](#documentation-index)
18. [Testing](#testing)
19. [Deployment](#deployment)
20. [Troubleshooting](#troubleshooting)
21. [Quick checklist](#quick-checklist)

---

## Overview

QuoteSense:

- Loads Tatva PM projects and vendor quotes (WhatsApp OTP / PM SSO).
- Lets users select **2–3 quotes of the same tier** and run a comparison job.
- Optionally extracts line items from **PDF uploads** (feature-flagged standalone lane).
- Builds a Pandas comparison matrix with vendor totals and market moving-average baselines.
- Generates a Gemini AI recommendation and supports follow-up chat over session data.
- Serves **market-rate suggest/lookup** APIs for Tatva vendor quote forms.
- Merges rates into `market_moving_averages` **only for finalized quotes** (`isFinalizeQuote`), never from compare-display sessions alone.

---

## Features

- **AI PDF extraction** — Gemini Vision → taxonomy-constrained JSON → Supabase `quotes` / `quote_items`.
- **Tatva Mongo sync compare** — Project hub payloads (or server-side Tatva fetch) → async compare job with progress polling.
- **Cost matrix & charts** — Category / sub-service breakdown, Recharts vendor totals, relative insights.
- **AI recommendation + chat** — Gemini report over the comparison session; `/api/chat` Q&A.
- **Market rates** — Bundle-keyed moving averages (`service_type` + category + sub-service + pricing method); vendor-form suggest/by-category; finalize-only writes.
- **Auth** — WhatsApp OTP and PM JWT SSO via Next.js BFF → Tatva Users API.
- **Ecosystem shell** — Tatva app switcher, service deep links with SSO query params.
- **Ops** — Session cleanup cron, Render keep-alive, Vercel deploy workflows, QA smoke scripts.

---

## Tech stack

| Layer | Stack |
|-------|--------|
| Backend | Python 3.10+, FastAPI, Uvicorn, Pydantic, Google Genai, Pandas, Supabase client, httpx, PyMuPDF |
| Frontend | Next.js 16.1.6, React 19, TypeScript, Tailwind CSS 4, Recharts, jsPDF, Vitest |
| Data | Supabase PostgreSQL |
| Auth / PM | Tatva Users + Vendor APIs (`devopsapi.withtatva.ai`) |
| Hosting | Frontend → Vercel; Backend → Render; DB → Supabase |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (Next.js :3000)                                        │
│  AppShell → Auth → Dashboard → ProjectHub → /compare            │
│  BFF: /api/auth/*  /api/projects/*  /api/compare/*  market-rate │
└───────────────┬─────────────────────────────┬───────────────────┘
                │                             │
                ▼                             ▼
     Tatva Users / Vendor API          QuoteSense FastAPI (:8001)
     (OTP, profile, projects,          main.py pipelines
      vendor quotes)                         │
                                       ┌─────┴─────┐
                                       ▼           ▼
                                 extractor.py  comparator.py
                                 (Gemini PDF)  (Pandas + Gemini)
                                       │           │
                                       └─────┬─────┘
                                             ▼
                                        Supabase
                         quotes / quote_items (staging)
                         market_moving_averages (permanent)
                         market_moving_avg_sessions (dedup)
```

**Data rules (product):**

1. Compare sessions stage data for the matrix/chat; they set `market_rates_applied_at` for **cleanup only**.
2. Only finalized quote payloads merge into `market_moving_averages`.
3. `MARKET_RATE_UPDATES_ENABLED=false` freezes all MA writes.

See also: [`docs/COMPARISON_DATA_LIFECYCLE.md`](docs/COMPARISON_DATA_LIFECYCLE.md).

---

## Repository layout

```
tatvaops-quotesense/
├── README.md                 # This file
├── start-local.sh            # Prints how to start local dev
├── stop_dev.sh               # Kills ports 3000 / 8001
├── .vercelignore             # Excludes backend/docs/supabase from Vercel upload
├── backend/                  # FastAPI QuoteSense API
├── frontend/                 # Next.js app + BFF routes
├── supabase/                 # SQL migrations + seed
├── docs/                     # Product/API deep-dives
├── scripts/                  # QA / deploy verification helpers
├── .github/workflows/        # Deploy, cleanup, keep-alive
└── graphify-out/             # Generated knowledge graph (local tooling)
```

---

## Prerequisites

- Python **3.10+**
- Node.js **18+** and npm
- Git
- Credentials:
  - Google Gemini API key
  - Supabase URL + service role key
  - Tatva API access (for live projects/quotes/catalog; optional for pure PDF-local demos)

---

## Installation & setup

```bash
git clone <repo-url>
cd tatvaops-quotesense

# Backend
cd backend
python3 -m venv .venv          # or use ./run_dev.sh which can use a cache venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # fill real keys

# Frontend
cd ../frontend
npm install
cp .env.example .env.local     # fill backend URL + optional Tatva URLs
```

Or follow the printed instructions from:

```bash
./start-local.sh
```

---

## Environment configuration

### Backend — `backend/.env` (from `.env.example`)

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Gemini client for extract / recommend / chat |
| `SUPABASE_URL` | Postgres project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side DB access |
| `TATVA_API_BASE` | PM API base (default `https://devopsapi.withtatva.ai`) |
| `TATVA_API_KEY` | Preferred `x-api-key` for live catalogs |
| `TATVA_ADMIN_TOKEN` | Legacy Bearer fallback |
| `TATVA_QUOTE_TYPE_*_ID` | Essential / Mid / Luxury ObjectIds |
| `MARKET_RATE_UPDATES_ENABLED` | `false` freezes MA writes |
| `GEMINI_EXTRACT_MODEL` | Default `gemini-2.5-flash` |
| `GEMINI_EXPLICIT_CACHE` / `GEMINI_CACHE_TTL` | Extraction context cache |
| `TATVA_CATALOG_CACHE_TTL` | Live catalog cache seconds |

### Frontend — `frontend/.env.local` (from `.env.example`)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_BACKEND_URL` | Browser-reachable FastAPI base |
| `BACKEND_URL` | Server-only override (Vercel → Render) |
| `NEXT_PUBLIC_OPS_URL` / `DIRECT` / `FINANCE` / `VANTAGE` / `VISION` | Ecosystem switcher |
| `NEXT_PUBLIC_SERVICE_*` | Tatva service deep-link bases |
| `NEXT_PUBLIC_STANDALONE_PDF_ENABLED` | Gate PDF-only compare lane (see `feature-flags.ts`) |

---

## Running locally

**Preferred:**

```bash
# Terminal 1
cd backend && ./run_dev.sh          # http://127.0.0.1:8001  — docs at /docs

# Terminal 2
cd frontend && ./run_dev.sh         # http://localhost:3000
```

**Stop:**

```bash
./stop_dev.sh
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend | http://127.0.0.1:8001 |
| Swagger | http://127.0.0.1:8001/docs |
| ReDoc | http://127.0.0.1:8001/redoc |

---

## User flows

### Auth

1. `/login` or `/register` → WhatsApp OTP via BFF → tokens in `localStorage`.
2. Or PM SSO: landing with `jwt_auth`/`token` + `user_id` → profile bootstrap → redirect (`buildPmRedirectPath`).
3. Protected routes (`/`, `/project/*`, `/compare`) redirect to `/login?returnTo=…`.
4. Missing display name → `WelcomeNameModal`.

### Project → compare → insights

```
/  ProjectDashboard
 → /project/:publicCode  ProjectHub (select 2–3 same-tier quotes)
 → /compare?projectId=&quotes=
 → resolveQuotesForCompare (sessionStorage cache → BFF)
 → POST /api/compare/sync-mongodb → poll FastAPI /api/progress/:session_id
 → VendorChart + matrix + VendorInsights + RecommendationView + chat + PDF export
```

### Compare lanes (`compare-lane.ts`)

| Lane | Trigger | Behavior |
|------|---------|----------|
| `project` | `projectId` + quote ids | Mongo/Tatva JSON sync compare |
| `integrated` | PM SSO session context | Integrated loading banners / session |
| `standalone` | Flag-enabled PDF upload | Multipart `/api/compare-quotes` |

### Market rates

- Vendor form / demo: `MarketRatePanel` or `public/market-rate-embed.js` → FastAPI `/api/market-rate/*`.
- Project load: quotes BFF may `apply-finalized` + catalog sync.
- Finalize merges are idempotent via `finalize:<quoteNumber>` session keys.

---

## Backend API reference

All live routes are defined in `backend/main.py` (not `api/routes.py`, which is an empty stub).

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Liveness message |
| `GET` | `/api/health` | Gemini + Supabase readiness |
| `GET`/`HEAD` | `/api/market-rate/by-category` | Bulk rates for one main service + quotation type |
| `GET` | `/api/market-rate/lookup` | Exact bundle lookup |
| `GET`/`POST` | `/api/market-rate/suggest` | Vendor-form guidance (banner when rate exceeds base) |
| `POST` | `/api/market-rate/recommend` | Suggest with body model |
| `POST` | `/api/market-rate/apply-finalized` | Merge finalized payloads into MA |
| `POST` | `/api/market-rate/sync-catalog` | Refresh ObjectId maps |
| `POST` | `/api/compare-quotes` | Multipart PDF upload → async extract+compare (2–3 files) |
| `GET` | `/api/progress/{session_id}` | Poll job status / partial matrix / result |
| `POST` | `/api/sync-mongodb-quotes` | Tatva JSON or `project_id` fetch → async compare |
| `GET` | `/api/get-comparison` | Re-run compare from Supabase session |
| `POST` | `/api/chat` | Gemini Q&A over session quote data |

**Constraints:** 2–3 quotes per compare. Progress is in-process (`JOBS`); use a single Uvicorn worker for local progress polling.

**Vendor form contracts:** [`docs/VENDOR_MARKET_RATE_API.md`](docs/VENDOR_MARKET_RATE_API.md), [`docs/VENDOR_MARKET_RATE_API_PM.md`](docs/VENDOR_MARKET_RATE_API_PM.md).

### Example: health

```bash
curl http://127.0.0.1:8001/api/health
```

### Example: PDF compare

```bash
curl -X POST http://127.0.0.1:8001/api/compare-quotes \
  -F "files=@quote1.pdf" \
  -F "files=@quote2.pdf" \
  -F "session_id=my_session_123"
```

Then poll:

```bash
curl http://127.0.0.1:8001/api/progress/my_session_123
```

---

## Backend file reference

### Entry & config

#### `backend/main.py` (~1578 lines)

FastAPI application: CORS, request models, **all live HTTP routes**, in-memory `JOBS` progress, PDF compare pipeline (`_run_compare_pipeline`), Mongo sync pipeline (`_run_mongodb_sync_pipeline`), Supabase ingest helpers, startup probes.

**Key symbols:** `app`, market-rate handlers, `compare-quotes`, `progress`, `sync-mongodb-quotes`, `get-comparison`, `chat`, `_ingest_quotes_to_supabase`, `_parse_quotes_payload`, `MarketRateRequest`, `ChatRequest`.

**Calls:** `extractor`, `comparator`, `market_rate`, `tatva_*`, `env_config`.

#### `backend/api/routes.py`

Empty placeholder; **not imported** by `main.py`.

#### `backend/.env.example`

Documents secrets and feature flags for local/prod env files.

#### `backend/requirements.txt`

Pinned/runtime deps: FastAPI, Uvicorn, Pydantic, PyMuPDF, python-dotenv, supabase, pandas, python-multipart, tabulate, google-genai, pytest, pytest-cov, httpx.

#### `backend/.gitignore` / `backend/pytest.ini`

Ignore local artifacts; pytest configuration for `tests/`.

---

### Models

#### `backend/models/schema.py`

Pydantic extraction schema for Gemini structured output.

| Class | Role |
|-------|------|
| `WorkItem` | Line item (sub_service, qty, rate, amount, pricing_method, …) |
| `MainService` | Category + items |
| `ExtractedQuote` | Vendor/client, dates, totals, nested services |

Used as `response_schema` in `extractor.process_quote_with_gemini`.

#### `backend/models/taxanomy.py`

Filename spelling is intentional/legacy. Exports `TATVAOPS_TAXONOMY`: ~11 main categories and official sub-service names (~137) injected into extraction prompts to reduce hallucination. Consumed via `taxonomy_prompt.py`.

---

### Services

#### `backend/services/env_config.py`

Loads `backend/.env`; lazy Gemini and Supabase clients; `env_diagnostics()` for health. Shared by nearly every service.

**Exports:** `get_gemini_client()`, `get_supabase_client()`, `env_diagnostics()`, `ENV_PATH`.

#### `backend/services/taxonomy_prompt.py`

Static extraction system instruction + compact taxonomy string for Gemini caching.

**Exports:** `EXTRACTION_SYSTEM_INSTRUCTION`, `compact_taxonomy_for_prompt()`, `build_extraction_system_instruction()`.

#### `backend/services/extraction_cache.py`

Gemini explicit context cache for static rules + taxonomy (PDF bytes still per-request).

**Exports:** `get_extraction_cached_content_name()`, `invalidate_extraction_cache()`.  
**Env:** `GEMINI_EXPLICIT_CACHE`, `GEMINI_CACHE_TTL`.

#### `backend/services/extractor.py`

PDF → Gemini JSON → validation → Supabase insert.

**Exports:** `process_quote_with_gemini()`, `validate_extraction()`, `push_to_supabase()`, `process_single_pdf()`.  
Invoked by `_run_compare_pipeline`. Writes `quotes` / `quote_items`.

#### `backend/services/comparator.py`

Session DataFrame → comparison matrix + AI report; Mongo payloads → DataFrame; chat over session. Lazy-imports pandas for faster Uvicorn cold start.

**Exports:** `fetch_data()`, `run_comparison()`, `mongodb_quotes_to_dataframe()`, `handle_chat_query()`, `sanitize_for_json()`, `_unwrap_quote_payload()`.  
Uses market-rate lookups in display mode (`fast_moving_avg=True` skips MA writes). Recommendation timeout ~45s with fallback bullets.

#### `backend/services/market_rate.py` (~984 lines)

Bundle-keyed market moving averages, vendor recommendations, finalized-quote merges, compare-session cleanup stamps.

**Important exports:** `normalize_*`, `resolve_service_type()`, `resolve_effective_rate()`, `bundle_key()`, `lookup_market_rate()`, `list_market_rates_by_category()`, `recommend_rate()`, `update_rate_moving_average()`, `apply_finalized_quotes_to_market_rates()`, `finalize_session_market_rates()`, `is_finalize_quote_flag()`, `market_rate_updates_enabled()`.

**Tables:** `market_moving_averages`, `market_moving_avg_sessions`, `quotes`.

#### `backend/services/sub_service_catalog.py`

Interiors PM catalog names + spreadsheet aliases → canonical sub-service strings.

**Exports:** `INTERIORS_SUB_SERVICES`, `SUB_SERVICE_ALIASES`, `resolve_sub_services()`, `is_known_sub_service()`, `normalize_label()`.

#### `backend/services/tatva_catalog.py` (~819 lines)

Label ↔ Mongo ObjectId maps for sub-services and pricing methods; harvest from quotes; live Tatva admin fetch; split service vs quotation-type IDs.

**Exports:** `resolve_item_labels()`, `resolve_sub_service_id/label`, `resolve_pricing_method_id/label`, `harvest_ids_from_quotes()`, `ensure_live_catalog()`, `fetch_*_from_tatva()`, `split_service_and_category_ids()`, etc.  
Persists into `data/tatva_*.json`.

#### `backend/services/tatva_services.py`

Resolve Tatva main-service ObjectId → `service_category` name (API cache → static JSON / map).

**Exports:** `resolve_service_by_id()`.

#### `backend/services/tatva_fetch.py`

Server-side fetch of project vendor quotes from Tatva PM.

**Exports:** `fetch_project_quotes(project_id, authorization)`, `filter_quotes_by_ids()`.  
Endpoint pattern: `/vendor/api/vendor/quotes/project/{id}?quotationShare=true`.

---

### Data JSON

| File | Purpose |
|------|---------|
| `backend/data/tatva_service_ids.json` | Main-service ObjectId → `{service_category, service_code}` |
| `backend/data/tatva_sub_service_ids.json` | Sub-service label → ObjectId (grown by harvest/live fetch) |
| `backend/data/tatva_pricing_method_ids.json` | Pricing-method label → ObjectId |

---

### Scripts & runners

| File | Purpose |
|------|---------|
| `backend/run_dev.sh` | Preferred local start: free port, optional cache venv, `uvicorn main:app` (`PORT` default 8001) |
| `backend/start_uvicorn.sh` | Manual uvicorn via project/cache venv; Desktop/iCloud tips |
| `backend/start_backend.sh` | Absolute-path launcher with `/tmp` logging (macOS File Provider workaround) |
| `backend/scripts/run_tests.sh` | Install pytest if needed; coverage on `services` + `main` → `coverage.xml` |
| `backend/scripts/backfill_market_rates.py` | Rebuild `market_moving_averages` from all `quote_items` (`--dry-run` supported) |
| `backend/scripts/cleanup_comparison_sessions.py` | Delete staging quotes/items older than `--days` (default 7) where `market_rates_applied_at` set; never deletes MA table |

---

### Backend tests

| File | Coverage |
|------|----------|
| `backend/tests/conftest.py` | Fixtures: stub dotenv, mock unconfigured env, mock heavy clients |
| `backend/tests/test_api_health.py` | `/`, `/api/health`, cache headers, `_require_service_type` |
| `backend/tests/test_market_rate_helpers.py` | Pure helpers: normalize, effective rate, bundle key, finalize flags |
| `backend/tests/test_tatva_catalog_helpers.py` | Catalog unwrap / ObjectId / map-shape helpers |
| `backend/tests/__init__.py` | Package marker |

**Not unit-tested today:** full Gemini extract, end-to-end JOBS pipelines, Supabase MA writes (ops/manual).

```bash
cd backend && ./scripts/run_tests.sh
# or
pytest tests/ -q --cov=services --cov=main
```

---

## Frontend routes & BFF

### Pages

| Route | File | User action |
|-------|------|-------------|
| `/` | `app/page.tsx` | Project dashboard; `?session_id=` → `/compare` |
| `/login` | `app/login/page.tsx` | WhatsApp OTP sign-in; `returnTo` |
| `/register` | `app/register/page.tsx` | Name/email/phone → OTP → profile |
| `/project/[projectId]` | `app/project/[projectId]/page.tsx` | Project hub; canonical public code URL |
| `/compare` | `app/compare/page.tsx` | Compare lanes, matrix, insights, chat, PDF |
| `/compare` (loading UI) | `app/compare/loading.tsx` | Route-level spinner |
| `/market-rate-demo` | `app/market-rate-demo/page.tsx` | Unprotected `MarketRatePanel` demo |

### BFF (`app/api`)

| Route | Proxies / role |
|-------|----------------|
| `POST /api/auth/send-otp` | Tatva Users send OTP |
| `POST /api/auth/verify-otp` | Tatva Users verify → tokens |
| `GET`/`PUT /api/auth/profile` | Tatva Users profile |
| `GET /api/projects?userId=` | Paginated merge of user projects |
| `GET /api/projects/:id/quotes` | Vendor quotes + catalog sync + apply-finalized + UI annotate |
| `POST /api/compare/sync-mongodb` | Same-origin proxy → FastAPI sync-mongodb-quotes |
| `POST /api/market-rate/apply-finalized` | Proxy → FastAPI apply-finalized |

Client also calls FastAPI **directly** for progress, chat, PDF upload, and market lookup/recommend.

---

## Frontend file reference

### App shell & pages

#### `frontend/app/layout.tsx`

Root layout: metadata, favicon, `globals.css`, wraps children in `AppShell`.

#### `frontend/app/globals.css`

Global Tailwind / design tokens (`qs-card`, brand colors, shared utilities).

#### `frontend/app/page.tsx`

Home: auth gate + dynamic `ProjectDashboard`; redirects `session_id` to compare.  
**Exports:** `Home`, `HomeContent`.

#### `frontend/app/login/page.tsx`

OTP login with `safeReturnTo` / `cleanReturnTo` sanitization.

#### `frontend/app/register/page.tsx`

Registration flow (name/email → OTP → profile PUT).

#### `frontend/app/project/[projectId]/page.tsx`

Loads project+quotes; canonicalizes to public code; renders `ProjectHub`.

#### `frontend/app/compare/page.tsx` (~1002 lines)

Main compare UX: lane detection, job start/poll, matrix, chart, insights, recommendation, chat, PDF download.  
**Exports:** `Home`, `QuoteSenseContent`, helpers.

#### `frontend/app/compare/loading.tsx`

First-load spinner for `/compare` compilation.

#### `frontend/app/market-rate-demo/page.tsx`

Interactive market guidance demo (not auth-guarded).

---

### BFF route handlers

| File | Exports | Notes |
|------|---------|-------|
| `app/api/auth/send-otp/route.ts` | `POST` | Phone → WhatsApp OTP |
| `app/api/auth/verify-otp/route.ts` | `POST` | Returns tokens + user |
| `app/api/auth/profile/route.ts` | `GET`, `PUT` | Normalizes `name` / `fullName` |
| `app/api/projects/route.ts` | `GET` | Multi-page merge; `X-Projects-*` headers |
| `app/api/projects/[projectId]/quotes/route.ts` | `GET` | Quotes + finalize/catalog side effects + dual badges |
| `app/api/compare/sync-mongodb/route.ts` | `POST` | CORS-safe compare start |
| `app/api/market-rate/apply-finalized/route.ts` | `POST` | Finalized → MA |

---

### Shell & chrome components

| File | Role |
|------|------|
| `components/AppShell.tsx` | `AuthProvider`, route protection, header/footer/name modal |
| `components/SiteHeader.tsx` | Logo, ecosystem menu, avatar → profile, sign-in/out |
| `components/Footer.tsx` | Marketing/legal footer on logged-out auth pages |
| `components/AuthPageLayout.tsx` | Centered auth card + `inputClass` + legal footer |
| `components/TatvaLogo.tsx` | Brand mark / link |
| `components/TatvaEcosystemMenu.tsx` | Ops/Connect/Direct/Finance/Vantage/Vision switcher |
| `components/WhatsAppIcon.tsx` | WhatsApp SVG for OTP CTAs |
| `components/WelcomeNameModal.tsx` | Blocking name capture via profile PUT |
| `components/ProfileModal.tsx` | Edit name/username/email |
| `components/LoginModal.tsx` | Modal OTP login (alternate to `/login`) |

---

### Dashboard components

| File | Role |
|------|------|
| `components/dashboard/ProjectDashboard.tsx` | Search/filter projects, empty/error states, PDF section |
| `components/dashboard/ProjectTile.tsx` | Project card → `/project/:code` |
| `components/dashboard/StandalonePdfSection.tsx` | Dashboard CTA for PDF-only compare |
| `components/dashboard/PdfUploadGateButton.tsx` | Flag gate + recovery modal (`PdfUploadRecoveryModal`, `StandalonePdfCompareGuard`) |

---

### Project hub components

| File | Role |
|------|------|
| `components/project/ProjectHub.tsx` | Vendor/quote selection, tier rules, cache payloads, navigate to compare, service SSO nav |
| `components/project/VendorCard.tsx` | Per-vendor quote list + “compare this vendor” |
| `components/project/QuoteRow.tsx` | Checkbox row: lifecycle badge + FINALIZED badge, tier, amount |
| `components/project/CompareActionBar.tsx` | Sticky bar: count, clear, Compare |
| `components/project/CompareSelectionBanner.tsx` | Compare nav/loading banners (`ComparePageNav`, `CompareLoadingBanner`, `IntegratedLoadingBanner`) |

---

### Compare / insights / market UI

| File | Role |
|------|------|
| `components/CompareLoadingPanel.tsx` | Staged progress (extract → matrix → recommend) |
| `components/VendorChart.tsx` | Recharts bar chart of vendor totals |
| `components/VendorInsights.tsx` | Category filter, totals, relative bars |
| `components/RecommendationView.tsx` | AI recommendation bullets |
| `components/quote/MarketRatePanel.tsx` | Lookup/recommend + low/fair/high verdict UI |

---

### Lib modules

| File | Purpose / key exports |
|------|------------------------|
| `lib/auth.tsx` | `AuthProvider`, `useAuth`, `getAuthToken`, `getAuthUserId`; SSO bootstrap, OTP, session |
| `lib/tatva-api.ts` | Tatva base URLs + `TatvaUser` / OTP types |
| `lib/backend-url.ts` | `getBackendBase()` — `BACKEND_URL` → `NEXT_PUBLIC_BACKEND_URL` → localhost |
| `lib/project-api.ts` | `fetchUserProjects`, `fetchProjectWithQuotes`, `resolveProjectRefForCompare`, `projectHref` |
| `lib/project-mappers.ts` | Tatva JSON → `ProjectData` / vendors / summaries; finalize/tier mapping |
| `lib/project-resolve.ts` | Public code ↔ Mongo id; `buildPmRedirectPath` |
| `lib/project-types.ts` | Domain types, `TATVA_SERVICES`, `formatInr`, selection helpers |
| `lib/project-list-filter.ts` | Dashboard search + service filter |
| `lib/projects-pagination.ts` | Pure pagination merge helpers for projects BFF |
| `lib/compare-sync.ts` | `resolveQuotesForCompare`, `startMongoCompareJob`, session id helpers |
| `lib/compare-progress.ts` | Adaptive poll of `/api/progress/:id` (up to ~25 min) |
| `lib/compare-payload-cache.ts` | `sessionStorage` quote payload cache (TTL) |
| `lib/compare-limits.ts` | `MIN/MAX_COMPARE_QUOTES` (2–3), clamp/validate |
| `lib/compare-lane.ts` | `getCompareLane`, `showPdfUpload`, `showProjectNav` |
| `lib/compare-matrix.ts` | Group table rows; sub-service sums incl. `moving_average` |
| `lib/download-comparison-pdf.ts` | jsPDF export of comparison matrix |
| `lib/format.ts` | Vendor labels, INR, chart axis, price-vs-baseline copy |
| `lib/market-rate.ts` | Client lookup/recommend + verdict styles |
| `lib/market-rate-apply.ts` | Filter finalized payloads; background apply-finalized |
| `lib/finalize-flags.ts` | Finalize/truthy flag detection; `digitsOnly` |
| `lib/quote-ui-status.ts` | Annotate UI status without rewriting Tatva `status` |
| `lib/feature-flags.ts` | `STANDALONE_PDF_UPLOAD_ENABLED` + recovery copy |
| `lib/tatva-services.ts` | Service deep links with JWT SSO params |
| `lib/tatva-ecosystem.ts` | Ecosystem app switcher config |
| `lib/user-display.ts` | Display name / initial / needs-name (never show phone as name) |
| `lib/dummy-project-data.ts` | Offline demo fixtures (`DUMMY_PROJECT*`); live path uses `project-api` |

---

### Frontend tests

| File | Covers |
|------|--------|
| `lib/__tests__/compare-limits.test.ts` | 2–3 quote limits |
| `lib/__tests__/format.test.ts` | Label/INR/baseline helpers |
| `lib/__tests__/project-helpers.test.ts` | Mappers / project helpers |
| `lib/__tests__/project-list-filter.test.ts` | Dashboard filter |
| `lib/__tests__/projects-pagination.test.ts` | BFF pagination helpers |
| `lib/__tests__/sonar-gates.test.ts` | Sonar/quality gate helpers |

```bash
cd frontend && npm test
```

---

### Frontend config, scripts, assets

| File | Purpose |
|------|---------|
| `frontend/package.json` | Scripts: `dev`, `build`, `test`, `test:coverage`; deps Next/React/Recharts/jsPDF |
| `frontend/package-lock.json` | Lockfile |
| `frontend/next.config.ts` | Turbopack root, remote images, webpack polling for iCloud Desktop |
| `frontend/tsconfig.json` | TS paths (`@/*`) |
| `frontend/next-env.d.ts` | Next-generated types |
| `frontend/postcss.config.mjs` | Tailwind PostCSS |
| `frontend/eslint.config.mjs` | ESLint Next config |
| `frontend/vitest.config.ts` | Vitest node env + coverage excludes |
| `frontend/sonar-project.properties` | SonarQube frontend settings |
| `frontend/.env.example` | Documented env vars |
| `frontend/.gitignore` | Ignores `.next`, `node_modules`, env locals, etc. |
| `frontend/scripts/dev.sh` | Primary `npm run dev`: free port 3000, polling watchers, webpack default |
| `frontend/run_dev.sh` | iCloud-safe install under `/tmp/qs-frontend-app` + symlink `node_modules` |
| `frontend/start_frontend.sh` | Minimal `npx next dev` on 3000 |
| `frontend/README.md` | Stock create-next-app stub (product docs live in root README) |
| `frontend/public/logo_fevicon.png` | Favicon / brand |
| `frontend/public/tatva_assets.jpg` | Brand imagery |
| `frontend/public/market-rate-embed.js` | Vanilla `TatvaMarketRate.mount` embed for withtatva.ai forms |
| `frontend/public/*.svg` | Default Next placeholder SVGs (`file`, `globe`, `next`, `vercel`, `window`) |

---

## Database (Supabase) reference

Base tables (`quotes`, `quote_items`, `market_moving_averages`) are assumed to exist before numbered migrations.

### Tables (product roles)

| Table | Role | Retention |
|-------|------|-----------|
| `quotes` + `quote_items` | Staging for compare/chat | Deleted after applied + ~7 days |
| `market_moving_averages` | Recommended base rates (Yash/PM API) | Permanent |
| `market_moving_avg_sessions` | Dedup (incl. `finalize:<quoteNumber>`) | Trimmed with cleanup |

### Migrations

| File | Purpose |
|------|---------|
| `supabase/migrations/001_market_moving_avg_sessions.sql` | Creates session-dedup table for MA updates |
| `supabase/migrations/002_market_rate_bundle.sql` | Bundle columns: `pricing_method`, `rate_moving_average`, `service_type` on MA; item fields + index |
| `supabase/migrations/003_market_rate_tier_multipliers.sql` | **Deprecated historical** synthetic MID/LUXURY multipliers — removed by 006 |
| `supabase/migrations/004_quotes_market_rates_applied.sql` | Adds `quotes.market_rates_applied_at` + index for cleanup |
| `supabase/migrations/005_fix_placeholder_rate_junk.sql` | Deletes MA rows with `rate_moving_average <= 1` |
| `supabase/migrations/006_remove_tier_multiplier_math.sql` | Deletes `TIER_MULTIPLIER_%` synthetic rows |
| `supabase/migrations/007_seed_interiors_base_rates.sql` | Truncates MA tables; seeds ~19 Interiors bundles × 3 tiers |
| `supabase/migrations/008_fix_luxury_base_to_1_5x_mid.sql` | Sets LUXURY = Mid × 1.5 |

### Seed

#### `supabase/seed.sql`

Idempotent demo session `seed_demo_0001` (two vendors + line items). Load compare via `/?session_id=seed_demo_0001` when data is present.

---

## Infrastructure & ops file reference

### Root scripts

| File | Purpose |
|------|---------|
| `start-local.sh` | Prints two-terminal start instructions (does not spawn processes) |
| `stop_dev.sh` | Kills listeners on **3000** and **8001** + related pkill patterns |
| `scripts/verify-test-deploy.sh` | Smoke-check QA frontend (`testquotesense.withtatva.ai`) quotes UI annotation |
| `scripts/apply_finalized_qa.sh` | POST finalized JSON into QA Render `apply-finalized` |

### GitHub Actions

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `.github/workflows/deploy_dev.yml` | `push` → `dev`, dispatch | Build frontend; Vercel deploy (dev project). Syncs Tatva API base. |
| `.github/workflows/deploy_test.yml` | `push` → `test`, dispatch | Build frontend; Vercel QA deploy; points backend URLs at Render QA |
| `.github/workflows/deploy_prod.yml` | `push` → `main` | Build frontend; Vercel prod deploy |
| `.github/workflows/cleanup_comparison_sessions.yml` | Cron `30 3 * * *` UTC + dispatch | Runs `cleanup_comparison_sessions.py` (needs Supabase secrets) |
| `.github/workflows/keep_alive.yml` | Cron every 12 min + dispatch | Pings prod Render `/api/health` to reduce idle sleep |

**Hosting map:** Frontend → Vercel (dev/test/prod projects); Backend → Render (`tatvaops-quotesense`, `tatvaops-quotesense-qa`); Tatva API → `https://devopsapi.withtatva.ai`.

### Other root / tooling

| Path | Purpose |
|------|---------|
| `.vercelignore` | Excludes `backend`, `docs`, `supabase`, `.github`, venvs, etc. from Vercel upload |
| `.cursor/rules/graphify.mdc` | Agent rule: use graphify before codebase exploration |
| `graphify-out/` | Generated knowledge graph artifacts (local) |

---

## Documentation index

| Path | Audience | Summary |
|------|----------|---------|
| `README.md` (this file) | Everyone | Setup, architecture, **full file reference** |
| `docs/QA_TESTING_KT.md` | **QA / testing** | Full KT: env pairings, OTP↔admin, compare/progress, market-rate, checklists, known pitfalls |
| `scripts/qa_env_smoke.sh` | QA / ops | Curl smoke for health + by-category (`./scripts/qa_env_smoke.sh test`) |
| `docs/COMPARISON_DATA_LIFECYCLE.md` | Ops / backend | Staging vs permanent tables, finalize-only MA, cleanup Action, gate flag |
| `docs/VENDOR_MARKET_RATE_API.md` | Integrators | Detailed suggest/by-category/lookup contract, verdict bands, caching |
| `docs/VENDOR_MARKET_RATE_API_PM.md` | PM quote-form | Shorter PM contract: `service_id` vs `category_id` (quote type), prod base URL, freeze flag |
| `frontend/README.md` | Dev | Stock Next.js getting-started stub |

---

## Testing

```bash
# Backend
cd backend && ./scripts/run_tests.sh

# Frontend
cd frontend && npm test
# coverage:
cd frontend && npm run test:coverage
```

---

## Deployment

### Frontend (Vercel)

- Branches: `dev` → dev project; `test` → QA (`testquotesense.withtatva.ai`); `main` → prod.
- Set `BACKEND_URL` / `NEXT_PUBLIC_BACKEND_URL` to the matching Render backend.
- Vercel **Root Directory must be empty (`./`)** for Dev and QA. CI runs `vercel` from `frontend/`
  (see `deploy_dev.yml` / `deploy_test.yml`). Setting Root Directory to `frontend` causes
  `frontend/frontend` or “No Next.js version detected” depending on cwd.

### Backend (Render)

- Deploy FastAPI from `backend/` with `uvicorn main:app`.
- Configure all vars from `backend/.env.example`.
- Prod health keep-alive: `.github/workflows/keep_alive.yml`.

### Database

Apply `supabase/migrations/*.sql` in order on each environment; use `seed.sql` only for demos.

### Manual QA helpers

```bash
# Verify QA quotes annotation
AUTH_TOKEN=... ./scripts/verify-test-deploy.sh

# Apply a finalized payload to QA MA
./scripts/apply_finalized_qa.sh path/to/payload.json
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'fastapi'`

```bash
cd backend && source .venv/bin/activate
pip install -r requirements.txt
```

### Missing `GEMINI_API_KEY` / Supabase env

Ensure keys live in **`backend/.env`** (not only repo root). Confirm with:

```bash
curl http://127.0.0.1:8001/api/health
```

### Frontend cannot reach backend

```bash
curl http://127.0.0.1:8001/
# frontend/.env.local:
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8001
```

Restart `frontend` after env changes.

### Port already in use

```bash
./stop_dev.sh
# or
lsof -i :3000
lsof -i :8001
```

### PDF extraction empty / failing

1. Valid Gemini key and model (`GEMINI_EXTRACT_MODEL`).
2. Readable PDF (not scanned garbage / corrupt).
3. Supabase reachable for persist.
4. Inspect Uvicorn logs during `/api/compare-quotes` + `/api/progress/...`.

### Next.js build / flaky Desktop iCloud

```bash
cd frontend
rm -rf .next
npm run dev:clean   # or ./run_dev.sh (tmp install path)
```

`next.config.ts` and `run_dev.sh` include polling / `/tmp` workarounds for iCloud Desktop paths.

### Market averages not updating

1. Quote must be **finalized** (`isFinalizeQuote`).
2. `MARKET_RATE_UPDATES_ENABLED` must not be `false`.
3. Compare-only sessions never write MA (by design).

### Cleanup deletes nothing

Cleanup only removes rows with `market_rates_applied_at IS NOT NULL`. Until compare finalize-stamp is live, the column stays null → no deletes. See lifecycle doc.

---

## Quick checklist

- [ ] Python 3.10+ and Node 18+ installed
- [ ] `backend/.env` filled from `.env.example`
- [ ] `frontend/.env.local` filled from `.env.example`
- [ ] `pip install -r backend/requirements.txt`
- [ ] `npm install` in `frontend/`
- [ ] `backend/run_dev.sh` → http://127.0.0.1:8001/docs
- [ ] `frontend/run_dev.sh` → http://localhost:3000
- [ ] Login / OTP or PM SSO works
- [ ] Open a project → select 2–3 quotes → compare completes
- [ ] (Optional) Supabase migrations applied; seed demo session loaded
- [ ] Backend tests + frontend tests pass

---

## License

Proprietary to TatvaOps. All rights reserved.

---

## Support

- File GitHub issues for bugs and improvements.
- Market-rate integrators: start with `docs/VENDOR_MARKET_RATE_API_PM.md`.
- Data retention / MA ops: `docs/COMPARISON_DATA_LIFECYCLE.md`.
