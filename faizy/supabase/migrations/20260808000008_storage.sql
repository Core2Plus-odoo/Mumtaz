-- =============================================================================
-- Faizy — 0008: Storage buckets and their access rules.
--
-- All three buckets are PRIVATE. Files are served through short-lived signed
-- URLs, never public links. These buckets hold CNIC scans, selfies and medical
-- paperwork — a public bucket here is a data breach with a guessable URL.
--
-- Path convention (enforced by the policies below):
--   documents/<user_id>/<uuid>.<ext>
--   proofs/<order_id>/<uuid>.jpg
--   applications/<reference_no>/<cnic_front|cnic_back|selfie>.<ext>
-- =============================================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('documents', 'documents', false, 26214400,
   array['image/jpeg','image/png','image/webp','image/heic','application/pdf']),
  ('proofs', 'proofs', false, 10485760,
   array['image/jpeg','image/png','image/webp','image/heic']),
  ('applications', 'applications', false, 10485760,
   array['image/jpeg','image/png','image/webp','image/heic','application/pdf'])
on conflict (id) do nothing;

-- ── documents bucket ─────────────────────────────────────────────────────────
-- First path segment must be the caller's own user id.
create policy "documents: owner reads own folder"
  on storage.objects for select to authenticated
  using (
    bucket_id = 'documents'
    and ((storage.foldername(name))[1] = auth.uid()::text or public.is_admin())
  );

create policy "documents: owner writes own folder"
  on storage.objects for insert to authenticated
  with check (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "documents: owner deletes own folder"
  on storage.objects for delete to authenticated
  using (
    bucket_id = 'documents'
    and ((storage.foldername(name))[1] = auth.uid()::text or public.is_admin())
  );

-- ── proofs bucket ────────────────────────────────────────────────────────────
-- The assigned worker uploads proof-of-delivery; the owning customer and admins
-- can view it.
create policy "proofs: assigned worker uploads"
  on storage.objects for insert to authenticated
  with check (
    bucket_id = 'proofs'
    and exists (
      select 1 from public.orders o
       where o.id::text = (storage.foldername(name))[1]
         and o.faizy_id = public.current_faizy_id()
    )
  );

create policy "proofs: order participants read"
  on storage.objects for select to authenticated
  using (
    bucket_id = 'proofs'
    and (
      public.is_admin()
      or exists (
        select 1 from public.orders o
         where o.id::text = (storage.foldername(name))[1]
           and (o.user_id = auth.uid() or o.faizy_id = public.current_faizy_id())
      )
    )
  );

-- ── applications bucket ──────────────────────────────────────────────────────
-- The public wizard uploads here before the applicant has an account, so anon
-- INSERT is required. anon must NOT be able to read — otherwise every applicant's
-- CNIC and selfie is retrievable with the public key.
create policy "applications: anon uploads only"
  on storage.objects for insert to anon, authenticated
  with check (bucket_id = 'applications');

create policy "applications: admin reads"
  on storage.objects for select to authenticated
  using (bucket_id = 'applications' and public.is_admin());
