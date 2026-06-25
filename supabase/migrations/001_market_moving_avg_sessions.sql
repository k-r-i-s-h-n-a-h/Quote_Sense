-- Run once in Supabase SQL editor to stop market_moving_avg_sessions warnings.
CREATE TABLE IF NOT EXISTS public.market_moving_avg_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id text NOT NULL,
    item_id uuid NOT NULL REFERENCES public.market_moving_averages(id) ON DELETE CASCADE,
    batch_avg numeric NOT NULL,
    batch_weight integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (session_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_moving_avg_sessions_session
    ON public.market_moving_avg_sessions (session_id);
