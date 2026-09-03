# Comparison data lifecycle

## Tables

| Table | Purpose | Retention |
|-------|---------|-----------|
| `quotes` + `quote_items` | Staging for compare/chat | Deleted after compare session marks applied + 7 days |
| `market_moving_averages` | Yash market-rate API | Permanent |
| `market_moving_avg_sessions` | Dedup (incl. `finalize:<quoteNumber>`) | Trimmed with quotes |

## Product rules

1. User selects **2 quotes among N** for a compare session — only those payloads run comparison / extraction for that session.
2. Compare is **display-only** for market averages: session rates do **not** update `market_moving_averages`.
3. When the user marks **one quote as finalized** (`isFinalizeQuote` / `isFinalizedQuote` / `finalizeQuote`), **only that** payload’s line rates merge into `market_moving_averages`: existing bundles blend; a new combo **inserts one row for that quote's tier** when the line has Tatva `sub_service_id` + `pricing_method_id`. Sibling tiers are not pre-created.

## Flow

1. User picks quotes in Project hub → compare session (session-selected quotes only).
2. Compare completes → optional Supabase staging of those session quotes + `finalize_session_market_rates()` sets `quotes.market_rates_applied_at` for **cleanup only** (no MA write).
3. Finalized quote path:
   - `POST /api/market-rate/apply-finalized` with Tatva quote payload(s), and/or
   - Project load (`fetchProjectWithQuotes`) background-applies any cached payloads with the finalize flag, and/or
   - Compare mongo pipeline runs `apply_finalized_quotes_to_market_rates` on the session list **only if** a payload already has the finalize flag (e.g. user finalizes then re-loads project).
4. MA apply is idempotent via session id `finalize:<quoteNumber>` in `market_moving_avg_sessions`.
5. Daily GitHub Action runs `cleanup_comparison_sessions.py --days 7` on rows with `market_rates_applied_at` set.

## Gate

`MARKET_RATE_UPDATES_ENABLED=false` freezes MA writes (finalized apply becomes no-op). Compare still works.

## Do not run cleanup DELETE before backend deploy

The scheduled SQL only affects quotes where `market_rates_applied_at IS NOT NULL`.
Until the backend hook is live, that column is empty → cleanup deletes nothing.

## Manual commands

```bash
cd backend
venv/bin/python scripts/cleanup_comparison_sessions.py --dry-run --days 7
venv/bin/python scripts/cleanup_comparison_sessions.py --days 7
```

## GitHub Actions setup

Add repository secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Workflow: `.github/workflows/cleanup_comparison_sessions.yml` (daily + manual dispatch).

## Migration

Run on staging/prod if not already applied:

`supabase/migrations/004_quotes_market_rates_applied.sql`
