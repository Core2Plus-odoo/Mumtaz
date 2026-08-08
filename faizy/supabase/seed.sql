-- =============================================================================
-- Faizy — local/dev seed. Run automatically by `supabase db reset`.
--
-- ⚠️ TWO NUMBERS BELOW ARE PLACEHOLDERS AND MUST BE CONFIRMED BEFORE BILLING
-- GOES LIVE (docs/00-decisions.md §3, §9):
--
--   * activities_included — the brief specifies "N activities per month" for
--     each tier but never states N. The values here are guesses scaled to price.
--   * overage_price_minor — never specified at all. AED 10.00 is a placeholder.
--
-- Prices themselves come from the brief and are described there as approximate,
-- so confirm those too. Everything is a one-row UPDATE, not a schema change.
-- =============================================================================

insert into public.plans
  (code, name, price_minor, currency, activities_included, overage_price_minor, sort_order, features)
values
  ('lite', 'Lite', 2650, 'AED', 5, 1000, 1, '[
     "Up to 5 care activities a month",
     "1 family member",
     "WhatsApp booking & updates",
     "Photo proof on every task"
   ]'::jsonb),
  ('standard', 'Standard', 6620, 'AED', 15, 1000, 2, '[
     "Up to 15 care activities a month",
     "Up to 4 family members",
     "Priority assignment",
     "Document vault",
     "Monthly spending report"
   ]'::jsonb),
  ('family_pro', 'Family Pro', 11920, 'AED', 40, 1000, 3, '[
     "Up to 40 care activities a month",
     "Unlimited family members",
     "Priority + emergency response",
     "Dedicated care calendar",
     "Product sourcing requests",
     "Full spending analytics"
   ]'::jsonb)
on conflict (code) do update
  set name                = excluded.name,
      price_minor         = excluded.price_minor,
      activities_included = excluded.activities_included,
      overage_price_minor = excluded.overage_price_minor,
      features            = excluded.features,
      sort_order          = excluded.sort_order;

-- Demo ground network, matching the three cities in the original prototype seed.
insert into public.faizies
  (full_name, phone, cnic, city, areas_covered, services, status, is_available, base_rate_pkr)
values
  ('Ahmed Raza', '+923001234567', '42101-1234567-1', 'Karachi',
   array['Gulshan-e-Iqbal','North Nazimabad','Clifton'],
   array['groceries','medicine','doctor_visit']::public.service_category[],
   'active', true, 1500),
  ('Fatima Bibi', '+923011234568', '35202-2345678-2', 'Lahore',
   array['Model Town','Johar Town','DHA'],
   array['companionship','doctor_visit','documents']::public.service_category[],
   'active', true, 1500),
  ('Usman Khalid', '+923211234569', '61101-3456789-3', 'Islamabad',
   array['F-10','G-11','Bahria Town'],
   array['groceries','documents','gift_delivery','emergency']::public.service_category[],
   'active', true, 1800)
on conflict (phone) do nothing;
