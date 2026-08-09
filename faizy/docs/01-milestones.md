# Faizy — Milestone Plan

Estimates assume **one full-time engineer** (Shafat) with me generating code, and
that the blockers in `00-decisions.md` §10 clear promptly. Ranges are working
days, not calendar days.

**Two things gate the schedule and neither is code:**

1. **Meta WhatsApp business verification** — days to weeks, needs the C2P
   Consultants FZC LLC trade licence. **Start today.** Everything in M4 and M7
   waits on it. (Twilio fallback keeps you moving if it runs late.)
2. **Payment gateway account approval** — Stripe UAE onboarding for a free-zone
   entity is not instant. Start once you've signed off on §3.

---

## M0 — Foundations ✅ *complete*

| Item | Status |
|---|---|
| Monorepo (pnpm + Turborepo), three apps, three packages | ✅ |
| Brand system on corrected orange/black/Poppins tokens | ✅ |
| Database: 16 tables, RLS, triggers, storage buckets | ✅ verified against real Postgres |
| Business-rule test suite (36 checks) | ✅ all passing |
| Typed data layer, auth helpers, money helpers | ✅ |
| WhatsApp queue + provider adapters (Meta + Twilio) | ✅ code complete, unconfigured |
| Decision memo | ✅ |

Run `./scripts/verify-db.sh` to confirm the schema on any machine.

---

## M1 — Live Supabase project · **0.5–1 day**

Blocked on: **region decision** (§6).

- Create the project in the chosen region, push migrations, apply seed.
- Regenerate `database.types.ts` from the live schema (replaces the hand-written file).
- Wire env vars into all three apps; confirm anon-key reads obey RLS.
- **Verify RLS by attack, not by assumption**: sign in as customer A, try to read
  customer B's family members and documents, confirm every attempt returns zero rows.

## M2 — Auth end-to-end · **1–2 days**

- Twilio account, WhatsApp sender, Supabase phone provider configured.
- OTP request → verify → session persistence across all three apps.
- Role assignment (`app_metadata.role`) for admin and worker accounts.
- Route protection: middleware per app, correct redirects for the wrong role.

## M3 — Customer app · **5–8 days** 🔒

**Blocked on `faizy-final.html`.** Estimate assumes the prototype arrives; without
it, add 2–3 days of UX rework and expect churn on details you'd rather not
re-litigate.

Onboarding (2-step) · family status card · care-score rings · smart suggestions ·
booking flow with privacy toggle · care calendar · recurring bookings · spending
analytics · document vault · FMB ID surfaces · rating modal · Trust Center ·
5-tab nav · realtime order status.

## M4 — Admin panel · **5–7 days** 🔒

**Blocked on `admin.html`.**

Action-first dashboard · Orders Kanban with inline assignment · Customers CRM with
slide-over (Overview/Orders/Family/Notes/Timeline) and auto-segmentation ·
Faizies roster · Applications pipeline · Analytics · WhatsApp queue view ·
Settings. Admin reads that need privilege go through server route handlers.

## M5 — Worker onboarding wizard · **2–3 days** 🔒

**Blocked on `vendor-onboarding.html`.**

6 steps, CNIC auto-formatter, document upload to the private `applications`
bucket, `FZY-XXXXX` reference on completion, feeds the M4 pipeline.
**Add a CAPTCHA or per-IP rate limit** — the endpoint accepts anonymous inserts.

## M6 — Worker app · **4–6 days**

Not blocked — no prototype exists, so this is a fresh build (§4).
Assigned jobs · accept/start/complete · camera proof upload · earnings/payouts ·
availability toggle. Ship the WhatsApp-only path alongside it and compare adoption.

## M7 — WhatsApp automation · **2–3 days**

Blocked on Meta verification. Templates drafted and submitted for approval (that
review is itself 1–2 days), Edge Function deployed, drain scheduled, delivery
webhooks wired back to `wa_notifications`.

> Draft and submit templates EARLY — they can be approved while the apps are
> still being built, and a rejected template found late is a launch delay.

## M8 — Billing · **4–6 days** 🔒

**Blocked on gateway sign-off** (§3) and on the missing numbers: exact tier
prices, activities per tier, overage rate, currency policy.

Gateway integration · subscription lifecycle · activity metering against
`consume_activity` · overage billing · wallet top-ups · dunning · webhook
handlers with signature verification.

## M9 — Deploy & harden · **2–3 days**

Vercel projects ×3 · domains · Supabase production config · rewrite
`DEPLOYMENT_GUIDE.md` against what actually shipped · **RLS penetration pass** ·
backup schedule · error tracking · smoke tests on real devices in UAE and Pakistan.

---

## Rough totals

| Scenario | Working days |
|---|---|
| Everything unblocked, prototypes in hand | **~26–39** |
| Prototypes never arrive (rebuild UX from scratch) | **~33–48** |

**"Deployable this week" is achievable for a narrower thing than the full brief.**
The realistic week-one slice is M1 + M2 + M7 + a cut-down M3 (onboarding, booking,
order list, realtime status) — a working WhatsApp-OTP app that takes bookings and
notifies customers, with ops running on the admin Kanban. Billing and the worker
app follow. If you want that slice, say so and I'll sequence for it.

## Critical path

```
Region decision ─┐
                 ├─→ M1 ─→ M2 ─┬─→ M3 ─→ M9
Meta verification ┘            ├─→ M4 ─→ M5
   (start now)                 ├─→ M6
Gateway sign-off ──────────────┴─→ M8 ─→ M9
```

Meta verification and gateway approval run in parallel with all the code. Both
are paperwork with external wait times — start them before writing another line.
