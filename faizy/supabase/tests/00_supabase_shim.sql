-- =============================================================================
-- Supabase shim for validating migrations on a PLAIN PostgreSQL instance.
--
-- Purpose: let anyone check that the migrations parse and apply cleanly without
-- needing Docker or a Supabase project. It recreates only the surface the
-- migrations touch — the auth and storage schemas, the JWT helpers, and the
-- three Supabase roles.
--
-- NOT FOR PRODUCTION, and never applied to a real Supabase project (which
-- already has all of this, properly implemented). Used by `pnpm db:verify`.
--
-- Usage:
--   createdb faizy_check
--   psql -d faizy_check -f supabase/tests/00_supabase_shim.sql
--   for f in supabase/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -d faizy_check -f "$f"; done
-- =============================================================================

create extension if not exists "pgcrypto";

-- ── Roles ────────────────────────────────────────────────────────────────────
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
end
$$;

-- ── auth schema ──────────────────────────────────────────────────────────────
create schema if not exists auth;

create table if not exists auth.users (
  id                  uuid primary key default gen_random_uuid(),
  phone               text unique,
  email               text unique,
  raw_user_meta_data  jsonb not null default '{}'::jsonb,
  raw_app_meta_data   jsonb not null default '{}'::jsonb,
  created_at          timestamptz not null default now()
);

-- Reads the same request.jwt.claims GUC that Supabase's PostgREST sets, so tests
-- can impersonate a user with:  set local request.jwt.claims = '{"sub":"...”}';
create or replace function auth.jwt()
returns jsonb
language sql
stable
as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true), '')::jsonb,
    '{}'::jsonb
  );
$$;

create or replace function auth.uid()
returns uuid
language sql
stable
as $$
  select nullif(auth.jwt() ->> 'sub', '')::uuid;
$$;

create or replace function auth.role()
returns text
language sql
stable
as $$
  select coalesce(auth.jwt() ->> 'role', 'anon');
$$;

-- ── storage schema ───────────────────────────────────────────────────────────
create schema if not exists storage;

create table if not exists storage.buckets (
  id                 text primary key,
  name               text not null,
  public             boolean not null default false,
  file_size_limit    bigint,
  allowed_mime_types text[],
  created_at         timestamptz not null default now()
);

create table if not exists storage.objects (
  id         uuid primary key default gen_random_uuid(),
  bucket_id  text references storage.buckets(id),
  name       text not null,
  owner      uuid,
  created_at timestamptz not null default now()
);

alter table storage.objects enable row level security;

-- Splits an object path into its segments, matching Supabase's implementation.
create or replace function storage.foldername(name text)
returns text[]
language plpgsql
immutable
as $$
declare
  parts text[];
begin
  parts := string_to_array(name, '/');
  return parts[1:array_length(parts, 1) - 1];
end;
$$;

grant usage on schema public, auth, storage to anon, authenticated, service_role;
