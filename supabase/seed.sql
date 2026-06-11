-- Seed data for the STAGING branch (test data only).
-- Supabase runs this automatically after migrations when the branch is built.
-- All rows share one session_id so you can load them in the app via:
--   /?session_id=seed_demo_0001
--
-- NOTE: the `quote_number` column must exist for this seed to load. If you have
-- not added it to production yet, run this on production BEFORE `supabase db pull`:
--   ALTER TABLE public.quotes ADD COLUMN IF NOT EXISTS quote_number text;

-- Clean any previous seed rows so re-seeding is idempotent.
delete from public.quote_items
where quote_id in (
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222'
);
delete from public.quotes
where id in (
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222'
);

-- ---------------------------------------------------------------------------
-- Quotes
-- ---------------------------------------------------------------------------
insert into public.quotes
  (id, vendor_name, client_name, quote_date, grand_total, source_filename, session_id, quote_number)
values
  ('11111111-1111-1111-1111-111111111111', 'LINEA VITA DESIGN STUDIO', 'Rajiv Kumar Bansal',
   '07/05/2026', 1178042.16, 'Dura Plywood - Linea Vita.pdf', 'seed_demo_0001', 'Q52OW75'),
  ('22222222-2222-2222-2222-222222222222', 'PRIME BUILD & COAT', 'Rajiv Kumar Bansal',
   '08/05/2026', 1024500.00, 'Prime Build Quote.pdf', 'seed_demo_0001', 'PB10042');

-- ---------------------------------------------------------------------------
-- Quote line items
-- ---------------------------------------------------------------------------
insert into public.quote_items
  (quote_id, service_category, sub_service, work_title, description, quantity, pricing_method, rate, amount)
values
  -- Linea Vita
  ('11111111-1111-1111-1111-111111111111', 'Interiors', 'Modular Kitchen', 'Kitchen',
   'L-shaped modular kitchen with soft-close hardware', 1, 'Lump Sum', 245000, 245000),
  ('11111111-1111-1111-1111-111111111111', 'Interiors', 'Wardrobes', 'Master Bedroom',
   '4-door sliding wardrobe, laminate finish', 1, 'Lump Sum', 132000, 132000),
  ('11111111-1111-1111-1111-111111111111', 'Interiors', 'False Ceiling', 'Living Room',
   'Gypsum false ceiling with cove lighting', 320, 'Area (in sqft)', 95, 30400),
  ('11111111-1111-1111-1111-111111111111', 'Electrical Services', 'Lighting Installation', 'Whole Home',
   'Supply and install LED panel and spot lights', 1, 'Lump Sum', 84370, 84370),
  ('11111111-1111-1111-1111-111111111111', 'Painting', 'Interior Painting', 'Whole Home',
   'Premium emulsion, two coats with putty base', 2400, 'Area (in sqft)', 38, 91200),

  -- Prime Build & Coat
  ('22222222-2222-2222-2222-222222222222', 'Interiors', 'Modular Kitchen', 'Kitchen',
   'Straight modular kitchen, membrane shutters', 1, 'Lump Sum', 188000, 188000),
  ('22222222-2222-2222-2222-222222222222', 'Interiors', 'Wardrobes', 'Master Bedroom',
   '3-door hinged wardrobe, laminate finish', 1, 'Lump Sum', 118500, 118500),
  ('22222222-2222-2222-2222-222222222222', 'Electrical Services', 'Lighting Installation', 'Whole Home',
   'Supply and install LED panel lights', 1, 'Lump Sum', 76250, 76250),
  ('22222222-2222-2222-2222-222222222222', 'Painting', 'Interior Painting', 'Whole Home',
   'Standard emulsion, two coats', 2400, 'Area (in sqft)', 32, 76800);
