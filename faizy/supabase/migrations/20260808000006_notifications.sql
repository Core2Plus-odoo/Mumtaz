-- =============================================================================
-- Faizy — 0006: the WhatsApp notification queue.
--
-- Every message is a ROW BEFORE IT IS AN API CALL. That ordering is the whole
-- point: a send that fails is a visible, retryable row rather than a lost
-- customer notification nobody noticed. It also gives ops a single place to see
-- what was sent to whom, which matters when a customer says "I was never told".
--
-- Provider-agnostic on purpose — Meta Cloud API and Twilio both drain this same
-- queue. See docs/00-decisions.md §2.
-- =============================================================================

create table public.wa_notifications (
  id              bigserial primary key,
  -- Recipient. May be a customer, a Faizy, or a raw number (OTP before signup).
  user_id         uuid references public.profiles(id) on delete set null,
  faizy_id        uuid references public.faizies(id) on delete set null,
  to_phone        text not null,

  message_type    public.wa_message_type not null,
  -- The approved WhatsApp template name. Free-form text messages only work
  -- inside a 24h customer service window; templates work always. Everything
  -- outbound and unprompted must be a template.
  template_name   text,
  template_params jsonb not null default '{}'::jsonb,
  body_preview    text,
  language_code   text not null default 'en',

  order_id        uuid references public.orders(id) on delete set null,

  status          public.wa_status not null default 'queued',
  provider        text,                                 -- 'meta' | 'twilio'
  provider_msg_id text,
  error_message   text,
  attempts        integer not null default 0,
  -- Backoff: the drain worker only picks up rows whose time has come.
  next_attempt_at timestamptz not null default now(),
  sent_at         timestamptz,
  delivered_at    timestamptz,

  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  constraint wa_to_phone_e164 check (to_phone ~ '^\+[1-9]\d{7,14}$'),
  constraint wa_attempts_bounded check (attempts >= 0 and attempts <= 10),
  constraint wa_language_valid check (language_code in ('en', 'ur'))
);

-- The drain query: queued or retryable, oldest first.
create index wa_notifications_drain_idx
  on public.wa_notifications (next_attempt_at, status)
  where status in ('queued', 'failed');

create index wa_notifications_user_idx on public.wa_notifications (user_id, created_at desc);
create index wa_notifications_order_idx on public.wa_notifications (order_id);
create index wa_notifications_provider_msg_idx on public.wa_notifications (provider_msg_id)
  where provider_msg_id is not null;

create trigger wa_notifications_touch before update on public.wa_notifications
  for each row execute function public.touch_updated_at();

-- ── Queue helper ─────────────────────────────────────────────────────────────
-- SECURITY DEFINER so triggers and server routes can enqueue without granting
-- clients write access to the queue. A customer who could INSERT here could
-- send WhatsApp messages from Faizy's number to anyone.
create or replace function public.queue_wa_notification(
  p_to_phone      text,
  p_message_type  public.wa_message_type,
  p_template_name text default null,
  p_params        jsonb default '{}'::jsonb,
  p_user_id       uuid default null,
  p_faizy_id      uuid default null,
  p_order_id      uuid default null,
  p_language      text default 'en'
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id bigint;
begin
  insert into public.wa_notifications
    (to_phone, message_type, template_name, template_params,
     user_id, faizy_id, order_id, language_code)
  values
    (p_to_phone, p_message_type, p_template_name, coalesce(p_params, '{}'::jsonb),
     p_user_id, p_faizy_id, p_order_id, coalesce(p_language, 'en'))
  returning id into v_id;
  return v_id;
end;
$$;

revoke all on function public.queue_wa_notification(
  text, public.wa_message_type, text, jsonb, uuid, uuid, uuid, text
) from public, anon, authenticated;

-- ── Automatic notifications on order status change ───────────────────────────
-- Booking confirmation, assignment (to both sides), and status updates are
-- queued by the database rather than by app code, so they fire regardless of
-- which surface moved the order.
create or replace function public.notify_on_order_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_customer_phone text;
  v_customer_lang  text;
  v_faizy_phone    text;
  v_faizy_name     text;
begin
  select phone, preferred_language into v_customer_phone, v_customer_lang
    from public.profiles where id = new.user_id;

  if v_customer_phone is null or v_customer_phone = '' then
    return new;
  end if;

  -- New booking → confirm to the customer.
  if tg_op = 'INSERT' then
    perform public.queue_wa_notification(
      v_customer_phone, 'booking_confirmation', 'booking_confirmation',
      jsonb_build_object('order_no', new.order_no, 'title', new.title),
      new.user_id, null, new.id, v_customer_lang);
    return new;
  end if;

  if new.status is distinct from old.status then
    if new.status = 'assigned' and new.faizy_id is not null then
      select phone, full_name into v_faizy_phone, v_faizy_name
        from public.faizies where id = new.faizy_id;

      perform public.queue_wa_notification(
        v_customer_phone, 'faizy_assigned', 'faizy_assigned',
        jsonb_build_object('order_no', new.order_no, 'faizy_name', v_faizy_name),
        new.user_id, null, new.id, v_customer_lang);

      -- The worker's assignment message. This is also the WhatsApp-first worker
      -- path discussed in docs/00-decisions.md §4 — it works with or without
      -- the worker app installed.
      if v_faizy_phone is not null then
        perform public.queue_wa_notification(
          v_faizy_phone, 'faizy_assigned', 'worker_assignment',
          jsonb_build_object('order_no', new.order_no, 'title', new.title,
                             'city', new.city, 'address', coalesce(new.address, '')),
          null, new.faizy_id, new.id, 'ur');
      end if;

    elsif new.status in ('in_progress', 'completed', 'cancelled') then
      perform public.queue_wa_notification(
        v_customer_phone, 'status_update', 'order_status_update',
        jsonb_build_object('order_no', new.order_no, 'status', new.status::text),
        new.user_id, null, new.id, v_customer_lang);

      -- Completion also sends the receipt.
      if new.status = 'completed' then
        perform public.queue_wa_notification(
          v_customer_phone, 'receipt', 'order_receipt',
          jsonb_build_object('order_no', new.order_no,
                             'total', new.total_amount::text,
                             'currency', new.currency),
          new.user_id, null, new.id, v_customer_lang);
      end if;
    end if;
  end if;

  return new;
end;
$$;

create trigger orders_notify
  after insert or update of status on public.orders
  for each row execute function public.notify_on_order_change();
