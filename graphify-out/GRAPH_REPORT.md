# Graph Report - tatvaops-quotesense  (2026-08-11)

## Corpus Check
- 133 files · ~66,603 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1007 nodes · 2049 edges · 72 communities (56 shown, 16 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.77)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `16767346`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- comparator.py
- ProjectHub.tsx
- auth.tsx
- tatva_catalog.py
- project-mappers.ts
- dependencies
- tatva-api.ts
- compilerOptions
- extractor.py
- download-comparison-pdf.ts
- _require_service_type
- tatva_services.py
- market_rate.py
- compare/page.tsx
- main.py
- market_rate_sync_catalog
- sonar-gates.test.ts
- Vendor Market Rate API — withtatva.ai Quote Form Integration
- get
- TatvaEcosystemMenu.tsx
- Services
- tatva_fetch.py
- resolve_sub_services
- CompareLoadingPanel.tsx
- test_market_rate_helpers.py
- compare-progress.ts
- dev.sh
- _run_mongodb_sync_pipeline
- market_rate_by_category
- market-rate-embed.js
- backend/run_dev.sh
- devDependencies
- eslint.config.mjs
- next.config.ts
- postcss.config.mjs
- frontend/run_dev.sh
- start-local.sh
- normalize_service_type
- QuoteSense Comparator
- apply_finalized_quotes_to_market_rates
- compare-payload-cache.ts
- scripts
- get_supabase_client
- App shell & pages
- Frontend file reference
- Troubleshooting
- conftest.py
- CompareSelectionBanner.tsx
- compare-sync.ts
- resolve_service_type
- CompareChat.tsx
- User flows
- Deployment
- Database (Supabase) reference
- Infrastructure & ops file reference
- start_backend.sh
- start_uvicorn.sh
- EmptyState.tsx
- frontend/README.md
- Backend API reference
- Environment configuration
- Frontend routes & BFF
- run_tests.sh
- eslint-config-next
- @vitest/coverage-v8
- start_frontend.sh
- apply_finalized_qa.sh
- stop_dev.sh

## God Nodes (most connected - your core abstractions)
1. `get_supabase_client()` - 26 edges
2. `QuoteSense Comparator` - 25 edges
3. `useAuth()` - 23 edges
4. `getAuthUserId()` - 19 edges
5. `normalize_service_type()` - 17 edges
6. `fetch_pricing_methods_from_tatva()` - 16 edges
7. `fetch_sub_services_from_tatva()` - 16 edges
8. `buildVendorLabels()` - 16 edges
9. `compilerOptions` - 16 edges
10. `normalize_text()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `_resolve_lookup_category()` --indirect_call--> `resolve_service_by_id()`  [INFERRED]
  backend/main.py → backend/services/tatva_services.py
- `market_rate_by_category()` --indirect_call--> `list_market_rates_by_category()`  [INFERRED]
  backend/main.py → backend/services/market_rate.py
- `market_rate_by_category()` --indirect_call--> `resolve_service_by_id()`  [INFERRED]
  backend/main.py → backend/services/tatva_services.py
- `market_rate_lookup()` --indirect_call--> `recommend_rate()`  [INFERRED]
  backend/main.py → backend/services/market_rate.py
- `market_rate_suggest_get()` --indirect_call--> `recommend_rate()`  [INFERRED]
  backend/main.py → backend/services/market_rate.py

## Import Cycles
- None detected.

## Communities (72 total, 16 thin omitted)

### Community 0 - "comparator.py"
Cohesion: 0.12
Nodes (23): health(), _agent_debug_log(), _build_fallback_report(), fetch_data(), _generate_recommendation(), handle_chat_query(), _line_item_key(), _PandasLazy (+15 more)

### Community 1 - "ProjectHub.tsx"
Cohesion: 0.23
Nodes (14): CompareActionBar(), CompareActionBarProps, selectionCopy(), ProjectHubProps, VendorCard(), VendorCardProps, clampQuoteIds(), dedupeQuoteIds() (+6 more)

### Community 2 - "auth.tsx"
Cohesion: 0.05
Nodes (54): dmSans, metadata, cleanReturnTo(), LoginContent(), safeReturnTo(), HomeContent(), ProjectDashboard, ProjectDetailContent() (+46 more)

### Community 3 - "tatva_catalog.py"
Cohesion: 0.07
Nodes (68): _admin_auth_headers(), apply_catalog_maps(), _cache_fresh(), _catalog_auth_missing_message(), ensure_live_catalog(), _ensure_maps_loaded(), _entry_name_and_id(), fetch_pricing_methods_from_tatva() (+60 more)

### Community 4 - "project-mappers.ts"
Cohesion: 0.05
Nodes (83): PdfUploadGateButton(), DashboardError, isAuthSessionError(), ProjectDashboard(), formatUpdated(), ProjectTile(), ProjectTileProps, StandalonePdfSection() (+75 more)

### Community 5 - "dependencies"
Cohesion: 0.12
Nodes (16): dependencies, jspdf, jspdf-autotable, next, react, react-dom, recharts, name (+8 more)

### Community 6 - "tatva-api.ts"
Cohesion: 0.13
Nodes (18): GET(), pageUrl(), withMergedList(), dedupeById(), findList(), idsOf(), JsonRecord, LIST_KEYS (+10 more)

### Community 7 - "compilerOptions"
Cohesion: 0.07
Nodes (29): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+21 more)

### Community 8 - "extractor.py"
Cohesion: 0.11
Nodes (24): ExtractedQuote, MainService, BaseModel, WorkItem, _cache_ttl(), _explicit_cache_enabled(), get_extraction_cached_content_name(), invalidate_extraction_cache() (+16 more)

### Community 9 - "download-comparison-pdf.ts"
Cohesion: 0.08
Nodes (50): ComparisonMatrix(), Props, ChartRow, Props, relativeLabel(), VendorSummary(), ChartPoint, ChartRow (+42 more)

### Community 10 - "_require_service_type"
Cohesion: 0.16
Nodes (17): market_rate_lookup(), market_rate_recommend(), market_rate_suggest_get(), market_rate_suggest_post(), _missing_service_type_error(), Resolve main-service category name for suggest/lookup/recommend. New PM…, Resolve labels from ObjectIds and/or names. Returns (sub, pm, error)., Resolve quotation type; return (type, None) or (None, error_payload). (+9 more)

### Community 11 - "tatva_services.py"
Cohesion: 0.21
Nodes (15): _fetch_services_from_api(), _get_services_cached(), _load_static_service_map(), _normalize_service_name(), SSLContext, Resolve Tatva PM service ObjectIds to service category names., Map Tatva PM service ObjectId → service_category name used in…, Strip zero-width chars Tatva sometimes prefixes on service names. (+7 more)

### Community 12 - "market_rate.py"
Cohesion: 0.14
Nodes (15): _above_market_message(), _base_rate_message(), _label_ids(), Market rate moving averages and vendor form recommendations. Bundle key (exact…, Compare entered rate to recommended base only (no ±% band)., Short actionable guidance for PM UI chips / banners., Attach Tatva ObjectIds when the catalog (live or static) knows the labels., Flat item row for PM bulk cache — labels + ObjectIds when known. (+7 more)

### Community 13 - "compare/page.tsx"
Cohesion: 0.15
Nodes (14): isErrorReport(), isStaleSessionMessage(), QuoteSenseContent(), VendorChart, PdfUploadGateButtonProps, StandalonePdfCompareGuard(), RecommendationView(), renderInline() (+6 more)

### Community 14 - "main.py"
Cohesion: 0.19
Nodes (12): _agent_debug_log(), ChatRequest, MarketRateRequest, MarketRateSuggestRequest, _probe_supabase_tables(), BaseModel, # NOTE: this lives in the process, so it assumes a single uvicorn worker (the, Vendor quote form (withtatva.ai) — exact bundle match for market guidance. (+4 more)

### Community 15 - "market_rate_sync_catalog"
Cohesion: 0.21
Nodes (14): chat_with_data(), market_rate_apply_finalized(), market_rate_sync_catalog(), _parse_quotes_payload(), Any, _quote_ids_from_payload(), Normalize Tatva/MongoDB quote payloads to a list of quote dicts., RECEIVES: Tatva/MongoDB quote JSON (list or single object), OR project_id +… (+6 more)

### Community 16 - "sonar-gates.test.ts"
Cohesion: 0.12
Nodes (25): POST(), POST(), applyFinalizedQuotesFromPayload(), GET(), RouteContext, syncMarketRateCatalog(), PRICING_METHODS, SAMPLE_ITEMS (+17 more)

### Community 17 - "Vendor Market Rate API — withtatva.ai Quote Form Integration"
Cohesion: 0.05
Nodes (36): Comparison data lifecycle, Do not run cleanup DELETE before backend deploy, Flow, Gate, GitHub Actions setup, Manual commands, Migration, Product rules (+28 more)

### Community 18 - "get"
Cohesion: 0.15
Nodes (15): _format_quote_date(), get_existing_comparison(), get_progress(), _ingest_quotes_to_supabase(), _mongodb_quote_metadata(), _quote_line_item(), Poll endpoint for the async compare pipeline. ``has_partial`` lets the frontend…, Push quote headers + line items to Supabase. Returns quotes ingested. (+7 more)

### Community 19 - "TatvaEcosystemMenu.tsx"
Cohesion: 0.29
Nodes (7): TatvaEcosystemMenu(), CURRENT_APP_ID, CURRENT_APP_LABEL, envUrl(), getTatvaEcosystemApps(), TatvaApp, TatvaAppId

### Community 20 - "Services"
Cohesion: 0.08
Nodes (24): `backend/api/routes.py`, `backend/.env.example`, Backend file reference, `backend/.gitignore` / `backend/pytest.ini`, `backend/main.py` (~1578 lines), `backend/models/schema.py`, `backend/models/taxanomy.py`, `backend/requirements.txt` (+16 more)

### Community 21 - "tatva_fetch.py"
Cohesion: 0.36
Nodes (7): _unwrap_quote_payload(), fetch_project_quotes(), filter_quotes_by_ids(), Fetch Tatva PM vendor quotes server-side (MongoDB lane + project_id)., GET vendor quotes for a Tatva project (Mongo _id)., _tatva_api_base(), _unwrap_quotes_list()

### Community 22 - "resolve_sub_services"
Cohesion: 0.32
Nodes (6): is_known_sub_service(), normalize_label(), PM Interiors sub-service catalog + spreadsheet alias map. Lookup is case-…, Trim and collapse internal whitespace., Map a free-text sub_service to exact PM catalog name(s). Matching order: 1)…, resolve_sub_services()

### Community 23 - "CompareLoadingPanel.tsx"
Cohesion: 0.38
Nodes (6): CompareLoadingPanel(), CompareProgressStage, formatElapsed(), Props, stepIndex(), STEPS

### Community 24 - "test_market_rate_helpers.py"
Cohesion: 0.16
Nodes (19): is_amount_based_pricing_method(), market_rate_updates_enabled(), When false, finalized-quote MA writers must not rewrite market_moving_averages…, Return a trustworthy per-unit rate for moving-average purposes. If the vendor…, resolve_effective_rate(), Unit tests for pure market-rate helpers (high coverage, no DB)., test_bundle_key_normalizes_fields(), test_is_amount_based_pricing_method() (+11 more)

### Community 25 - "compare-progress.ts"
Cohesion: 0.38
Nodes (6): CompareProgressPayload, pollCompareProgress(), PollCompareProgressOptions, PollCompareProgressResult, pollDelayMs(), sleep()

### Community 26 - "dev.sh"
Cohesion: 0.33
Nodes (5): CHOKIDAR_USEPOLLING, _dbg(), dev.sh script, WATCHPACK_POLLING, WATCHPACK_POLLING_INTERVAL

### Community 27 - "_run_mongodb_sync_pipeline"
Cohesion: 0.24
Nodes (10): handle_customer_upload(), Background worker: compare in-memory from payloads, persist to Supabase after., Background worker: extract every PDF in parallel, then compare. Updates the…, Receives PDFs, saves them, and kicks off the extract+compare pipeline in the…, _run_compare_pipeline(), _run_mongodb_sync_pipeline(), _set_progress(), finalize_session_market_rates() (+2 more)

### Community 28 - "market_rate_by_category"
Cohesion: 0.16
Nodes (10): market_rate_by_category(), _market_rate_by_category_cache_control(), _market_rate_by_category_response(), Bulk market rates for one Main Service. PM contract: service_id → main service…, client(), fixture, FastAPI smoke tests for root + health endpoints., test_market_rate_cache_control_helpers() (+2 more)

### Community 31 - "devDependencies"
Cohesion: 0.12
Nodes (17): eslint, devDependencies, eslint, tailwindcss, @tailwindcss/postcss, @types/node, @types/react, @types/react-dom (+9 more)

### Community 36 - "frontend/run_dev.sh"
Cohesion: 0.33
Nodes (5): CHOKIDAR_USEPOLLING, NEXT_PUBLIC_BACKEND_URL, NODE_OPTIONS, run_dev.sh script, WATCHPACK_POLLING

### Community 39 - "normalize_service_type"
Cohesion: 0.27
Nodes (15): aggregate(), fetch_all_quote_items(), main(), bundle_key(), _canonical_sub_service_names(), list_market_rates_by_category(), lookup_market_rate(), normalize_pricing_method() (+7 more)

### Community 40 - "QuoteSense Comparator"
Cohesion: 0.13
Nodes (15): Architecture, Documentation index, Features, Installation & setup, License, Overview, Prerequisites, Quick checklist (+7 more)

### Community 41 - "apply_finalized_quotes_to_market_rates"
Cohesion: 0.23
Nodes (13): mongodb_quotes_to_dataframe(), Build a comparison DataFrame directly from Tatva/MongoDB quote JSON., apply_finalized_quotes_to_market_rates(), finalize_quote_already_applied_to_ma(), finalized_quote_session_id(), is_finalize_quote_flag(), Any, True when Tatva/platform marks this payload as the user-selected final quote. (+5 more)

### Community 42 - "compare-payload-cache.ts"
Cohesion: 0.26
Nodes (12): ProjectHub(), CacheEntry, cacheProjectQuotePayloads(), cacheSelectedComparePayloads(), CompareProjectMeta, getCachedQuotesByIds(), KEY(), RawQuote (+4 more)

### Community 43 - "scripts"
Cohesion: 0.15
Nodes (13): scripts, build, dev, dev:built, dev:clean, dev:turbo, dev:webpack, lint (+5 more)

### Community 44 - "get_supabase_client"
Cohesion: 0.30
Nodes (11): cleanup(), _cutoff_iso(), _fetch_stale_quote_ids(), main(), get_supabase_client(), fetch_market_rate_row(), Merge session batch of raw rates into stored weighted moving average., _record_session() (+3 more)

### Community 45 - "App shell & pages"
Cohesion: 0.20
Nodes (10): App shell & pages, `frontend/app/compare/loading.tsx`, `frontend/app/compare/page.tsx` (~1002 lines), `frontend/app/globals.css`, `frontend/app/layout.tsx`, `frontend/app/login/page.tsx`, `frontend/app/market-rate-demo/page.tsx`, `frontend/app/page.tsx` (+2 more)

### Community 46 - "Frontend file reference"
Cohesion: 0.22
Nodes (9): BFF route handlers, Compare / insights / market UI, Dashboard components, Frontend config, scripts, assets, Frontend file reference, Frontend tests, Lib modules, Project hub components (+1 more)

### Community 47 - "Troubleshooting"
Cohesion: 0.22
Nodes (9): Cleanup deletes nothing, Frontend cannot reach backend, Market averages not updating, Missing `GEMINI_API_KEY` / Supabase env, `ModuleNotFoundError: No module named 'fastapi'`, Next.js build / flaky Desktop iCloud, PDF extraction empty / failing, Port already in use (+1 more)

### Community 48 - "conftest.py"
Cohesion: 0.33
Nodes (6): mock_env_unconfigured(), mock_heavy_clients(), fixture, Shared pytest fixtures for QuoteSense backend tests., Prevent startup Supabase probes and keep health checks deterministic., Stub Gemini/Supabase clients so FastAPI app import stays offline.

### Community 49 - "CompareSelectionBanner.tsx"
Cohesion: 0.33
Nodes (6): CompareLoadingBanner(), ComparePageNav(), CompareSelectionBanner(), CompareSelectionBannerProps, IntegratedLoadingBanner, projectFromCache()

### Community 50 - "compare-sync.ts"
Cohesion: 0.43
Nodes (6): backendUrl(), newComparisonSessionId(), RawQuote, StartCompareJobResult, startMongoCompareJob(), syncMongoUrl()

### Community 51 - "resolve_service_type"
Cohesion: 0.33
Nodes (6): _quote_type_id_map(), Map Tatva quote-type ObjectIds from env → ESSENTIAL / MID_SEGMENT / LUXURY., Resolve quotation type from service_type string and/or quote_type_id ObjectId.…, resolve_service_type(), test_resolve_service_type_aliases(), test_resolve_service_type_returns_none_when_unknown()

### Community 52 - "CompareChat.tsx"
Cohesion: 0.40
Nodes (4): CompareChat(), Message, Props, SUGGESTIONS

### Community 53 - "User flows"
Cohesion: 0.40
Nodes (5): Auth, Compare lanes (`compare-lane.ts`), Market rates, Project → compare → insights, User flows

### Community 54 - "Deployment"
Cohesion: 0.40
Nodes (5): Backend (Render), Database, Deployment, Frontend (Vercel), Manual QA helpers

### Community 55 - "Database (Supabase) reference"
Cohesion: 0.40
Nodes (5): Database (Supabase) reference, Migrations, Seed, `supabase/seed.sql`, Tables (product roles)

### Community 56 - "Infrastructure & ops file reference"
Cohesion: 0.50
Nodes (4): GitHub Actions, Infrastructure & ops file reference, Other root / tooling, Root scripts

### Community 61 - "Backend API reference"
Cohesion: 0.67
Nodes (3): Backend API reference, Example: health, Example: PDF compare

### Community 62 - "Environment configuration"
Cohesion: 0.67
Nodes (3): Backend — `backend/.env` (from `.env.example`), Environment configuration, Frontend — `frontend/.env.local` (from `.env.example`)

### Community 63 - "Frontend routes & BFF"
Cohesion: 0.67
Nodes (3): BFF (`app/api`), Frontend routes & BFF, Pages

## Knowledge Gaps
- **264 isolated node(s):** `run_dev.sh script`, `PYTHONUNBUFFERED`, `run_tests.sh script`, `start_backend.sh script`, `PYTHONUNBUFFERED` (+259 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `downloadComparisonPdf()` connect `download-comparison-pdf.ts` to `dependencies`, `compare/page.tsx`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `jspdf` connect `dependencies` to `download-comparison-pdf.ts`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **What connects `run_dev.sh script`, `PYTHONUNBUFFERED`, `run_tests.sh script` to the rest of the system?**
  _264 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `comparator.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12 - nodes in this community are weakly interconnected._
- **Should `auth.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.05387861084063616 - nodes in this community are weakly interconnected._
- **Should `tatva_catalog.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0650103519668737 - nodes in this community are weakly interconnected._
- **Should `project-mappers.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.052277227722772275 - nodes in this community are weakly interconnected._