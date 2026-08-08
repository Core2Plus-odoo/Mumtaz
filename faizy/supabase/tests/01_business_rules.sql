-- =============================================================================
-- Faizy — business-rule regression tests.
--
-- Covers the logic that would silently cost money if it broke: fee computation,
-- the free-activity grant, the paywall, and the notification queue.
--
-- Run against a scratch database after the shim + migrations + seed:
--   psql -v ON_ERROR_STOP=1 -d faizy_check -f supabase/tests/01_business_rules.sql
--
-- Every check raises an exception on failure, so ON_ERROR_STOP turns a broken
-- rule into a non-zero exit code.
-- =============================================================================

\set ON_ERROR_STOP on

create or replace function pg_temp.check(p_label text, p_condition boolean, p_detail text default '')
returns void
language plpgsql
as $$
begin
  if p_condition then
    raise notice '  PASS  %', p_label;
  else
    raise exception 'FAIL: % %', p_label, p_detail;
  end if;
end;
$$;

do $$
declare
  v_user      uuid := gen_random_uuid();
  v_member1   uuid;
  v_member2   uuid;
  v_fmb1      text;
  v_fmb2      text;
  v_order     uuid;
  v_order2    uuid;
  v_faizy     uuid;
  v_platform  numeric;
  v_commission numeric;
  v_total     numeric;
  v_source    text;
  v_free      integer;
  v_notifs    integer;
  v_rating    numeric;
  v_paywalled boolean := false;
  i           integer;
begin
  raise notice '--- identity & FMB allocation ---';

  insert into auth.users (id, phone, raw_user_meta_data)
  values (v_user, '+971501234567', '{"full_name":"Test Customer"}'::jsonb);

  perform pg_temp.check(
    'profile auto-created from auth.users',
    exists (select 1 from public.profiles where id = v_user));

  perform pg_temp.check(
    'new customer starts with 3 free activities',
    (select free_activities_remaining from public.profiles where id = v_user) = 3);

  insert into public.family_members (user_id, full_name, relationship, city)
  values (v_user, 'Ammi', 'mother', 'Karachi') returning id, fmb_id into v_member1, v_fmb1;

  insert into public.family_members (user_id, full_name, relationship, city)
  values (v_user, 'Abbu', 'father', 'Karachi') returning id, fmb_id into v_member2, v_fmb2;

  perform pg_temp.check('FMB IDs are zero-padded to 6 digits', v_fmb1 ~ '^FMB-\d{6}$', v_fmb1);
  perform pg_temp.check('FMB IDs increment', v_fmb2 > v_fmb1, v_fmb1 || ' -> ' || v_fmb2);

  raise notice '--- order fee computation (server-side) ---';

  select id into v_faizy from public.faizies where city = 'Karachi' limit 1;

  -- No vendor: platform fee only.
  insert into public.orders (user_id, family_member_id, category, title, city,
                             purchase_value, service_fee)
  values (v_user, v_member1, 'groceries', 'Weekly groceries', 'Karachi', 100.00, 20.00)
  returning id, platform_fee, vendor_commission, total_amount
  into v_order, v_platform, v_commission, v_total;

  perform pg_temp.check('platform fee is 5% of purchase value', v_platform = 5.00, v_platform::text);
  perform pg_temp.check('no vendor means no commission', v_commission = 0, v_commission::text);
  perform pg_temp.check('total = goods + platform fee + service fee', v_total = 125.00, v_total::text);

  -- With a vendor: 10% commission, and it must NOT reach the customer total.
  insert into public.orders (user_id, family_member_id, category, title, city,
                             purchase_value, service_fee, vendor_name)
  values (v_user, v_member1, 'medicine', 'Monthly medicines', 'Karachi', 200.00, 15.00, 'PharmaCo')
  returning id, platform_fee, vendor_commission, total_amount
  into v_order2, v_platform, v_commission, v_total;

  perform pg_temp.check('vendor commission is 10% of purchase value', v_commission = 20.00, v_commission::text);
  perform pg_temp.check('commission is excluded from the customer total', v_total = 225.00, v_total::text);

  -- A client attempting to zero out its own price must not win.
  update public.orders set purchase_value = 500.00 where id = v_order2;
  select platform_fee into v_platform from public.orders where id = v_order2;
  perform pg_temp.check('fees recompute on purchase_value update', v_platform = 25.00, v_platform::text);

  raise notice '--- free activities, then the paywall ---';

  select public.consume_activity(v_order) into v_source;
  perform pg_temp.check('first activity draws on the free grant', v_source = 'free', v_source);

  perform pg_temp.check(
    'consume_activity is idempotent per order',
    public.consume_activity(v_order) = 'already_counted');

  select public.consume_activity(v_order2) into v_source;
  perform pg_temp.check('second activity is still free', v_source = 'free', v_source);

  select free_activities_remaining into v_free from public.profiles where id = v_user;
  perform pg_temp.check('free grant decremented twice', v_free = 1, v_free::text);

  -- Burn the last free activity.
  insert into public.orders (user_id, category, title, city, purchase_value)
  values (v_user, 'documents', 'NADRA renewal', 'Karachi', 0) returning id into v_order;
  perform public.consume_activity(v_order);

  -- Fourth activity with no subscription must hit the hard paywall.
  insert into public.orders (user_id, category, title, city, purchase_value)
  values (v_user, 'other', 'Fourth task', 'Karachi', 0) returning id into v_order;
  begin
    perform public.consume_activity(v_order);
  exception when sqlstate 'P0001' then
    v_paywalled := true;
  end;
  perform pg_temp.check('hard paywall once free activities are spent', v_paywalled);

  raise notice '--- subscription allowance and overage ---';

  insert into public.subscriptions (user_id, plan_code, status, activities_included)
  values (v_user, 'lite', 'active',
          (select activities_included from public.plans where code = 'lite'));

  select public.consume_activity(v_order) into v_source;
  perform pg_temp.check('subscribed activity draws on the included allowance',
                        v_source = 'included', v_source);

  -- Spend the rest of the Lite allowance (5 included, 1 already used).
  for i in 1..4 loop
    insert into public.orders (user_id, category, title, city, purchase_value)
    values (v_user, 'other', 'Task ' || i, 'Karachi', 0) returning id into v_order;
    perform public.consume_activity(v_order);
  end loop;

  insert into public.orders (user_id, category, title, city, purchase_value)
  values (v_user, 'other', 'Over the limit', 'Karachi', 0) returning id into v_order;
  select public.consume_activity(v_order) into v_source;
  perform pg_temp.check('activity beyond the allowance bills as overage',
                        v_source = 'overage', v_source);

  perform pg_temp.check(
    'overage is charged at the plan rate',
    (select amount_minor from public.activity_ledger
      where order_id = v_order) = (select overage_price_minor from public.plans where code = 'lite'));

  raise notice '--- order lifecycle & notifications ---';

  update public.orders set faizy_id = v_faizy, status = 'assigned' where id = v_order2;
  perform pg_temp.check('assignment stamps assigned_at',
                        (select assigned_at from public.orders where id = v_order2) is not null);

  update public.orders set status = 'completed' where id = v_order2;
  perform pg_temp.check('completion stamps completed_at',
                        (select completed_at from public.orders where id = v_order2) is not null);
  perform pg_temp.check('completion increments the customer counter',
                        (select completed_orders from public.profiles where id = v_user) = 1);
  perform pg_temp.check('completion increments the Faizy counter',
                        (select completed_orders from public.faizies where id = v_faizy) = 1);

  perform pg_temp.check(
    'status changes are recorded in the audit trail',
    (select count(*) from public.order_events where order_id = v_order2) >= 3);

  select count(*) into v_notifs from public.wa_notifications where order_id = v_order2;
  perform pg_temp.check('WhatsApp messages are queued for the order', v_notifs >= 4, v_notifs::text);

  perform pg_temp.check(
    'the assigned worker is notified too',
    exists (select 1 from public.wa_notifications
             where order_id = v_order2 and faizy_id = v_faizy));

  perform pg_temp.check(
    'a receipt is queued on completion',
    exists (select 1 from public.wa_notifications
             where order_id = v_order2 and message_type = 'receipt'));

  raise notice '--- ratings ---';

  insert into public.ratings (order_id, user_id, faizy_id, score, comment)
  values (v_order2, v_user, v_faizy, 5, 'Excellent');

  select rating_avg into v_rating from public.faizies where id = v_faizy;
  perform pg_temp.check('rating average updates', v_rating = 5.00, v_rating::text);
  perform pg_temp.check('rating count updates',
                        (select rating_count from public.faizies where id = v_faizy) = 1);

  raise notice '--- constraint enforcement ---';

  begin
    insert into public.ratings (order_id, user_id, faizy_id, score)
    values (v_order2, v_user, v_faizy, 9);
    raise exception 'FAIL: out-of-range rating was accepted';
  exception when check_violation then
    raise notice '  PASS  rating score is range-checked';
  end;

  begin
    insert into public.profiles (id, phone) values (gen_random_uuid(), '0501234567');
    raise exception 'FAIL: non-E.164 phone was accepted';
  exception when check_violation then
    raise notice '  PASS  phone numbers must be E.164';
  end;

  begin
    insert into public.wallet_transactions (user_id, txn_type, amount_minor)
    values (v_user, 'debit', 500);
    raise exception 'FAIL: a positive debit was accepted';
  exception when check_violation then
    raise notice '  PASS  wallet debits must be negative';
  end;

  raise notice '';
  raise notice 'ALL BUSINESS-RULE CHECKS PASSED';
end;
$$;
