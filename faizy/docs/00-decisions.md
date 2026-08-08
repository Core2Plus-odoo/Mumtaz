# Faizy — Technical Decision Memo

**For:** Muhammad (CEO), Shafat Ali (CTO)
**Status:** recommendations — three items marked **DECIDE** need your sign-off before I wire them in
**Scope:** answers every question in §8 of the build brief, plus two corrections to §5 that are
expensive to reverse later.

---

## TL;DR

| # | Question | Recommendation | Reversibility |
|---|---|---|---|
| 1 | Odoo vs all-in Supabase | **All-in Supabase.** No Odoo in the product path. | Cheap to revisit |
| 2 | WhatsApp: Meta vs Twilio | **Meta Cloud API** as target, **Twilio as launch fallback**, behind one interface | Cheap — it's an adapter |
| 3 | Payment gateway | **Stripe** first, local rail (Tap/PayTabs) added when Saudi volume justifies | **DECIDE** — costly |
| 4 | Worker app: PWA vs React Native | **PWA.** Plus a WhatsApp assignment path — see §4, it may matter more than the app | Cheap |
| 5 | Hosting | **Vercel**, not Netlify — conflicts with the existing guide | Cheap |
| 6 | Supabase region | **NOT Singapore.** Frankfurt or Mumbai — see §6 | **DECIDE** — near-irreversible |
| 7 | Data model | Supabase Auth owns identity; `public.users` is a *profile* table — see §7 | **DECIDE** — costly |

Everything not marked **DECIDE** I've already defaulted on and started building.

---

## 1. Odoo vs all-in Supabase — *recommendation: drop Odoo from the product path*

**Recommendation: build ops and billing entirely in Supabase + the admin panel. Do not put Odoo in
the critical path.**

Reasoning:

- **Two systems of record is the actual cost, not the hosting.** The exploratory `faizy_core` models
  (`faizy.plan`, `faizy.subscription`, `faizy.vendor`, `faizy.product.request`) duplicate tables the
  Supabase schema needs anyway. Run both and you own a sync problem forever: an order completes in
  Supabase, an invoice lives in Odoo, and now two systems disagree about who has paid. That class of
  bug is expensive and never fully goes away.
- **The logic is small.** Commission (10% vendor), platform fee (5% of purchase value), activity
  counting with overage, product-request quoting — that is roughly five tables and arithmetic. It is
  not worth an ERP.
- **The admin panel needs to show all of it regardless.** You are building those screens either way.
  Building them against Supabase means one data model, one auth model, one realtime channel.
- **Team shape.** Four people, one CTO who also owns infra. An Odoo instance is a standing
  maintenance commitment — version upgrades, module compatibility, a specialist to keep it alive.
  That is a poor trade at 22 subscribers.

**The honest counterargument:** C2P Consultants already runs Odoo work — this very repo is an Odoo
delivery practice, so the in-house familiarity is real. But familiarity in the consulting business is
not a reason to put an ERP in the product's critical path. Different risk profile entirely.

**What Odoo would genuinely be good at is accounting** — VAT-compliant books, double-entry journals,
statutory financial statements. That is a real need, just not this quarter and not coupled to the app.

**So build for that exit now, cheaply:** the schema I've written keeps `wallet_transactions` and the
activity ledger as **append-only, signed, immutable rows** with an explicit counterparty on every
entry. That is a hand-off-ready ledger. When you do want books, a monthly export into Odoo Accounting
(or Zoho Books) is a mapping exercise, not a re-architecture.

**Revisit when:** vendor payouts run at volume and need reconciliation, or an auditor requires
double-entry books, or you pass ~1,000 subscribers. Not before.

---

## 2. WhatsApp — Meta Cloud API vs Twilio

**Recommendation: target Meta Cloud API direct. Keep Twilio as the launch fallback. Build both behind
one `WhatsAppProvider` interface so the choice is a config change, not a rewrite.**

| | Meta Cloud API (direct) | Twilio |
|---|---|---|
| Per-message cost | Meta's rate only | Meta's rate **+ Twilio markup** |
| Setup | Meta app, business verification, webhook, token rotation | Fastest — one SDK, they handle sender registration |
| Time to first message | Days–weeks (verification) | Hours |
| Feature lag | None — newest features first | Follows Meta |
| Ops burden | You own token refresh + webhook | Twilio absorbs it |

Two things drive this:

1. **Cost compounds and the markup is pure overhead.** Your volume is per-order notifications across
   OTP, booking confirmation, assignment, status updates, and receipts — call it 5–10 messages per
   order. That scales linearly with the business, and a per-message markup scales with it forever.
   The one-time setup cost of going direct is repaid quickly.

2. **Business verification is the schedule risk, not the code.** Meta business verification takes
   days to weeks and needs trade licence documents for C2P Consultants FZC LLC. **This is the long
   pole for launch — start it today, before any of this code is finished.** If it lands late, ship on
   Twilio and flip the provider flag; nothing else changes.

> ⚠️ **Verify current pricing yourself before committing.** WhatsApp moved to per-template pricing
> (authentication / utility / marketing categories priced separately, per destination country) and
> the rates for Pakistan and UAE change. Do not budget off my numbers — pull the current rate card
> from Meta and Twilio for **PK and AE destinations** specifically. Note that the OTP path uses
> *authentication* templates, which are priced differently from the *utility* templates your
> order-status messages will use.

Implementation: a Supabase Edge Function is the right home for the send path (close to the DB, no
separate service to host, cheap). The `wa_notifications` table stays the queue and the audit trail —
every message is a row before it is an API call, so failed sends are visible and replayable.

---

## 3. Payment gateway — **DECIDE**

You flagged this as needing your sign-off. Here is the case.

**Recommendation: start on Stripe. Add a local rail (Tap Payments or PayTabs) as a second provider
when Saudi volume justifies it.**

Why Stripe first:

- **Your billing model maps directly onto Stripe Billing.** "N activities per month, overage billed
  per-activity" is precisely Stripe's metered/usage-based subscription primitive. Free activities are
  a trial quantity. Proration, dunning, retries on failed cards, invoice generation — all
  off-the-shelf. Rolling that yourself against a local processor is genuinely weeks of work, and
  dunning done badly silently loses you paying subscribers.
- **UAE is your primary market and is card-heavy.** Stripe supports AED natively. The local-payment
  gap that matters in Saudi (mada) is not a factor in UAE.
- **Fastest path to revenue**, which is what you asked for.

What you give up, and when it starts to hurt:

- **mada** is the dominant debit network in Saudi Arabia and Stripe does not acquire on it. Saudi
  customers paying with mada-only cards will simply fail. If Saudi is a meaningful share of the 22
  and growing, this bites early.
- Local acquiring generally posts **better authorisation rates** in-region than international
  acquiring. On small recurring tickets (AED 26–119), a few points of decline rate is material.

So: **instrument declines from day one.** The payments layer I'm scaffolding is a provider interface
with a `payment_attempts` audit table. When mada-shaped declines show up in the data, adding Tap or
PayTabs as a second rail is an adapter, not a migration.

Alternatives considered: **Checkout.com** (excellent MENA approval rates, but enterprise-oriented
onboarding and you build recurring logic yourself), **Telr** (UAE-solid, weak billing primitives),
**Tap** (best GCC coverage incl. mada/KNET, developer-friendly — the most likely second rail).

> ⚠️ **Two things to check before I wire this in:**
> 1. **Entity eligibility.** You bill as C2P Consultants FZC LLC — a free-zone entity. Stripe UAE
>    onboarding requires a UAE-licensed entity and the trade licence activity must actually cover
>    this service. Free-zone companies are generally fine, but confirm your licence activity matches
>    a subscription care service before building on it.
> 2. **Currency presentation.** §4 prices in AED only. Do Saudi customers get charged in AED (FX
>    surprise on their statement) or SAR (you hold two price books)? This changes the schema, so I
>    need it early. My default until you say otherwise: **AED as the single billing currency, with
>    SAR shown as an indicative converted price** — simplest, and honest as long as the UI says so.

---

## 4. Worker app — PWA vs React Native

**Recommendation: build it as a second Next.js PWA. Not React Native.**

The two capabilities you named are both solved on the web:

- **Camera for proof-of-delivery:** `<input type="file" accept="image/*" capture="environment">`
  opens the native camera on both Android and iOS. Sufficient for photo proof.
- **GPS:** `navigator.geolocation` works fine for check-in/check-out location stamping.

What you actually give up: reliable **background** location (geofencing to auto-detect arrival),
and app-store presence. iOS web push is supported for installed PWAs since 16.4, so notifications are
mostly a non-issue — and your workers are on Android anyway.

What you gain, and it is the real argument: **your workers are in Pakistan on mid- and low-end
Android.** Android PWA install works well there, and — more importantly — **you can ship a fix in
minutes instead of waiting on Play Store review.** For a field-ops app you will iterate on weekly in
the first months, that difference dominates everything else. One codebase, one design system, one
deploy pipeline, and Shafat does not inherit a mobile release process.

**Revisit if** you need background geofencing or genuinely offline-first operation in low-connectivity
areas. Both are plausible later. Neither is a week-one blocker.

### One product flag worth more than the framework choice

**Your workers already live in WhatsApp. An app — any app — is a new thing to install, learn, and
remember.** You are building a WhatsApp notification service regardless. Consider making the core
worker loop work *entirely inside WhatsApp*: receive assignment → reply to accept → send photo to
complete. The PWA then becomes the richer surface for earnings, history, and availability, rather
than a hard dependency for doing the job.

For adoption among ground staff in Pakistan I would expect that to outperform any app. I've kept the
data model agnostic about which surface writes the status change, so you can run both. Worth a
conversation — it may change what "the worker app" needs to be.

---

## 5. Hosting — Vercel over Netlify ⚠️ *conflicts with the existing guide*

**Recommendation: Vercel.** The existing `DEPLOYMENT_GUIDE.md` assumes Netlify.

Next.js is a Vercel product. App Router capabilities — server actions, streaming, middleware, ISR —
land on Vercel first and work without adapter friction; Netlify's Next runtime consistently lags and
produces a class of "works locally, breaks deployed" bugs that costs real debugging time. Since we
are standardising on Next.js App Router, Vercel removes that whole category. Cost is comparable at
your scale.

Not a hard call — if Shafat has a strong Netlify preference, it works. I've kept the apps free of
platform-specific APIs either way.

---

## 6. Supabase region — **DECIDE**, and please don't use Singapore

§5 specifies `ap-southeast-1` (Singapore) as "closest low-latency region to both Pakistan and the
GCC." **That is not right, and the region cannot be changed after project creation without a full
migration** — so it's worth thirty seconds now.

Rough distances to Dubai, your primary market:

| Region | ~Distance from Dubai | ~Distance from Karachi |
|---|---|---|
| `ap-southeast-1` Singapore | ~5,800 km | ~4,900 km |
| `ap-south-1` Mumbai | ~1,900 km | ~900 km |
| `eu-central-1` Frankfurt | ~4,800 km | ~5,800 km |

Singapore is the **farthest** option from your customers. It is a real latency penalty on every
round trip, and your app is realtime-dependent (§7 asks for sub-2-second order updates).

Two defensible choices:

- **`ap-south-1` (Mumbai)** — fastest by a wide margin for both your GCC customers and your Pakistani
  workers. The concern is jurisdictional: hosting Pakistani customers' family data, CNIC scans, and
  medical-errand records in India. Some of your customers would object to that if they knew, and it
  is the kind of thing that surfaces at the worst moment.
- **`eu-central-1` (Frankfurt)** — ~110–130 ms to the GCC, mature region, neutral jurisdiction,
  strong data-protection posture. Slower than Mumbai, still far better than Singapore.

**My recommendation: Frankfurt.** You are storing CNIC documents, family member records, and health-
related errands for a diaspora community. The jurisdictional neutrality is worth more than the ~50 ms
Mumbai would save, and Frankfurt still beats the currently-specified region comfortably. But this is
a business call about your customers' data as much as a technical one — tell me which and I'll set it.

---

## 7. Data model correction — **DECIDE** (small but structural)

The prototype `schema.sql` has a `users` table. Supabase Auth already owns identity in `auth.users`.

A second parallel identity table is a well-known prototype-to-production trap: two sources of truth
for "who is this person," RLS policies that can't reference the right key, and orphaned rows when one
side is deleted.

**The fix is standard:** `public.profiles` (or keep the name `users`) holds *profile* data only, with
`id uuid primary key references auth.users(id) on delete cascade`. Auth owns identity; your table
owns everything else. Every RLS policy then keys off `auth.uid()` cleanly.

I've written the migrations this way. It is the right shape and I'd need a strong reason to deviate —
but since it touches every table's foreign keys, flagging rather than silently diverging from a file
you told me was the source of truth.

---

## 8. Stack — confirmed

Everything else in §5 I'm adopting as specified, and it's a sound set of choices:

- **Next.js App Router + TypeScript + Tailwind**, mobile-first, PWA-installable — right for a
  phone-first GCC audience.
- **Supabase** for Postgres + Auth + Realtime + Storage — right call at your stage; the free tier
  genuinely covers you to ~500 users, and Realtime gives you the sub-2s requirement without a socket
  server to run.
- **WhatsApp-number OTP, no email/password** — correct for the audience.
- **Turborepo + pnpm workspaces** — scaffolded.

One addition you didn't ask for but will want: **the admin panel must never hold the Supabase service-
role key in the browser.** That key bypasses RLS entirely. Admin privileged reads go through
server-side route handlers with the key server-only. I've structured `apps/admin` accordingly — worth
knowing since it's the single most common way a Supabase app gets fully compromised.

---

## 9. Conflicts between the old prototypes and this brief

You asked me to call these out rather than silently pick. Items 1–2 you've already resolved; 3–9 are
open.

| # | Conflict | Resolution |
|---|---|---|
| 1 | Brand: blue/gold + Cormorant vs orange/black + Poppins | **Resolved by you** — new identity. Old tokens purged; nothing ships blue/gold. |
| 2 | Urdu tagline spelling — ہ vs ح | **Resolved by you** — حاضر ہیں۔ with ح (bari he). Implemented with Noto Nastaliq + proper RTL shaping. |
| 3 | Guide says Netlify; I recommend Vercel | §5 — your call, low cost either way |
| 4 | Brief says Singapore region; I recommend Frankfurt | §6 — **needs your answer**, near-irreversible |
| 5 | Odoo `faizy_core` exploration vs all-in Supabase | §1 — recommend dropping Odoo |
| 6 | Guide assumes Twilio; I recommend Meta direct | §2 — both built, config flag |
| 7 | `schema.sql` `users` table vs Supabase `auth.users` | §7 — **needs your answer** |
| 8 | Prices are "approx" AED, and SAR handling is undefined | §3 — **need exact figures + currency policy** |
| 9 | "3 free activities" — expiry undefined | Defaulted to **no expiry, consumed on use**. Say if wrong. |
| 10 | Prototypes hold logic in localStorage/client | Under RLS, pricing/commission/activity-counting **must** be server-side — a customer can otherwise forge their own activity count. Moving to DB functions + server routes. |

---

## 10. What I need from you

**Blocking (I cannot finish these parts without you):**

1. **The prototype files.** `faizy-final.html`, the Faizy `admin.html`, `vendor-onboarding.html`,
   `schema.sql`, `supabase-integration.js`, `DEPLOYMENT_GUIDE.md` — **none of them are in this repo.**
   I checked every branch and the full commit history. Please re-export them. You said they encode
   decisions you don't want re-litigated, so I've deliberately **not** rebuilt the customer/admin/
   worker feature sets from guesswork — that's exactly where invented UX would waste your time.
2. **The logo PNG** from facebook.com/faizy.pk, so the F monogram can be traced properly. I've built
   an interim geometric mark to the description so nothing is blocked, but it must be replaced with
   the real asset before launch — see `packages/brand/README.md`.
3. **Region** (§6) and **payment gateway** (§3) — both expensive to reverse.

**Non-blocking but needed soon:** exact tier prices and currency policy (§3), free-activity expiry
(§9), and confirmation on the `users`/`auth.users` shape (§7).

**Already started, no input needed:** monorepo scaffold, brand/design system, database migrations,
auth flow, provider interfaces for WhatsApp and payments.
