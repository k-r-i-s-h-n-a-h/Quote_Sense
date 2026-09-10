-- Vendor email captured from Tatva vendorDetail or a printed quote header.
-- Quote-level: one vendor contact address per quote.
ALTER TABLE public.quotes
  ADD COLUMN IF NOT EXISTS vendor_email text;

COMMENT ON COLUMN public.quotes.vendor_email IS
  'Vendor email stored on the quote. Empty when the source payload has none.';
