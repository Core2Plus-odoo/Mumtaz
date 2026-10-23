# Faizy — Technical Decision Memo

**For:** Muhammad (CEO), Shafat Ali (CTO)
**Scope:** answers every question in §8 of the build brief, plus corrections to §5.

---

## ⚠️ DECIDED: Odoo Community, full stack

**Muhammad's call. Faizy runs on Odoo Community — a separate instance, its own
database, its own domain. Not Next.js + Supabase.**

This reverses the recommendation in §1 below, which argued for dropping Odoo. The
reasoning in that section is kept as the record of what was weighed, but it is
**superseded** — do not build from it.

**The argument that decided it, and which §1 under-weighted:** Odoo *is* the admin
panel. The orders kanban, the customer CRM with segmentation, the applications
pipeline, vendor bills and analytics all come out of the box. That is 5–7 days of
build that simply disappears, for a four-person team whose company already runs an
Odoo practice. Add the website builder and the customer portal and the surface
area that would have been hand-built shrinks dramatically.

**What was traded away, so nobody is surprised later:**

1. **Odoo Community has no Subscriptions app** — `sale_subscription` is Enterprise.
   The recurring cycle is therefore built in `faizy_core`: a daily cron closes each
   period, raises the invoice through `account.move` with an overage line, and
   rolls the allowance. It works, it is tested, and it is ours to maintain.
2. **The customer experience is a web portal, not an installable phone app.**
   Faizy's edge over Mohsyn is transparency, and the portal delivers it — live
   status, receipts, photo proof. But it will not feel like a native app on a
   phone in Dubai. If that becomes the complaint, the answer is a thin PWA over
   Odoo's JSON-RPC, not a rebuild.

**What carried over unchanged:** the brand system, the FMB ID scheme, the fee
model (5% platform, 10% commission), the free-activity grant and paywall, and the
WhatsApp-queue design. The business logic was never the part in question.

**Superseded by this decision:** §1 (Odoo vs Supabase), §5 (Vercel hosting), §6
(Supabase region), §7 (auth.users vs profiles). Sections 2, 3, 4, 8.1, 9 and 10
still stand — WhatsApp provider, payment gateway, the worker-app question, the
repo split, and what is still needed from you.

Deployment: `docs/02-odoo-deployment.md`.

---

## ⚠️ DECIDED: customers can be based anywhere

**Muhammad's call.** The business is not GCC-only and the product should stop
assuming it is. The CRM already has subscribers in London, Manchester and New
York alongside Dubai and Riyadh. What defines a Faizy customer is where their
*family* is, not where they are.

### What this changed

**Prices are published per market, never converted.** Each plan carries a
`faizy.plan.price` row per currency — PKR, AED, SAR, USD, GBP — and the pricing
page has a currency switcher. `plan.price_for(currency)` deliberately does *not*
call `_convert`. A subscription price is a commercial decision expressed in
round local numbers: AED 26.50 and GBP 5.68 are each round in their own market,
and neither is the other run through an FX rate. Quoting a number that moves
with the daily rate is not a price list, it is a currency trade the customer
did not ask for.

**Subscriptions bill in their own currency.** `faizy.subscription.currency_id`
used to be `related="plan_id.currency_id"`, which meant every subscriber in the
world was invoiced in AED. It is now set once from the customer's country when
the subscription is created and then left alone — re-deriving it later would
silently re-price a live subscription the next time someone edited an address.
The price is stored and editable, so a negotiated rate survives a plan change.

**FX is used in exactly one place** and it is labelled as such: plan MRR, which
sums subscriptions across currencies into the company currency. That is an
internal comparison figure, never a number shown to a customer. It is only as
good as the rates in *Settings → Currencies*.

### Two bugs this surfaced

1. `plan.overage_price` was never populated by the data file, so
   `_prepare_invoice_lines` guarded on `if overage_count > 0 and
   plan.overage_price` and **overage never billed at all**. Extra activities
   were free. Now published per market, with the base field set as the fallback.
2. The pricing page rendered that same empty field as "Extra activities
   AED0.00 each".

### What ops must confirm before launch

The PKR figures and the AED plan prices come from the prototype. **The SAR, USD
and GBP plan prices and every non-PKR overage rate were derived** — carried
across at the rate each market's own plan price implies, then rounded to
something sane. They are a working default, not a commercial decision. The rows
are `noupdate`, so editing them in *Faizy → Plans → Prices by Market* sticks
across upgrades.

`tools/check_plan_prices.py` (wired into CI) holds the matrix together: no
market gaps, no missing overage rate, and the plan's own fields kept in step
with the row they are the fallback for.

---

## ⚠️ DECIDED: vendors are a segment of contacts, not a model

**Muhammad's call: "make vendor segment in faizy core."** Built as fields on
`res.partner` behind an `is_faizy_vendor` flag, with its own kanban/list/form
and a *Faizy → Network → Vendors* menu.

**Why not a `faizy.vendor` model.** `faizy.order.vendor_id` already pointed at
`res.partner`, and so do vendor bills, payments and anything the accountant
will eventually want to reconcile. A separate table would mean the same
pharmacy exists twice, and the day the two rows disagree nobody can say which
is right. That is the failure this codebase avoids everywhere else — customers
are `res.partner` too — so vendors follow the same rule. Flagging a partner as
a vendor also sets `supplier_rank`, so they are a vendor everywhere in Odoo,
not only on our screens.

**Commission is per vendor now.** The company rate in Settings is still the
default; `faizy_vendor_custom_commission` + `faizy_vendor_commission_rate` is
the exception. A boolean rather than "0.0 means inherit", because 0% is a real
arrangement — a partner clinic we take nothing from — and "blank means inherit"
would make it impossible to express.

The rate is deliberately **not** in `_compute_amounts`'s `@api.depends`.
Renegotiating terms must not silently rewrite the commission on orders already
delivered and reconciled; new orders pick up the new rate, old ones keep the
figure they were actually computed with. Same principle as the company rate.

**One bug this surfaced.** The sample-data loader's `order()` helper took a
`vendor=None` parameter and never wrote it. Every sample order therefore had
zero commission — the one number that proves the revenue model was the one the
demo could not show. Four sample vendors now exist, three of them attached to
completed orders, one on a negotiated 15%.

---

## Privacy policy — published, and three numbers need your sign-off

`/privacy` is live in `faizy_website`, linked from the footer and from the
contact form. It is written from what the software actually does — every claim
maps to a model in `faizy_core`, including the per-task privacy setting that
hides the family member's name, phone and notes from the assigned Faizy.

**The retention periods are mine, not yours.** I picked working defaults so the
page could say something concrete rather than "TBD", which is worse than
useless on a privacy policy. Confirm or change:

| What | Currently says |
|---|---|
| Account and family records | While subscribed, then 12 months |
| Task history and proof-of-delivery photos | 24 months |
| Stored documents | Until deleted, or 12 months after leaving |
| Invoices, wallet ledger, accounting | 7 years (tax) |
| WhatsApp message log | 24 months |
| Vetting records, unsuccessful applicants | 12 months after the decision |

Two other lines are deliberately non-committal until you decide: the payment
processor is unnamed ("when a provider is in place we will name it"), and there
is no privacy email address because the company record has no email set — the
page routes those requests to WhatsApp and the contact form instead.

Nothing on that page is enforced by code yet. A retention promise without a
cron that deletes is a promise, not a control — worth building before the
customer base is large enough for anyone to ask.

---

## ⚠️ DECIDED: the accounting entity is Pakistani — PKR books, l10n_pk

**Muhammad's call**, asked because it is expensive to reverse: Odoo will not
stop you changing a company's currency under existing journal entries, it
simply restates every one of them.

- **Company currency: PKR.** Was AED.
- **Country: Pakistan**, which is what makes Odoo offer the right taxes.
- **Chart of accounts: `l10n_pk`** — Pakistan - Accounting, which ships in
  Community and carries the CoA, taxes, the VAT report and the withholding tax
  report. It is now a hard dependency of `faizy_core` rather than something ops
  installs by hand: without a chart, Invoicing is present but cannot post, and
  that is the state this database was in.
- **Default price: PKR.** The work is done in Pakistan and costed in rupees.
  Every other market price — AED, SAR, USD, GBP — is a commercial decision made
  on top of that one, not a conversion of it, and the per-market rows are
  unchanged: a subscriber in Dubai still pays the AED figure published for
  Dubai.

**The window this fitted through.** The currency could only be changed because
the books were empty — and they were empty for a bad reason. No plan had a
`product_id`, so `_prepare_invoice_lines` raised `UserError` on every run of the
daily billing cron, which caught it and wrote the failure into the
subscription's chatter. **The recurring billing has never raised a single
invoice.** Six service products now exist and the plans point at them.

Migration order matters and is enforced by the version numbers: `19.0.1.9.0`
gives the plans their products and moves them to PKR, `19.0.1.10.0` moves the
company. Both refuse, loudly and in the log, if the window has closed.

### What this leaves inconsistent, and needs your answer

`res.company.report_footer` still reads **"Faizy is a service of C2P
Consultants FZC LLC"** — a UAE free-zone entity — and it prints on every
invoice. The books are now Pakistani. One of those two is wrong and I have not
guessed which: you told me the accounting entity is Pakistani, you have never
told me the legal entity changed. Either the footer needs the Pakistani
company's name, or the books belong somewhere else after all.

Also still true: orders never reach accounting at all. `purchase_value`,
`platform_fee` and `service_fee` are computed and stored on `faizy.order` and
no `account.move` is ever created, so the 5% platform fee is not in the books.
Vendor commission is computed and never billed. The wallet ledger is
append-only and has no journal entries behind it. Subscriptions are the only
thing that invoices.

---

## TL;DR

*(Sections below predate the decision above. Kept as the record of the analysis;
read the banner first.)*

| # | Question | Recommendation | Reversibility |
|---|---|---|---|
| 1 | Odoo vs all-in Supabase | **All-in Supabase.** No Odoo in the product path. | Cheap to revisit |
| 2 | WhatsApp: Meta vs Twilio | **Meta Cloud API** as target, **Twilio as launch fallback**, behind one interface | Cheap — it's an adapter |
| 3 | Payment gateway | **Stripe** first, local rail (Tap/PayTabs) added when Saudi volume justifies | **DECIDE** — costly |
| 4 | Worker app: PWA vs React Native | **PWA.** Plus a WhatsApp assignment path — see §4, it may matter more than the app | Cheap |
| 5 | Hosting | **Vercel**, not Netlify — conflicts with the existing guide | Cheap |
| 6 | Supabase region | **NOT Singapore.** Frankfurt or Mumbai — see §6 | **DECIDE** — near-irreversible |
| 7 | Data model | Supabase Auth owns identity; `public.users` is a *profile* table — see §7 | **DECIDE** — costly |
| 8 | Where this code lives | **Move to its own repo.** It is currently inside `Core2Plus-odoo/Mumtaz` — see §8.1 | Cheap now, annoying later |

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

### 8.1 Where this code lives — *recommendation: give Faizy its own repository*

Right now this sits in `Core2Plus-odoo/Mumtaz`, under a top-level `faizy/` directory. That is where
the work was commissioned, not where it belongs.

Mumtaz is a different product — an Odoo marketplace and the C2P Agency OS, with its own Python
tooling, its own CI, and its own deployment path to a Hostinger VPS. Faizy is a separate company's
product with a Node/Next toolchain deploying to Vercel and Supabase. Keeping them together means:

- **CI runs the wrong checks.** Every Faizy PR triggers flake8, bandit, pip-audit, Odoo manifest
  validation and hadolint. They pass — because they find nothing to inspect — which is worse than
  failing: it looks like coverage where none exists. Faizy currently has *no* CI of its own.
- **Access control gets awkward.** Anyone who can commit to Faizy can commit to Mumtaz. If Shafat
  or a contractor works on Faizy, they get the Odoo delivery practice too.
- **The histories tangle**, and separating them later costs more the longer you wait.

**Recommendation: `Core2Plus-odoo/faizy`, split before feature work starts.** Nothing here depends on
anything outside `faizy/`, so `git subtree split` moves it with history intact, and a proper CI
workflow (typecheck, build, `verify-db.sh`) can be added at the same time. It is an hour of work now
and a bad afternoon in three months.

Until that happens, treat `faizy/` as self-contained: no imports across the boundary in either
direction.

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
| 8 | Prices are "approx" AED, and SAR handling is undefined | **Resolved** — published price per market (PKR/AED/SAR/USD/GBP), never FX-converted. See "customers can be based anywhere" above. PKR + AED figures are yours; SAR/USD/GBP are derived defaults awaiting your confirmation. |
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

---

## 11. Corrections

**The free-activity grant was never broken.** On 14 Aug I reported that
`/start` had been handing out zero free activities since launch, and shipped
migration `19.0.1.19.0` plus a seed in `apply_company_profile` to repair it.
That was wrong, twice over.

The migration ran on production and changed nothing — no company row and no
partner matched. Measured afterwards on the live database:

    grant as admin       : 3
    public env.company   : 1 'Faizy'
    grant as public      : 3
    a /start signup gets : {'faizy_free_activities': 3}

So the company grant was correct, the public website environment resolves the
company correctly, and a signup receives three. Both diagnoses were wrong: the
column-default premise, and the follow-up guess that `env.company` reads empty
on a public route the way it does in `whatsapp_url`.

What actually prompted it was one contact — partner 32, Muhammad Umer — sitting
at `faizy_free_activities = 0`. That is a fact about one record, not about the
signup flow, and it was generalised without evidence. Its cause is still
unexplained and is worth a look before anyone treats it as a pattern:
`faizy.subscription.consume_activity` spends the free grant first, so a
subscription touching that partner would explain it.

The shipped code is kept. The migration is idempotent and only acts on a grant
of 0 or NULL, and the `apply_company_profile` seed only fires when the grant is
falsy — both are harmless guards against a state that would be a genuine
problem if it ever occurred. Only the claim was wrong, and commit `4024183`'s
message overstates it as a live incident.

