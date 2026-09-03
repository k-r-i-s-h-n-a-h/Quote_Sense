-- Seed weight must be 1, never 0.
-- weight=0 makes the first finalize ignore the seed rate:
--   (seed * 0 + vendor * 1) / 1 = vendor only.
-- weight=1 keeps the seed as the first observation so the next
-- finalize blends: (seed * 1 + vendor * 1) / 2.
-- Do not use NULL: column weight is NOT NULL.

UPDATE public.market_moving_averages
SET weight = 1
WHERE weight = 0;
