-- =============================================================================
-- Faizy — 0001: extensions, enums, and shared helper functions.
--
-- NOTE FOR REVIEW (Shafat): the prototype `schema.sql` referenced in the brief
-- was not present in the repo when these migrations were authored, so this set
-- is reconstructed from the written spec. Reconcile against the original on
-- receipt — table and column NAMES especially, since the prototype's
-- supabase-integration.js queries them directly.
--
-- Design rules applied throughout:
--   * Supabase Auth owns identity. public.profiles is a PROFILE table keyed to
--     auth.users(id). There is no second identity store.
--   * Money is numeric(12,2) in a stated currency. Never float.
--   * Every table that a customer can reach is RLS-protected (see 0007).
--   * Anything a customer could profit from forging — activity counts, fees,
--     commission — is computed server-side, never trusted from the client.
-- =============================================================================

create extension if not exists "pgcrypto";      -- gen_random_uuid()
create extension if not exists "pg_trgm";       -- fuzzy search in admin CRM

-- ── Enums ────────────────────────────────────────────────────────────────────

-- Mirrors the admin Kanban columns and the StatusBadge component exactly.
create type public.order_status as enum (
  'pending', 'assigned', 'in_progress', 'completed', 'cancelled'
);

create type public.service_category as enum (
  'groceries', 'medicine', 'doctor_visit', 'documents', 'companionship',
  'gift_delivery', 'emergency', 'product_request', 'other'
);

create type public.user_role as enum ('customer', 'worker', 'admin');

create type public.faizy_status as enum ('applicant', 'active', 'suspended', 'inactive');

create type public.application_status as enum (
  'submitted', 'under_review', 'interview', 'approved', 'rejected'
);

create type public.plan_code as enum ('lite', 'standard', 'family_pro');

create type public.subscription_status as enum (
  'trialing', 'active', 'past_due', 'cancelled', 'paused'
);

create type public.wallet_txn_type as enum (
  'topup', 'debit', 'refund', 'adjustment', 'payout'
);

create type public.wa_message_type as enum (
  'otp', 'booking_confirmation', 'faizy_assigned', 'status_update', 'receipt', 'generic'
);

create type public.wa_status as enum (
  'queued', 'sending', 'sent', 'delivered', 'read', 'failed'
);

create type public.document_type as enum (
  'cnic_front', 'cnic_back', 'selfie', 'passport', 'medical', 'receipt', 'proof_of_delivery', 'other'
);

create type public.payment_status as enum (
  'requires_action', 'processing', 'succeeded', 'failed', 'refunded'
);

-- ── Helper functions ─────────────────────────────────────────────────────────
-- Role lives in the JWT's app_metadata, which only the service role can write —
-- so a customer cannot escalate themselves by editing their own profile row.

create or replace function public.auth_role()
returns public.user_role
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    nullif(auth.jwt() -> 'app_metadata' ->> 'role', ''),
    'customer'
  )::public.user_role;
$$;

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.auth_role() = 'admin';
$$;

-- Keeps updated_at honest without trusting the client to send it.
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ── ID sequences ─────────────────────────────────────────────────────────────
-- Both allocated by the database, never by the client: two offline devices would
-- otherwise cheerfully mint the same ID.

-- Family member IDs: FMB-000001, FMB-000002, ...
create sequence public.fmb_id_seq start 1;

-- Worker application reference numbers: FZY-10000, FZY-10001, ...
-- Starts at 10000 so every reference is a stable 5 digits.
create sequence public.faizy_app_ref_seq start 10000;

-- Human-facing order numbers: FZO-100000, ...
create sequence public.order_no_seq start 100000;
