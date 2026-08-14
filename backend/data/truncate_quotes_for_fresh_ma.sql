-- Fresh-start wipe for QuoteSense compare / MA testing (staging).
-- Run in Supabase SQL editor AFTER freezing MA writes:
--   MARKET_RATE_UPDATES_ENABLED=false
--
-- Order: children first (quote_items → quotes), then MA session dedup.
-- Does NOT truncate market_moving_averages — reseed that separately with
--   seed_market_moving_averages_full_weight1.sql
--
-- After this + MA reseed, re-enable updates only once seed-match-only code is deployed.

BEGIN;

-- Compare / sync staging rows
TRUNCATE TABLE public.quote_items RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.quotes RESTART IDENTITY CASCADE;

-- Dedup ledger for finalize:/session MA applies (safe to clear on reset)
TRUNCATE TABLE public.market_moving_avg_sessions RESTART IDENTITY CASCADE;

COMMIT;

-- Optional verification:
-- SELECT count(*) FROM public.quotes;
-- SELECT count(*) FROM public.quote_items;
-- SELECT count(*) FROM public.market_moving_avg_sessions;
-- SELECT count(*) FROM public.market_moving_averages;  -- should stay until you reseed
