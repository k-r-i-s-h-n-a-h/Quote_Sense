-- Market rate recommendations: bundle key + quote_items extensions
-- Run on staging first, then prod when validated.

ALTER TABLE public.market_moving_averages
  ADD COLUMN IF NOT EXISTS pricing_method text,
  ADD COLUMN IF NOT EXISTS rate_moving_average numeric(18, 2),
  ADD COLUMN IF NOT EXISTS service_type text;

UPDATE public.market_moving_averages
SET pricing_method = COALESCE(NULLIF(trim(pricing_method), ''), 'Unit')
WHERE pricing_method IS NULL OR trim(pricing_method) = '';

UPDATE public.market_moving_averages
SET service_type = COALESCE(NULLIF(trim(service_type), ''), 'ESSENTIAL')
WHERE service_type IS NULL OR trim(service_type) = '';

UPDATE public.market_moving_averages
SET rate_moving_average = COALESCE(rate_moving_average, moving_average, 0)
WHERE rate_moving_average IS NULL;

ALTER TABLE public.market_moving_averages
  ALTER COLUMN pricing_method SET DEFAULT 'Unit',
  ALTER COLUMN rate_moving_average SET DEFAULT 0,
  ALTER COLUMN service_type SET DEFAULT 'ESSENTIAL';

ALTER TABLE public.quote_items
  ADD COLUMN IF NOT EXISTS item_name text,
  ADD COLUMN IF NOT EXISTS service_type text DEFAULT 'ESSENTIAL';

CREATE INDEX IF NOT EXISTS idx_quote_items_bundle
  ON public.quote_items (service_type, service_category, sub_service, pricing_method);

-- See 001_market_moving_avg_sessions.sql for session dedup table.
