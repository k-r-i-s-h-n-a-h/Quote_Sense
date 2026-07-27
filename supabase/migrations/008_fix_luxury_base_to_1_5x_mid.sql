-- Correct LUXURY base rates: Mid * 1.5 (was seeded as Mid * 2.5 from older sheet).
BEGIN;

UPDATE public.market_moving_averages AS lux
SET
  rate_moving_average = round(mid.rate_moving_average * 1.5, 2),
  moving_average = round(mid.rate_moving_average * 1.5, 2),
  updated_at = now()
FROM public.market_moving_averages AS mid
WHERE lux.service_type = 'LUXURY'
  AND mid.service_type = 'MID_SEGMENT'
  AND lux.service_category = mid.service_category
  AND lux.sub_service = mid.sub_service
  AND lux.pricing_method = mid.pricing_method;

COMMIT;
