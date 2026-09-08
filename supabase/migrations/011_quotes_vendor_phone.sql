-- Vendor WhatsApp / contact number captured at extract (Tatva vendorDetail or PDF).
-- Quote-level: one number per quote header, not per line item.
ALTER TABLE public.quotes
  ADD COLUMN IF NOT EXISTS vendor_phone text;

COMMENT ON COLUMN public.quotes.vendor_phone IS
  'Vendor contact as stored on the quote (digits, optional leading +). Empty when the payload had none.';
