# Graph Report - /Users/krishnahonnikhere/Desktop/tatvaops-quotesense  (2026-07-31)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 720 nodes · 1529 edges · 39 communities (32 shown, 7 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.77)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3854e7d0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- market_rate.py
- ProjectHub.tsx
- auth.tsx
- tatva_catalog.py
- project-mappers.ts
- scripts
- tatva-api.ts
- compilerOptions
- extractor.py
- format.ts
- _require_service_type
- tatva_services.py
- recommend_rate
- compare/page.tsx
- main.py
- get
- MarketRatePanel.tsx
- download-comparison-pdf.ts
- _ingest_quotes_to_supabase
- TatvaEcosystemMenu.tsx
- PdfUploadGateButton.tsx
- tatva_fetch.py
- resolve_sub_services
- CompareLoadingPanel.tsx
- compare-matrix.ts
- compare-progress.ts
- dev.sh
- _run_compare_pipeline
- market_rate_by_category
- market-rate-embed.js
- backend/run_dev.sh
- eslint.config.mjs
- next.config.ts
- postcss.config.mjs
- frontend/run_dev.sh
- start-local.sh

## God Nodes (most connected - your core abstractions)
1. `get_supabase_client()` - 25 edges
2. `useAuth()` - 23 edges
3. `QuoteSenseContent()` - 20 edges
4. `getAuthUserId()` - 19 edges
5. `fetch_pricing_methods_from_tatva()` - 16 edges
6. `fetch_sub_services_from_tatva()` - 16 edges
7. `compilerOptions` - 16 edges
8. `normalize_service_type()` - 15 edges
9. `_ensure_maps_loaded()` - 14 edges
10. `downloadComparisonPdf()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `_resolve_lookup_category()` --indirect_call--> `resolve_service_by_id()`  [INFERRED]
  backend/main.py → backend/services/tatva_services.py
- `market_rate_by_category()` --indirect_call--> `list_market_rates_by_category()`  [INFERRED]
  backend/main.py → backend/services/market_rate.py
- `market_rate_by_category()` --indirect_call--> `resolve_service_by_id()`  [INFERRED]
  backend/main.py → backend/services/tatva_services.py
- `market_rate_suggest_post()` --indirect_call--> `recommend_rate()`  [INFERRED]
  backend/main.py → backend/services/market_rate.py
- `market_rate_recommend()` --indirect_call--> `recommend_rate()`  [INFERRED]
  backend/main.py → backend/services/market_rate.py

## Import Cycles
- None detected.

## Communities (39 total, 7 thin omitted)

### Community 0 - "market_rate.py"
Cohesion: 0.06
Nodes (74): aggregate(), fetch_all_quote_items(), main(), cleanup(), _cutoff_iso(), _fetch_stale_quote_ids(), main(), _agent_debug_log() (+66 more)

### Community 1 - "ProjectHub.tsx"
Cohesion: 0.06
Nodes (64): ProjectTile(), ProjectTileProps, STATUS_STYLE, CompareActionBar(), CompareActionBarProps, CompareLoadingBanner(), ComparePageNav(), CompareSelectionBanner() (+56 more)

### Community 2 - "auth.tsx"
Cohesion: 0.05
Nodes (52): metadata, cleanReturnTo(), LoginContent(), safeReturnTo(), HomeContent(), ProjectDashboard, ProjectDetailContent(), RegisterPage() (+44 more)

### Community 3 - "tatva_catalog.py"
Cohesion: 0.08
Nodes (52): _admin_auth_headers(), apply_catalog_maps(), _cache_fresh(), _catalog_auth_missing_message(), _ensure_maps_loaded(), _entry_name_and_id(), fetch_pricing_methods_from_tatva(), fetch_sub_services_from_tatva() (+44 more)

### Community 4 - "project-mappers.ts"
Cohesion: 0.12
Nodes (43): cacheProjectQuotePayloads(), authHeaders(), FetchProjectDetailResult, FetchProjectsResult, fetchProjectWithQuotes(), fetchUserProjects(), isPublicProjectRef(), parseJson() (+35 more)

### Community 5 - "scripts"
Cohesion: 0.05
Nodes (43): eslint, eslint-config-next, dependencies, jspdf, jspdf-autotable, next, react, react-dom (+35 more)

### Community 6 - "tatva-api.ts"
Cohesion: 0.09
Nodes (21): backendBase(), GET(), RouteContext, syncMarketRateCatalog(), findList(), GET(), idsOf(), JsonRecord (+13 more)

### Community 7 - "compilerOptions"
Cohesion: 0.07
Nodes (28): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+20 more)

### Community 8 - "extractor.py"
Cohesion: 0.12
Nodes (22): ExtractedQuote, MainService, BaseModel, WorkItem, _cache_ttl(), _explicit_cache_enabled(), get_extraction_cached_content_name(), invalidate_extraction_cache() (+14 more)

### Community 9 - "format.ts"
Cohesion: 0.18
Nodes (19): ChartPoint, ChartRow, makeTick(), VendorChart(), BAR_COLORS, Row, Stat, VendorInsights() (+11 more)

### Community 10 - "_require_service_type"
Cohesion: 0.15
Nodes (16): chat_with_data(), ChatRequest, market_rate_recommend(), market_rate_suggest_post(), MarketRateRequest, MarketRateSuggestRequest, _missing_service_type_error(), BaseModel (+8 more)

### Community 11 - "tatva_services.py"
Cohesion: 0.21
Nodes (15): _fetch_services_from_api(), _get_services_cached(), _load_static_service_map(), _normalize_service_name(), SSLContext, Resolve Tatva PM service ObjectIds to service category names., Map Tatva PM service ObjectId → service_category name used in…, Strip zero-width chars Tatva sometimes prefixes on service names. (+7 more)

### Community 12 - "recommend_rate"
Cohesion: 0.15
Nodes (15): market_rate_lookup(), market_rate_suggest_get(), Resolve main-service category name for suggest/lookup/recommend. New PM…, Resolve labels from ObjectIds and/or names. Returns (sub, pm, error)., Return market rate when exact bundle exists; otherwise recommend=false., Unified vendor-form endpoint (GET) — single exact-bundle match, no bulk scan.…, _resolve_lookup_category(), _resolve_work_item_labels() (+7 more)

### Community 13 - "compare/page.tsx"
Cohesion: 0.23
Nodes (12): isErrorReport(), isStaleSessionMessage(), QuoteSenseContent(), VendorChart, RecommendationView(), renderInline(), getCompareLane(), showPdfUpload() (+4 more)

### Community 14 - "main.py"
Cohesion: 0.15
Nodes (13): _agent_debug_log(), get_existing_comparison(), health(), _probe_supabase_tables(), Used by the 'Auto-Lane' to fetch results for a session that was already…, # NOTE: this lives in the process, so it assumes a single uvicorn worker (the, Sync Supabase probes — must never run on the event loop without a timeout., Log env status immediately; probe Supabase in the background with a timeout.… (+5 more)

### Community 15 - "get"
Cohesion: 0.22
Nodes (14): get_progress(), market_rate_sync_catalog(), _parse_quotes_payload(), Any, _quote_ids_from_payload(), Poll endpoint for the async compare pipeline. ``has_partial`` lets the frontend…, Normalize Tatva/MongoDB quote payloads to a list of quote dicts., Background worker: compare in-memory from payloads, persist to Supabase after. (+6 more)

### Community 16 - "MarketRatePanel.tsx"
Cohesion: 0.25
Nodes (10): PRICING_METHODS, SAMPLE_ITEMS, MarketRatePanel(), MarketRatePanelProps, backendBase(), lookupMarketRate(), MarketRateLookup, MarketRateParams (+2 more)

### Community 17 - "download-comparison-pdf.ts"
Cohesion: 0.23
Nodes (13): buildColumnStyles(), downloadComparisonPdf(), formatPdfAmount(), formatPdfPrice(), loadLogoForPdf(), pdfLayout(), SUB_AVG_FILL, SUB_GAP_FILL (+5 more)

### Community 18 - "_ingest_quotes_to_supabase"
Cohesion: 0.15
Nodes (13): _format_quote_date(), _ingest_quotes_to_supabase(), _mongodb_quote_metadata(), _quote_line_item(), Push quote headers + line items to Supabase. Returns quotes ingested., Normalize Tatva quoteDate (ISO) to DD/MM/YYYY like PDF extraction., Accept raw quote objects or Tatva API envelopes { data: {...} }., Map TatvaOps MongoDB quote fields to Supabase quotes columns. (+5 more)

### Community 19 - "TatvaEcosystemMenu.tsx"
Cohesion: 0.29
Nodes (7): TatvaEcosystemMenu(), CURRENT_APP_ID, CURRENT_APP_LABEL, envUrl(), getTatvaEcosystemApps(), TatvaApp, TatvaAppId

### Community 20 - "PdfUploadGateButton.tsx"
Cohesion: 0.27
Nodes (5): PdfUploadGateButtonProps, StandalonePdfCompareGuard(), CompareLane, STANDALONE_PDF_RECOVERY_MESSAGE, STANDALONE_PDF_UPLOAD_ENABLED

### Community 21 - "tatva_fetch.py"
Cohesion: 0.36
Nodes (7): _unwrap_quote_payload(), fetch_project_quotes(), filter_quotes_by_ids(), Fetch Tatva PM vendor quotes server-side (MongoDB lane + project_id)., GET vendor quotes for a Tatva project (Mongo _id)., _tatva_api_base(), _unwrap_quotes_list()

### Community 22 - "resolve_sub_services"
Cohesion: 0.32
Nodes (6): is_known_sub_service(), normalize_label(), PM Interiors sub-service catalog + spreadsheet alias map. Lookup is case-…, Trim and collapse internal whitespace., Map a free-text sub_service to exact PM catalog name(s). Matching order: 1)…, resolve_sub_services()

### Community 23 - "CompareLoadingPanel.tsx"
Cohesion: 0.38
Nodes (6): CompareLoadingPanel(), CompareProgressStage, formatElapsed(), Props, stepIndex(), STEPS

### Community 24 - "compare-matrix.ts"
Cohesion: 0.33
Nodes (6): CatGroup, CompareTableRow, roundInr(), SubGroup, SubServiceTotals, sumSubServiceRow()

### Community 25 - "compare-progress.ts"
Cohesion: 0.38
Nodes (6): CompareProgressPayload, pollCompareProgress(), PollCompareProgressOptions, PollCompareProgressResult, pollDelayMs(), sleep()

### Community 26 - "dev.sh"
Cohesion: 0.33
Nodes (5): CHOKIDAR_USEPOLLING, _dbg(), dev.sh script, WATCHPACK_POLLING, WATCHPACK_POLLING_INTERVAL

### Community 27 - "_run_compare_pipeline"
Cohesion: 0.40
Nodes (6): handle_customer_upload(), Background worker: extract every PDF in parallel, then compare. Updates the…, Receives PDFs, saves them, and kicks off the extract+compare pipeline in the…, _run_compare_pipeline(), _set_progress(), UploadFile

### Community 28 - "market_rate_by_category"
Cohesion: 0.40
Nodes (6): market_rate_by_category(), _market_rate_by_category_cache_control(), _market_rate_by_category_response(), Bulk market rates for one Main Service. PM contract: service_id → main service…, head, JSONResponse

## Knowledge Gaps
- **127 isolated node(s):** `run_dev.sh script`, `RouteContext`, `JsonRecord`, `LIST_KEYS`, `ListLocation` (+122 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `downloadComparisonPdf()` connect `download-comparison-pdf.ts` to `compare-matrix.ts`, `scripts`, `compare/page.tsx`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `jspdf` connect `scripts` to `download-comparison-pdf.ts`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **What connects `run_dev.sh script`, `RouteContext`, `JsonRecord` to the rest of the system?**
  _127 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `market_rate.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05553923009109609 - nodes in this community are weakly interconnected._
- **Should `ProjectHub.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.060939060939060936 - nodes in this community are weakly interconnected._
- **Should `auth.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.054340396445659606 - nodes in this community are weakly interconnected._
- **Should `tatva_catalog.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08490566037735849 - nodes in this community are weakly interconnected._