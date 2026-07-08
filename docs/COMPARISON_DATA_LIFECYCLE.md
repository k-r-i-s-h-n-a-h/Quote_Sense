# Comparison data lifecycle

## Tables

| Table | Purpose | Retention |
|-------|---------|-----------|
| `quotes` + `quote_items` | Staging for compare/chat | Deleted after merge + 7 days |
| `market_moving_averages` | Yash market-rate API | Permanent |
| `market_moving_avg_sessions` | Dedup per compare session | Trimmed with quotes |

## Flow

1. User compares quotes → rows in `quotes` / `quote_items`
2. Compare completes → `finalize_session_market_rates()` merges rates into `market_moving_averages`
3. Same step sets `quotes.market_rates_applied_at = now()`
4. Daily GitHub Action runs `cleanup_comparison_sessions.py --days 7`
5. Only rows with `market_rates_applied_at` older than 7 days are deleted

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
