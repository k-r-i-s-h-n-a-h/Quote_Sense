-- Remove the old math-derived Mid-segment/Luxury rows (Essential × 1.35 / × 1.75)
-- inserted by migration 003_market_rate_tier_multipliers.sql.
--
-- Why: real vendor quotes on the Tatva platform now carry an explicit quoteType
-- (essential / midlevel / luxury). The backend ingestion pipeline writes each
-- quote's real rates directly into market_moving_averages under its own
-- service_type instead of guessing Mid-segment/Luxury via a fixed multiplier.
-- Keeping the synthetic rows around would let fake data mix with (and dilute)
-- real submitted rates once genuine Mid-segment/Luxury quotes start flowing in.
--
-- Run in Supabase SQL editor (staging first, then prod). Safe to re-run.

-- 1) Preview what will be deleted.
SELECT service_type, service_category, sub_service, pricing_method, rate_moving_average, weight
FROM public.market_moving_averages
WHERE COALESCE(last_session_id, '') LIKE 'TIER_MULTIPLIER_%'
ORDER BY service_type, service_category, sub_service;

-- 2) Delete the synthetic rows. Real Essential rows (and any real Mid-segment/
--    Luxury rows already ingested from actual quotes) are untouched.
DELETE FROM public.market_moving_averages
WHERE COALESCE(last_session_id, '') LIKE 'TIER_MULTIPLIER_%';

-- 3) Verify — Mid-segment/Luxury counts should now reflect only real ingested
--    quotes (likely 0 until vendors submit quotes of those types).
-- SELECT service_type, COUNT(*) FROM public.market_moving_averages GROUP BY 1 ORDER BY 1;
