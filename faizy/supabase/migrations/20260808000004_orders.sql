-- =============================================================================
-- Faizy — 0004: orders, the request types that spawn them, and the audit trail.
-- =============================================================================

-- ── orders ───────────────────────────────────────────────────────────────────
create table public.orders (
  id                uuid primary key default gen_random_uuid(),
  order_no          text not null unique
                    default 'FZO-' || nextval('public.order_no_seq')::text,
  user_id           uuid not null references public.profiles(id) on delete restrict,
  -- Who the errand is FOR. Nullable: some orders serve the household generally.
  family_member_id  uuid references public.family_members(id) on delete set null,
  faizy_id          uuid references public.faizies(id) on delete set null,

  category          public.service_category not null,
  title             text not null,
  description       text,
  city              text not null,
  address           text,

  status            public.order_status not null default 'pending',
  scheduled_for     timestamptz,
  -- Recurring bookings: an RRULE-ish descriptor plus a self-reference to the
  -- template order that generated this occurrence.
  recurrence        jsonb,
  parent_order_id   uuid references public.orders(id) on delete set null,

  -- Privacy toggle from the booking flow: when true the assigned Faizy sees the
  -- task and address but NOT the family member's notes or medical detail.
  privacy_mode      boolean not null default false,

  -- ── Money. All server-computed; see recompute_order_totals() below. ────────
  currency          text not null default 'AED',
  -- What the customer's money actually bought (groceries, medicine, ...).
  purchase_value    numeric(12,2) not null default 0,
  -- 5% of purchase_value, added to the customer invoice.
  platform_fee      numeric(12,2) not null default 0,
  -- Faizy's service charge for running the errand.
  service_fee       numeric(12,2) not null default 0,
  -- 10% of purchase_value, retained from the VENDOR when one fulfils the order.
  -- Revenue to Faizy; NOT charged to the customer.
  vendor_commission numeric(12,2) not null default 0,
  vendor_name       text,
  total_amount      numeric(12,2) not null default 0,
  -- Whether this order consumed one of the subscription's monthly activities.
  consumed_activity boolean not null default false,

  assigned_at       timestamptz,
  started_at        timestamptz,
  completed_at      timestamptz,
  cancelled_at      timestamptz,
  cancellation_reason text,

  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),

  constraint orders_amounts_non_negative check (
    purchase_value >= 0 and platform_fee >= 0 and service_fee >= 0
    and vendor_commission >= 0 and total_amount >= 0
  ),
  -- A non-pending order must name the Faizy responsible for it.
  constraint orders_assigned_has_faizy check (
    status in ('pending', 'cancelled') or faizy_id is not null
  ),
  constraint orders_completed_has_timestamp check (
    status <> 'completed' or completed_at is not null
  )
);

-- Hot paths: the customer's order list, the admin Kanban, the worker's queue.
create index orders_user_idx        on public.orders (user_id, created_at desc);
create index orders_status_idx      on public.orders (status, created_at desc);
create index orders_faizy_idx       on public.orders (faizy_id, status)
  where faizy_id is not null;
create index orders_city_status_idx on public.orders (city, status);
create index orders_member_idx      on public.orders (family_member_id);
create index orders_scheduled_idx   on public.orders (scheduled_for)
  where status in ('pending', 'assigned');

create trigger orders_touch before update on public.orders
  for each row execute function public.touch_updated_at();

-- ── Server-side money. ───────────────────────────────────────────────────────
-- Fees are recomputed from purchase_value on every write. The client sends what
-- was bought; it never sends what it owes. A trigger rather than app code so it
-- holds no matter which surface (customer app, admin, worker) does the write.
--
-- Rounding: half-up to 2dp, applied per component. Documented because 5% and 10%
-- of an odd purchase value will otherwise drift against the customer's receipt.
create or replace function public.recompute_order_totals()
returns trigger
language plpgsql
as $$
begin
  new.platform_fee := round(new.purchase_value * 0.05, 2);

  new.vendor_commission := case
    when new.vendor_name is not null and length(trim(new.vendor_name)) > 0
      then round(new.purchase_value * 0.10, 2)
    else 0
  end;

  -- The customer pays for goods + platform fee + service. Vendor commission is
  -- retained from the vendor's side and is deliberately NOT in this sum.
  new.total_amount := new.purchase_value + new.platform_fee + new.service_fee;
  return new;
end;
$$;

create trigger orders_recompute_totals
  before insert or update of purchase_value, service_fee, vendor_name
  on public.orders
  for each row execute function public.recompute_order_totals();

-- ── Status transitions: stamp timestamps and keep counters honest. ───────────
create or replace function public.handle_order_status_change()
returns trigger
language plpgsql
as $$
begin
  if new.status is distinct from old.status then
    case new.status
      when 'assigned'  then new.assigned_at  := coalesce(new.assigned_at, now());
      when 'in_progress' then new.started_at := coalesce(new.started_at, now());
      when 'completed' then new.completed_at := coalesce(new.completed_at, now());
      when 'cancelled' then new.cancelled_at := coalesce(new.cancelled_at, now());
      else null;
    end case;

    if new.status = 'completed' and old.status <> 'completed' then
      update public.profiles set completed_orders = completed_orders + 1 where id = new.user_id;
      if new.faizy_id is not null then
        update public.faizies set completed_orders = completed_orders + 1 where id = new.faizy_id;
      end if;
    end if;

    if new.status = 'cancelled' and old.status <> 'cancelled' and new.faizy_id is not null then
      update public.faizies set cancelled_orders = cancelled_orders + 1 where id = new.faizy_id;
    end if;
  end if;
  return new;
end;
$$;

create trigger orders_status_change
  before update on public.orders
  for each row execute function public.handle_order_status_change();

-- ── order_events ─────────────────────────────────────────────────────────────
-- Append-only audit trail. Powers the customer's live tracking timeline and the
-- admin CRM's Timeline tab, and answers "who changed this and when".
create table public.order_events (
  id          bigserial primary key,
  order_id    uuid not null references public.orders(id) on delete cascade,
  from_status public.order_status,
  to_status   public.order_status not null,
  actor_id    uuid references public.profiles(id) on delete set null,
  actor_role  public.user_role,
  note        text,
  -- Proof-of-delivery photo captured by the worker on completion.
  photo_path  text,
  created_at  timestamptz not null default now()
);

create index order_events_order_idx on public.order_events (order_id, created_at desc);

create or replace function public.log_order_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'INSERT' or new.status is distinct from old.status then
    insert into public.order_events (order_id, from_status, to_status, actor_id, actor_role)
    values (
      new.id,
      case when tg_op = 'UPDATE' then old.status else null end,
      new.status,
      auth.uid(),
      public.auth_role()
    );
  end if;
  return new;
end;
$$;

create trigger orders_log_event
  after insert or update of status on public.orders
  for each row execute function public.log_order_event();

-- ── bridge_requests ──────────────────────────────────────────────────────────
-- "Bridge" a conversation between the expat customer and someone back home —
-- a doctor, a school, an official — with a Faizy facilitating.
create table public.bridge_requests (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references public.profiles(id) on delete cascade,
  family_member_id  uuid references public.family_members(id) on delete set null,
  order_id          uuid references public.orders(id) on delete set null,
  subject           text not null,
  details           text,
  counterparty_name text,
  counterparty_phone text,
  preferred_time    timestamptz,
  status            public.order_status not null default 'pending',
  outcome_notes     text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index bridge_requests_user_idx on public.bridge_requests (user_id, created_at desc);
create index bridge_requests_status_idx on public.bridge_requests (status);

create trigger bridge_requests_touch before update on public.bridge_requests
  for each row execute function public.touch_updated_at();

-- ── product_requests ─────────────────────────────────────────────────────────
-- Product-finder: customer describes what they want sourced, ops quotes it, the
-- customer approves, and only then does it become an order. The approval gate is
-- the point of the table — never source before the customer has accepted a price.
create table public.product_requests (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references public.profiles(id) on delete cascade,
  family_member_id  uuid references public.family_members(id) on delete set null,
  order_id          uuid references public.orders(id) on delete set null,
  product_name      text not null,
  description       text,
  reference_url     text,
  quantity          integer not null default 1,
  max_budget        numeric(12,2),
  currency          text not null default 'AED',

  -- Quote
  quoted_price      numeric(12,2),
  quoted_by         uuid references public.profiles(id) on delete set null,
  quoted_at         timestamptz,
  quote_notes       text,

  -- Customer decision
  approved_at       timestamptz,
  rejected_at       timestamptz,

  status            public.order_status not null default 'pending',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),

  constraint product_requests_qty_positive check (quantity > 0),
  constraint product_requests_not_both_decisions
    check (approved_at is null or rejected_at is null),
  -- Cannot be approved without a quote to approve.
  constraint product_requests_approved_needs_quote
    check (approved_at is null or quoted_price is not null)
);

create index product_requests_user_idx on public.product_requests (user_id, created_at desc);
create index product_requests_status_idx on public.product_requests (status);

create trigger product_requests_touch before update on public.product_requests
  for each row execute function public.touch_updated_at();

-- ── ratings ──────────────────────────────────────────────────────────────────
-- One rating per order, from the customer, about the Faizy who did the work.
create table public.ratings (
  id          uuid primary key default gen_random_uuid(),
  order_id    uuid not null unique references public.orders(id) on delete cascade,
  user_id     uuid not null references public.profiles(id) on delete cascade,
  faizy_id    uuid not null references public.faizies(id) on delete cascade,
  score       smallint not null,
  comment     text,
  created_at  timestamptz not null default now(),

  constraint ratings_score_range check (score between 1 and 5)
);

create index ratings_faizy_idx on public.ratings (faizy_id, created_at desc);

-- Keep the Faizy's running average correct without recomputing over all rows.
create or replace function public.apply_rating_to_faizy()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.faizies
     set rating_count = rating_count + 1,
         rating_avg = round(
           ((coalesce(rating_avg, 0) * rating_count) + new.score)::numeric
           / (rating_count + 1), 2)
   where id = new.faizy_id;
  return new;
end;
$$;

create trigger ratings_apply after insert on public.ratings
  for each row execute function public.apply_rating_to_faizy();
