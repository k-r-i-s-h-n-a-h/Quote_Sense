-- Unique bundle key so finalize inserts cannot duplicate a combo.
-- Key: service_type + service_category + sub_service + pricing_method.
-- Keep the higher-weight duplicate if any exist.

DELETE FROM public.market_moving_averages
WHERE id IN (
  SELECT id FROM (
    SELECT id,
           ROW_NUMBER() OVER (
             PARTITION BY service_type, service_category, sub_service, pricing_method
             ORDER BY COALESCE(weight, 0) DESC, id
           ) AS rn
    FROM public.market_moving_averages
  ) ranked
  WHERE rn > 1
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_market_moving_averages_bundle
  ON public.market_moving_averages (
    service_type,
    service_category,
    sub_service,
    pricing_method
  );
