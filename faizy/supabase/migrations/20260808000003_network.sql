-- =============================================================================
-- Faizy — 0003: the ground network. Faizies and the application pipeline.
-- =============================================================================

-- ── faizies ──────────────────────────────────────────────────────────────────
-- A vetted on-ground worker in Pakistan.
--
-- `user_id` is nullable on purpose: a Faizy exists as an operational record from
-- the moment ops approves them, which is before they have ever signed into the
-- worker app. It is linked when they first authenticate.
create table public.faizies (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid unique references public.profiles(id) on delete set null,
  full_name       text not null,
  phone           text not null unique,
  cnic            text unique,                        -- 13 digits, formatted 00000-0000000-0
  email           text,
  city            text not null,
  areas_covered   text[] not null default '{}',
  services        public.service_category[] not null default '{}',
  status          public.faizy_status not null default 'applicant',
  -- Availability toggle in the worker app. Assignment only considers workers
  -- who are both `active` AND available.
  is_available    boolean not null default false,
  photo_url       text,
  -- Performance stats shown on the admin roster. Maintained by trigger (0004).
  completed_orders integer not null default 0,
  cancelled_orders integer not null default 0,
  rating_avg      numeric(3,2),
  rating_count    integer not null default 0,
  -- Per-order payout rate. Payouts land in wallet_transactions as 'payout'.
  base_rate_pkr   numeric(12,2) not null default 0,
  joined_at       date not null default current_date,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  constraint faizies_phone_e164 check (phone ~ '^\+[1-9]\d{7,14}$'),
  constraint faizies_cnic_format check (cnic is null or cnic ~ '^\d{5}-\d{7}-\d$'),
  constraint faizies_rating_range check (rating_avg is null or rating_avg between 1 and 5)
);

-- Partial index: assignment always queries for available active workers in a
-- city, and that is the hot path in the admin Kanban.
create index faizies_assignable_idx on public.faizies (city, status)
  where status = 'active' and is_available;
create index faizies_status_idx on public.faizies (status);
create index faizies_name_trgm_idx on public.faizies using gin (full_name gin_trgm_ops);
create index faizies_services_idx on public.faizies using gin (services);

create trigger faizies_touch before update on public.faizies
  for each row execute function public.touch_updated_at();

-- ── faizy_applications ───────────────────────────────────────────────────────
-- Public 6-step onboarding wizard writes here. Feeds the admin Applications
-- pipeline. Deliberately NOT linked to auth — applicants have no account yet.
create table public.faizy_applications (
  id              uuid primary key default gen_random_uuid(),
  reference_no    text not null unique
                  default 'FZY-' || lpad(nextval('public.faizy_app_ref_seq')::text, 5, '0'),

  -- Step 2 — personal
  full_name       text not null,
  phone           text not null,
  cnic            text not null,
  email           text,
  date_of_birth   date,

  -- Step 3 — location & coverage
  city            text not null,
  areas_covered   text[] not null default '{}',

  -- Step 4 — services & availability
  services        public.service_category[] not null default '{}',
  availability    jsonb not null default '{}'::jsonb,   -- {mon:["09:00-17:00"], ...}
  has_vehicle     boolean not null default false,
  vehicle_type    text,

  -- Step 5 — experience & references
  experience_years integer,
  experience_notes text,
  references_json  jsonb not null default '[]'::jsonb,  -- [{name, relation, phone}]

  -- Step 6 — documents (storage paths, same signed-URL rule as public.documents)
  cnic_front_path text,
  cnic_back_path  text,
  selfie_path     text,

  -- Step 7 — agreements
  code_of_conduct_accepted boolean not null default false,
  rate_card_accepted       boolean not null default false,
  accepted_at              timestamptz,

  -- Pipeline
  status          public.application_status not null default 'submitted',
  review_notes    text,
  reviewed_by     uuid references public.profiles(id) on delete set null,
  reviewed_at     timestamptz,
  -- Set when an approved application is converted into a faizies row.
  faizy_id        uuid references public.faizies(id) on delete set null,

  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  constraint applications_phone_e164 check (phone ~ '^\+[1-9]\d{7,14}$'),
  constraint applications_cnic_format check (cnic ~ '^\d{5}-\d{7}-\d$'),
  -- An approved application must carry the reviewer's decision trail.
  constraint applications_approved_has_review
    check (status <> 'approved' or reviewed_at is not null)
);

create index applications_status_idx on public.faizy_applications (status, created_at desc);
create index applications_city_idx on public.faizy_applications (city);
create index applications_ref_idx on public.faizy_applications (reference_no);

create trigger applications_touch before update on public.faizy_applications
  for each row execute function public.touch_updated_at();

-- Promote an approved application into an active Faizy record.
-- SECURITY DEFINER + an explicit admin check: ops staff call this, and it is the
-- only supported path from application to worker.
create or replace function public.approve_faizy_application(p_application_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_app public.faizy_applications;
  v_faizy_id uuid;
begin
  if not public.is_admin() then
    raise exception 'only admins may approve applications' using errcode = '42501';
  end if;

  select * into v_app from public.faizy_applications where id = p_application_id for update;
  if not found then
    raise exception 'application % not found', p_application_id using errcode = 'P0002';
  end if;
  if v_app.faizy_id is not null then
    return v_app.faizy_id;   -- idempotent: already promoted
  end if;

  insert into public.faizies (full_name, phone, cnic, email, city, areas_covered, services, status)
  values (v_app.full_name, v_app.phone, v_app.cnic, v_app.email, v_app.city,
          v_app.areas_covered, v_app.services, 'active')
  returning id into v_faizy_id;

  update public.faizy_applications
     set status = 'approved',
         faizy_id = v_faizy_id,
         reviewed_by = auth.uid(),
         reviewed_at = now()
   where id = p_application_id;

  return v_faizy_id;
end;
$$;
