-- Track when session rates were merged into market_moving_averages (cleanup gate).
ALTER TABLE public.quotes
  ADD COLUMN IF NOT EXISTS market_rates_applied_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_quotes_rates_applied_cleanup
  ON public.quotes (market_rates_applied_at)
  WHERE market_rates_applied_at IS NOT NULL;
