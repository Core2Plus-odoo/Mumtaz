# Faizy

WhatsApp-first family care for Pakistanis living abroad. Customers subscribe;
a network of vetted on-ground workers in Pakistan ("Faizies") run errands and
provide care for their family back home.

What matters is where the family is, not where the subscriber is. The Gulf is
the largest market, but the customer base already spans the UK and the US, so
plans carry a published price per currency (PKR, AED, SAR, USD, GBP) rather
than one base price converted at today's rate.

Operated by **C2P Consultants FZC LLC**.

**Built on Odoo Community 19** — a separate instance with its own database and
its own domain. See `docs/00-decisions.md` for why, and
`docs/02-odoo-deployment.md` for how to stand it up.

---

## What's here

```
faizy/
├── odoo/
│   ├── addons/
│   │   ├── faizy_core/       Plans, subscriptions, family, network, orders, wallet, WhatsApp
│   │   └── faizy_website/    Public site, pricing, worker sign-up, customer portal
│   └── tools/
│       ├── validate_modules.py   Static checks — run before every push
│       └── make_icon.py          Renders the brand mark to the module icon
├── brand/                    The mark and the brand rules
└── docs/
    ├── 00-decisions.md       Architecture decisions and open questions
    ├── 01-milestones.md      Plan and estimates
    └── 02-odoo-deployment.md Provisioning the instance and the domain
```

## The business, as modelled

| Concept | Model |
|---|---|
| Subscription tiers | `faizy.plan` — price, monthly activity allowance, overage rate |
| A customer's plan and meter | `faizy.subscription` |
| Every activity consumed | `faizy.activity.log` (append-only) |
| Family back home | `faizy.family.member` — permanent FMB IDs |
| Ground workers | `faizy.worker`, `faizy.area`, `faizy.service` |
| Worker recruitment | `faizy.application` → promotes to a worker |
| Care tasks | `faizy.order` — kanban, assignment, photo proof, ratings |
| Conversations and sourcing | `faizy.bridge.request`, `faizy.product.request` |
| Money movement | `faizy.wallet.transaction` (append-only) |
| Outbound messaging | `faizy.whatsapp.message` (queue) |
| Document vault | `faizy.document` — CNICs, passports, expiry reminders |
| Sample data | `faizy.sample.data` — fills an empty instance, removable |

## Ground rules

**Money is computed, never entered.** The platform fee (5%) and vendor commission
(10%) are derived from purchase value by `_compute_amounts`, and the rates live on
`res.company` so ops changes them in Settings rather than waiting for a release.
Order amounts are stored, so a historical order keeps the rate it was actually
computed with.

**The meter is server-side.** Activities are spent through
`subscription.consume_activity()`, in the order free grant → plan allowance →
overage. A booking with neither free activities nor a subscription is refused at
`action_confirm`. Nothing customer-facing writes `activities_used`.

**Odoo Community has no Subscriptions app.** `sale_subscription` is Enterprise, so
the recurring cycle is ours: `_cron_recurring_invoice` closes the period, invoices
through `account.move` with an overage line, and rolls the allowance.

**Sensitive data is scoped.** Medical notes are restricted to the Operations
group. Portal record rules limit a customer to their own family and orders, and a
Faizy to their own assignments. Orders can be marked private, which hides the
member's identity from the assigned worker.

**The care score is a heuristic, and says so.** It answers whether a family is actually being looked after or the subscription is just sitting there — recency, coverage, consistency, readiness. It is a prompt for ops to reach out, not a rating of the customer.

**The brand is one thing in one place.** `brand/` holds the mark and the rules —
including the contrast rule that orange is a background colour, never a text
colour.

## Before you push

```bash
python3 odoo/tools/validate_modules.py
```

Checks manifests against the files on disk, parses every XML, verifies every
model has an ACL and every ACL resolves, and catches views referencing fields the
model never declares. CI runs the same thing, plus flake8 and a check that the
committed icon still matches its generator.

It is a smoke test, not a substitute for installing the module — do that on a
staging database before releasing.

## Known open items

- **Placeholder numbers.** `activities_included` per tier and the overage price
  are guesses; the brief never states them. Settings → Faizy → Plans.
- **The logo is hand-built, not traced.** See `brand/README.md`.
- **WhatsApp does not send yet.** Messages queue correctly and wait for a
  provider — `docs/00-decisions.md` §2.
- **`/join` needs a CAPTCHA or rate limit** before it is announced.
- **Payment gateway is still undecided** — `docs/00-decisions.md` §3.
