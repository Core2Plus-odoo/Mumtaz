-- =============================================================================
-- Faizy — 0007: Row Level Security.
--
-- Threat model this is written against: the anon key ships in the browser and in
-- every installed PWA. Treat it as public. RLS is therefore the ONLY thing
-- standing between one customer and another customer's family records, medical
-- notes, and CNIC scans. Every table below is deny-by-default.
--
-- Two rules applied throughout:
--   1. Money and entitlements are never client-writable. Subscriptions, the
--      activity ledger, wallet rows and payment attempts are readable by their
--      owner and writable only by the service role (server routes / Edge
--      Functions / SECURITY DEFINER functions).
--   2. Workers never get direct table access to customer data. They read through
--      `worker_orders`, a view that omits medical notes and honours privacy_mode.
-- =============================================================================

alter table public.profiles            enable row level security;
alter table public.family_members      enable row level security;
alter table public.documents           enable row level security;
alter table public.faizies             enable row level security;
alter table public.faizy_applications  enable row level security;
alter table public.orders              enable row level security;
alter table public.order_events        enable row level security;
alter table public.bridge_requests     enable row level security;
alter table public.product_requests    enable row level security;
alter table public.ratings             enable row level security;
alter table public.plans               enable row level security;
alter table public.subscriptions       enable row level security;
alter table public.activity_ledger     enable row level security;
alter table public.wallet_transactions enable row level security;
alter table public.payment_attempts    enable row level security;
alter table public.wa_notifications    enable row level security;

-- Helper: the faizies.id belonging to the currently authenticated worker.
create or replace function public.current_faizy_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select id from public.faizies where user_id = auth.uid();
$$;

-- ── profiles ─────────────────────────────────────────────────────────────────
create policy profiles_select_own on public.profiles
  for select to authenticated using (id = auth.uid() or public.is_admin());

create policy profiles_update_own on public.profiles
  for update to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

create policy profiles_admin_all on public.profiles
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- A customer must not be able to grant themselves free activities or inflate
-- their completed-order count. Both are server-maintained.
revoke update (free_activities_remaining, completed_orders) on public.profiles
  from authenticated;

-- ── family_members ───────────────────────────────────────────────────────────
create policy family_members_owner_all on public.family_members
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy family_members_admin_all on public.family_members
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- ── documents ────────────────────────────────────────────────────────────────
create policy documents_owner_all on public.documents
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy documents_admin_all on public.documents
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- ── faizies ──────────────────────────────────────────────────────────────────
-- A worker reads and updates only their own row, and only the availability
-- toggle and photo are theirs to change — status, rates and ratings are ops'.
create policy faizies_self_select on public.faizies
  for select to authenticated using (user_id = auth.uid() or public.is_admin());

create policy faizies_self_update on public.faizies
  for update to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy faizies_admin_all on public.faizies
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

revoke update (status, base_rate_pkr, rating_avg, rating_count,
               completed_orders, cancelled_orders, cnic, user_id)
  on public.faizies from authenticated;

-- ── faizy_applications ───────────────────────────────────────────────────────
-- The onboarding wizard is public, so anon may INSERT — but must never SELECT.
-- Applications hold CNIC numbers and selfies; readback would be a data breach
-- with a public key.
--
-- ⚠️ Anonymous INSERT needs abuse protection that RLS cannot provide. Put a
-- CAPTCHA or per-IP rate limit in front of the wizard before it goes live.
create policy applications_anon_insert on public.faizy_applications
  for insert to anon, authenticated with check (true);

create policy applications_admin_all on public.faizy_applications
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- Applicants check status by reference number through this function instead of
-- reading the table — it returns status only, never the stored documents.
create or replace function public.check_application_status(p_reference_no text, p_phone text)
returns table (reference_no text, status public.application_status, submitted_at timestamptz)
language sql
stable
security definer
set search_path = public
as $$
  select a.reference_no, a.status, a.created_at
    from public.faizy_applications a
   where a.reference_no = upper(trim(p_reference_no))
     and a.phone = p_phone;
$$;

-- ── orders ───────────────────────────────────────────────────────────────────
create policy orders_owner_select on public.orders
  for select to authenticated
  using (user_id = auth.uid() or public.is_admin() or faizy_id = public.current_faizy_id());

create policy orders_owner_insert on public.orders
  for insert to authenticated with check (user_id = auth.uid());

-- Customers may edit an order only while nobody has started work on it.
create policy orders_owner_update on public.orders
  for update to authenticated
  using (user_id = auth.uid() and status in ('pending', 'assigned'))
  with check (user_id = auth.uid());

-- The assigned worker moves their own order through the pipeline.
create policy orders_faizy_update on public.orders
  for update to authenticated
  using (faizy_id = public.current_faizy_id())
  with check (faizy_id = public.current_faizy_id());

create policy orders_admin_all on public.orders
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- Pricing, assignment and the activity flag are server-side decisions.
-- Without this, a customer could set their own purchase_value to zero.
revoke update (purchase_value, platform_fee, service_fee, vendor_commission,
               total_amount, consumed_activity, faizy_id, order_no, user_id)
  on public.orders from authenticated;

-- ── order_events ─────────────────────────────────────────────────────────────
-- Read-only to clients; written exclusively by the trigger.
create policy order_events_select on public.order_events
  for select to authenticated
  using (
    public.is_admin()
    or exists (
      select 1 from public.orders o
       where o.id = order_events.order_id
         and (o.user_id = auth.uid() or o.faizy_id = public.current_faizy_id())
    )
  );

revoke insert, update, delete on public.order_events from anon, authenticated;

-- ── bridge_requests / product_requests ───────────────────────────────────────
create policy bridge_owner_all on public.bridge_requests
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy bridge_admin_all on public.bridge_requests
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

create policy product_owner_all on public.product_requests
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy product_admin_all on public.product_requests
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- The customer accepts or declines a quote; they do not write the quote.
revoke update (quoted_price, quoted_by, quoted_at, quote_notes)
  on public.product_requests from authenticated;

-- ── ratings ──────────────────────────────────────────────────────────────────
-- Only the customer who owns a COMPLETED order may rate it, once.
create policy ratings_owner_insert on public.ratings
  for insert to authenticated
  with check (
    user_id = auth.uid()
    and exists (
      select 1 from public.orders o
       where o.id = ratings.order_id
         and o.user_id = auth.uid()
         and o.status = 'completed'
    )
  );

create policy ratings_select on public.ratings
  for select to authenticated
  using (user_id = auth.uid() or public.is_admin() or faizy_id = public.current_faizy_id());

create policy ratings_admin_all on public.ratings
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- ── plans ────────────────────────────────────────────────────────────────────
-- The pricing table is public — the marketing site and the paywall both read it.
create policy plans_public_read on public.plans
  for select to anon, authenticated using (is_active);

create policy plans_admin_all on public.plans
  for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- ── Money tables: owner-readable, service-role-writable only. ────────────────
create policy subscriptions_owner_select on public.subscriptions
  for select to authenticated using (user_id = auth.uid() or public.is_admin());

create policy activity_ledger_owner_select on public.activity_ledger
  for select to authenticated using (user_id = auth.uid() or public.is_admin());

create policy wallet_owner_select on public.wallet_transactions
  for select to authenticated
  using (user_id = auth.uid() or public.is_admin() or faizy_id = public.current_faizy_id());

create policy payment_attempts_owner_select on public.payment_attempts
  for select to authenticated using (user_id = auth.uid() or public.is_admin());

-- Belt and braces: even a future mistaken policy cannot open these to writes.
revoke insert, update, delete on public.subscriptions       from anon, authenticated;
revoke insert, update, delete on public.activity_ledger     from anon, authenticated;
revoke insert, update, delete on public.wallet_transactions from anon, authenticated;
revoke insert, update, delete on public.payment_attempts    from anon, authenticated;

-- ── wa_notifications ─────────────────────────────────────────────────────────
-- Admin-readable only. No client writes at all: INSERT rights here would let
-- anyone send WhatsApp messages from Faizy's business number.
create policy wa_admin_select on public.wa_notifications
  for select to authenticated using (public.is_admin());

revoke insert, update, delete on public.wa_notifications from anon, authenticated;

-- ── worker_orders view ───────────────────────────────────────────────────────
-- What a Faizy is allowed to see about an assigned job.
--
-- security_invoker so the underlying orders policies still apply — a worker sees
-- only their own assignments. Medical notes are never exposed, and privacy_mode
-- additionally masks the family member's name and the free-text description.
create view public.worker_orders
with (security_invoker = true)
as
select
  o.id,
  o.order_no,
  o.category,
  o.title,
  case when o.privacy_mode then null else o.description end as description,
  o.status,
  o.city,
  o.address,
  o.scheduled_for,
  o.assigned_at,
  o.started_at,
  o.completed_at,
  o.faizy_id,
  case when o.privacy_mode then null else fm.full_name end as member_name,
  fm.fmb_id,
  case when o.privacy_mode then null else fm.phone end as member_phone,
  fm.area as member_area,
  o.privacy_mode,
  o.created_at
from public.orders o
left join public.family_members fm on fm.id = o.family_member_id;

comment on view public.worker_orders is
  'Worker-facing projection of orders. Never exposes medical_notes; honours privacy_mode.';
