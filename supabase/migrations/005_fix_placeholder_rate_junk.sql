-- Fix "₹1" market rate rows caused by vendors leaving Rate = 1 as a form
-- placeholder on "On Actuals" / "Per Project" line items (the real total was
-- in Amount, not Rate). The backend now derives Amount / Quantity for those
-- pricing methods instead of trusting the placeholder Rate (see
-- services/market_rate.py: resolve_effective_rate / MIN_VALID_RATE).
--
-- This migration only needs to run ONCE against existing polluted data.
-- After it runs, re-seed those bundles correctly with:
--   cd backend && venv/bin/python scripts/backfill_market_rates.py
--
-- Safe to re-run.

-- 1) Preview which bundles are affected (junk = rate_moving_average <= 1).
SELECT service_type, service_category, sub_service, pricing_method, rate_moving_average, weight
FROM public.market_moving_averages
WHERE rate_moving_average <= 1
ORDER BY service_category, sub_service;

-- 2) Delete the junk rows. They will be correctly re-derived (from
--    Amount / Quantity) next time a session runs through the comparator,
--    or immediately if you re-run the backfill script above.
DELETE FROM public.market_moving_averages
WHERE rate_moving_average <= 1;
