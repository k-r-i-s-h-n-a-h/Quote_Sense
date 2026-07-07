-- Derive Mid-segment and Luxury market rates from Essential rows (generic tier data).
-- Run in Supabase SQL editor (staging first, then prod).
--
-- Multipliers:
--   MID_SEGMENT = ESSENTIAL × 1.35
--   LUXURY      = ESSENTIAL × 1.75
--
-- Safe to re-run: removes prior derived rows before insert.

DELETE FROM public.market_moving_averages
WHERE service_type IN ('MID_SEGMENT', 'LUXURY')
  AND COALESCE(last_session_id, '') LIKE 'TIER_MULTIPLIER_%';

INSERT INTO public.market_moving_averages (
  service_type,
  service_category,
  sub_service,
  pricing_method,
  rate_moving_average,
  moving_average,
  weight,
  item_key,
  last_session_id
)
SELECT
  'MID_SEGMENT',
  e.service_category,
  e.sub_service,
  e.pricing_method,
  ROUND(COALESCE(e.rate_moving_average, e.moving_average, 0) * 1.35, 2),
  ROUND(COALESCE(e.rate_moving_average, e.moving_average, 0) * 1.35, 2),
  e.weight,
  e.item_key,
  'TIER_MULTIPLIER_1.35'
FROM public.market_moving_averages e
WHERE e.service_type = 'ESSENTIAL'
  AND COALESCE(e.rate_moving_average, e.moving_average, 0) > 0
  AND COALESCE(e.weight, 0) >= 1;

INSERT INTO public.market_moving_averages (
  service_type,
  service_category,
  sub_service,
  pricing_method,
  rate_moving_average,
  moving_average,
  weight,
  item_key,
  last_session_id
)
SELECT
  'LUXURY',
  e.service_category,
  e.sub_service,
  e.pricing_method,
  ROUND(COALESCE(e.rate_moving_average, e.moving_average, 0) * 1.75, 2),
  ROUND(COALESCE(e.rate_moving_average, e.moving_average, 0) * 1.75, 2),
  e.weight,
  e.item_key,
  'TIER_MULTIPLIER_1.75'
FROM public.market_moving_averages e
WHERE e.service_type = 'ESSENTIAL'
  AND COALESCE(e.rate_moving_average, e.moving_average, 0) > 0
  AND COALESCE(e.weight, 0) >= 1;

-- Verify counts (expect MID_SEGMENT and LUXURY counts = ESSENTIAL count)
-- SELECT service_type, COUNT(*) FROM public.market_moving_averages GROUP BY 1 ORDER BY 1;

-- Sample: Wardrobes / Area (in sqft) across tiers
-- SELECT service_type, service_category, sub_service, pricing_method, rate_moving_average, weight
-- FROM public.market_moving_averages
-- WHERE sub_service = 'Wardrobes' AND pricing_method = 'Area (in sqft)'
-- ORDER BY service_type;
