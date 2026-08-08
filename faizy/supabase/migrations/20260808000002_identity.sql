-- =============================================================================
-- Faizy — 0002: customer identity and the family they are caring for.
-- =============================================================================

-- ── profiles ─────────────────────────────────────────────────────────────────
-- Profile data for an authenticated user. Identity itself lives in auth.users.
--
-- Auth is WhatsApp-number OTP, so `phone` is the login handle. It is duplicated
-- here (denormalised from auth.users.phone) purely so the admin CRM can search
-- and join without reaching into the auth schema.
create table public.profiles (
  id                uuid primary key references auth.users(id) on delete cascade,
  phone             text not null,
  full_name         text,
  email             text,
  -- Where the CUSTOMER lives (the expat), not where their family lives.
  country           text not null default 'AE',        -- ISO-3166-1 alpha-2
  city              text,
  preferred_language text not null default 'en',       -- 'en' | 'ur'
  avatar_url        text,
  -- Denormalised counter for the "care score" ring on the app home. Maintained
  -- by trigger in 0004 — never written by the client.
  completed_orders  integer not null default 0,
  onboarding_completed_at timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),

  constraint profiles_phone_e164 check (phone ~ '^\+[1-9]\d{7,14}$'),
  constraint profiles_language_valid check (preferred_language in ('en', 'ur'))
);

create unique index profiles_phone_key on public.profiles (phone);
create index profiles_country_city_idx on public.profiles (country, city);
create index profiles_name_trgm_idx on public.profiles using gin (full_name gin_trgm_ops);

create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

-- Create the profile row automatically when Supabase Auth creates the user, so
-- the app never has to handle a signed-in user with no profile.
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, phone, full_name)
  values (
    new.id,
    coalesce(new.phone, new.raw_user_meta_data ->> 'phone', ''),
    new.raw_user_meta_data ->> 'full_name'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_auth_user();

-- ── family_members ───────────────────────────────────────────────────────────
-- The people back home. Each gets a permanent FMB ID.
create table public.family_members (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.profiles(id) on delete cascade,
  -- Allocated by the sequence. Permanent for the life of the member.
  fmb_id        text not null unique
                default 'FMB-' || lpad(nextval('public.fmb_id_seq')::text, 6, '0'),
  full_name     text not null,
  relationship  text not null,                        -- mother, father, sibling, ...
  phone         text,
  date_of_birth date,
  -- Where the member actually lives — this drives Faizy assignment by city.
  city          text not null,
  area          text,
  address       text,
  -- Free-text medical notes (allergies, conditions, regular medication).
  -- Sensitive: RLS-restricted to the owning customer and admins.
  medical_notes text,
  notes         text,
  photo_url     text,
  is_active     boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),

  constraint family_members_phone_e164
    check (phone is null or phone ~ '^\+[1-9]\d{7,14}$')
);

create index family_members_user_idx on public.family_members (user_id) where is_active;
create index family_members_city_idx on public.family_members (city);
create index family_members_fmb_idx on public.family_members (fmb_id);

create trigger family_members_touch before update on public.family_members
  for each row execute function public.touch_updated_at();

-- ── documents ────────────────────────────────────────────────────────────────
-- The customer's document vault, plus worker-uploaded proof-of-delivery photos.
-- Files live in Supabase Storage; this table is the metadata + access control.
create table public.documents (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references public.profiles(id) on delete cascade,
  family_member_id uuid references public.family_members(id) on delete set null,
  doc_type      public.document_type not null default 'other',
  title         text not null,
  -- Path within the storage bucket, NOT a public URL. Access is always via a
  -- short-lived signed URL — CNIC scans must never sit behind a guessable link.
  storage_path  text not null,
  mime_type     text,
  size_bytes    bigint,
  expires_at    date,                                  -- passport/visa expiry reminders
  uploaded_by   uuid references public.profiles(id) on delete set null,
  created_at    timestamptz not null default now(),

  constraint documents_size_sane check (size_bytes is null or size_bytes between 0 and 26214400)
);

create index documents_user_idx on public.documents (user_id, created_at desc);
create index documents_member_idx on public.documents (family_member_id);
create index documents_expiry_idx on public.documents (expires_at) where expires_at is not null;
