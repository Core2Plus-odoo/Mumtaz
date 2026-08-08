-- =============================================================================
-- Faizy — 0005: plans, subscriptions, the activity ledger, wallet, payments.
--
-- ⚠️ OPEN QUESTIONS — see docs/00-decisions.md §3 and §9. Two numbers the brief
-- did not specify are seeded as placeholders and MUST be confirmed before
-- billing goes live:
--   * activities_included per tier (brief says "N activities", never states N)
--   * overage price per activity
-- Both are single-row updates to public.plans, not a schema change.
-- =============================================================================

-- ── plans ────────────────────────────────────────────────────────────────────
create table public.plans (
  code                public.plan_code primary key,
  name                text not null,
  -- Prices are stored in minor units to keep gateway reconciliation exact:
  -- AED 26.50 -> 2650 fils. Display formatting happens in the app.
  price_minor         integer not null,
  currency            text not null default 'AED',
  activities_included integer not null,
  overage_price_minor integer not null,
  features            jsonb not null default '[]'::jsonb,
  is_active           boolean not null default true,
  sort_order          integer not null default 0,
  -- Gateway price ID (Stripe price_xxx or equivalent). Null until billing is wired.
  gateway_price_id    text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),

  constraint plans_price_non_negative check (price_minor >= 0),
  constraint plans_activities_positive check (activities_included > 0)
);

create trigger plans_touch before update on public.plans
  for each row execute function public.touch_updated_at();

-- ── subscriptions ────────────────────────────────────────────────────────────
create table public.subscriptions (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references public.profiles(id) on delete cascade,
  plan_code             public.plan_code not null references public.plans(code),
  status                public.subscription_status not null default 'trialing',

  current_period_start  timestamptz not null default now(),
  current_period_end    timestamptz not null default (now() + interval '1 month'),
  -- Reset to the plan's allowance at each period rollover. Kept denormalised so
  -- the paywall check is a single indexed read, not an aggregate over the ledger.
  activities_used       integer not null default 0,
  activities_included   integer not null,

  cancel_at_period_end  boolean not null default false,
  cancelled_at          timestamptz,

  gateway_customer_id     text,
  gateway_subscription_id text,

  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),

  constraint subscriptions_used_non_negative check (activities_used >= 0),
  constraint subscriptions_period_ordered check (current_period_end > current_period_start)
);

-- A user has at most one live subscription. Cancelled history is retained.
create unique index subscriptions_one_live_per_user
  on public.subscriptions (user_id)
  where status in ('trialing', 'active', 'past_due', 'paused');

create index subscriptions_user_idx on public.subscriptions (user_id, created_at desc);
create index subscriptions_period_end_idx on public.subscriptions (current_period_end)
  where status in ('trialing', 'active');
create index subscriptions_gateway_idx on public.subscriptions (gateway_subscription_id)
  where gateway_subscription_id is not null;

create trigger subscriptions_touch before update on public.subscriptions
  for each row execute function public.touch_updated_at();

-- ── free activity grant ──────────────────────────────────────────────────────
-- Three free activities at signup, then a hard paywall.
-- Held on the profile rather than the subscription because it is granted before
-- any subscription exists.
--
-- DEFAULTED ASSUMPTION (docs/00-decisions.md §9): free activities do NOT expire
-- and are consumed before any paid allowance. Say the word and it becomes a
-- windowed grant instead.
alter table public.profiles
  add column free_activities_remaining integer not null default 3
  constraint profiles_free_activities_non_negative check (free_activities_remaining >= 0);

-- ── activity_ledger ──────────────────────────────────────────────────────────
-- Append-only. Every consumed activity, and which bucket paid for it. This is
-- the audit trail behind every invoice line — never UPDATE or DELETE these rows.
create table public.activity_ledger (
  id              bigserial primary key,
  user_id         uuid not null references public.profiles(id) on delete cascade,
  order_id        uuid references public.orders(id) on delete set null,
  subscription_id uuid references public.subscriptions(id) on delete set null,
  -- 'free' | 'included' | 'overage'
  source          text not null,
  -- Charge for this activity in minor units. Zero for free/included.
  amount_minor    integer not null default 0,
  currency        text not null default 'AED',
  note            text,
  created_at      timestamptz not null default now(),

  constraint activity_ledger_source_valid check (source in ('free', 'included', 'overage')),
  constraint activity_ledger_amount_non_negative check (amount_minor >= 0)
);

create index activity_ledger_user_idx on public.activity_ledger (user_id, created_at desc);
create index activity_ledger_order_idx on public.activity_ledger (order_id);
create index activity_ledger_sub_period_idx on public.activity_ledger (subscription_id, created_at);

-- ── consume_activity ─────────────────────────────────────────────────────────
-- The paywall. Called server-side when an order is confirmed.
--
-- SECURITY DEFINER and never exposed to the client for direct arbitrary use:
-- if a customer could call this with their own arguments, or worse, write
-- activities_used themselves, they would bill themselves nothing forever.
--
-- Order of consumption: free grant → included allowance → overage.
-- Row-locks the subscription so two concurrent bookings cannot both spend the
-- last remaining activity.
create or replace function public.consume_activity(p_order_id uuid)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid;
  v_sub     public.subscriptions;
  v_plan    public.plans;
  v_free    integer;
  v_source  text;
  v_amount  integer := 0;
begin
  select user_id into v_user_id from public.orders where id = p_order_id;
  if v_user_id is null then
    raise exception 'order % not found', p_order_id using errcode = 'P0002';
  end if;

  if exists (select 1 from public.activity_ledger where order_id = p_order_id) then
    return 'already_counted';   -- idempotent: safe to retry
  end if;

  -- Lock the profile row for the free-grant decrement.
  select free_activities_remaining into v_free
    from public.profiles where id = v_user_id for update;

  if v_free > 0 then
    update public.profiles
       set free_activities_remaining = free_activities_remaining - 1
     where id = v_user_id;
    v_source := 'free';
  else
    select * into v_sub
      from public.subscriptions
     where user_id = v_user_id
       and status in ('trialing', 'active', 'past_due')
     order by created_at desc
     limit 1
     for update;

    if not found then
      -- Hard paywall: no free activities, no subscription.
      raise exception 'no_active_subscription' using errcode = 'P0001';
    end if;

    select * into v_plan from public.plans where code = v_sub.plan_code;

    if v_sub.activities_used < v_sub.activities_included then
      v_source := 'included';
    else
      v_source := 'overage';
      v_amount := v_plan.overage_price_minor;
    end if;

    update public.subscriptions
       set activities_used = activities_used + 1
     where id = v_sub.id;
  end if;

  insert into public.activity_ledger
    (user_id, order_id, subscription_id, source, amount_minor)
  values (v_user_id, p_order_id, v_sub.id, v_source, v_amount);

  update public.orders set consumed_activity = true where id = p_order_id;

  return v_source;
end;
$$;

revoke all on function public.consume_activity(uuid) from public, anon, authenticated;

-- ── wallet_transactions ──────────────────────────────────────────────────────
-- Append-only ledger. Balance is derived by summing, never stored — a stored
-- balance and a ledger will eventually disagree, and then you cannot tell which
-- one lied. This is also the table that makes a future accounting export (Odoo,
-- Zoho) a mapping exercise rather than an archaeology project.
create table public.wallet_transactions (
  id            bigserial primary key,
  user_id       uuid references public.profiles(id) on delete cascade,
  -- Worker payouts reference a Faizy instead of a customer. Exactly one is set.
  faizy_id      uuid references public.faizies(id) on delete cascade,
  order_id      uuid references public.orders(id) on delete set null,
  txn_type      public.wallet_txn_type not null,
  -- Signed minor units: credits positive, debits negative. Sign is enforced
  -- against txn_type below so a "debit" can never sneak in as a credit.
  amount_minor  integer not null,
  currency      text not null default 'AED',
  balance_note  text,
  reference     text,
  created_at    timestamptz not null default now(),

  constraint wallet_txn_one_party check (
    (user_id is not null and faizy_id is null) or
    (user_id is null and faizy_id is not null)
  ),
  constraint wallet_txn_sign_matches_type check (
    (txn_type in ('topup', 'refund') and amount_minor > 0) or
    (txn_type in ('debit', 'payout') and amount_minor < 0) or
    (txn_type = 'adjustment')
  )
);

create index wallet_txn_user_idx on public.wallet_transactions (user_id, created_at desc)
  where user_id is not null;
create index wallet_txn_faizy_idx on public.wallet_transactions (faizy_id, created_at desc)
  where faizy_id is not null;
create index wallet_txn_order_idx on public.wallet_transactions (order_id);

create or replace function public.wallet_balance_minor(p_user_id uuid)
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(sum(amount_minor), 0)::integer
    from public.wallet_transactions
   where user_id = p_user_id;
$$;

-- ── payment_attempts ─────────────────────────────────────────────────────────
-- Every charge attempt, successful or not. Deliberately records the DECLINE
-- CODE: the decision on whether to add a local Saudi rail (mada) rests on
-- seeing decline patterns in real data, and that evidence has to exist before
-- the question gets asked. See docs/00-decisions.md §3.
create table public.payment_attempts (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.profiles(id) on delete cascade,
  subscription_id uuid references public.subscriptions(id) on delete set null,
  order_id        uuid references public.orders(id) on delete set null,
  provider        text not null,                       -- 'stripe' | 'tap' | 'paytabs'
  provider_ref    text,
  amount_minor    integer not null,
  currency        text not null default 'AED',
  status          public.payment_status not null,
  decline_code    text,
  error_message   text,
  card_country    text,
  card_brand      text,
  created_at      timestamptz not null default now()
);

create index payment_attempts_user_idx on public.payment_attempts (user_id, created_at desc);
create index payment_attempts_status_idx on public.payment_attempts (status, created_at desc);
create index payment_attempts_declines_idx on public.payment_attempts (decline_code, card_country)
  where status = 'failed';
