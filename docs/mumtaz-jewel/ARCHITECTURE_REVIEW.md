# Jawhar: architecture review against standard Odoo 19 Community

Date: 2026-11-10. Reviewed as a solution architecture, standard-first: nothing
gets built that Odoo already does. Module availability was checked against the
Odoo 19.0 Community source in this session, not from memory — the repo
`odoo/odoo` is Community only, so a module present there ships to you and one
absent does not.

## 0. Three findings that change the plan

**1. Studio does not exist for you.** `web_studio` is not in Community.
`docs/mumtaz-jewel/CLAUDE.md` says "Odoo 19 Community only. No Enterprise
code", and the repo-root ladder is "standard config → native automation →
Studio → custom-on-top". **Drop the Studio rung.** Your real ladder is:

> standard config → views and `base_automation` + server actions → custom module

Anything previously filed as "Studio will handle it" is now either a view/
automation change or a custom module. `base_automation` is in Community and
covers a lot of what Studio is used for.

**2. WhatsApp is not in Community.** The `whatsapp` module is Enterprise.
Slice 3's owner daily summary and all of Slice 6 assume it. The roadmap
already says "WhatsApp comes through the Meta Cloud API", which is the right
call — just be explicit that there is **no standard module to configure**, so
every WhatsApp feature is custom integration work against Meta's API, with
its own template approval, 24-hour window and opt-in rules.

**3. ZATCA e-invoicing *is* in Community, and so is the bilingual invoice.**
`l10n_sa_edi` ships the real thing: ZATCA UBL 2.1, certificates and CSID,
clearance, attachment handling. `l10n_ae` is the UAE chart. **`l10n_gcc_invoice`
adds Arabic as a secondary language on invoices, credit notes and bills.**

Slice 1 lists "bilingual invoice layout" as something to build. **Do not build
it.** Install `l10n_gcc_invoice`. Slice 11 lists "e-invoicing link" as work;
for Saudi that is a configuration exercise on `l10n_sa_edi`, not a build.

---

## 1. Requirement breakdown

| # | Requirement | Verdict |
| --- | --- | --- |
| R1 | Gold rate with two-person approval; every price derived from it | **Custom** — correctly built |
| R2 | Piece-level identity with weights, tag, certificate | **Standard**, extended |
| R3 | Old-gold intake, melt loss, valuation, threshold approval | **Custom** — correctly built |
| R4 | Client book: tiers, relationship manager, taste, occasions | **Standard + custom fields**, mostly built |
| R5 | Private/Royal confidentiality and access logging | **Standard** (record rules) + custom log |
| R6 | Counter / POS, offline, serial, shift close | **Standard** — see POS_NATIVE_AUDIT.md |
| R7 | Multi-store stock, transfers, per-store limits | **Standard** |
| R8 | Daily gold reconciliation in grams | **Custom** (thin) |
| R9 | Repairs and custom orders | **Standard** (`repair`, `mrp`) |
| R10 | Loyalty, wishlist, campaigns | **Standard** (`loyalty`) |
| R11 | Pipeline: tray → viewing → reservation → sale | **Standard** (`crm`, `sale`) |
| R12 | Bilingual (Arabic/English) documents and UI | **Standard** (`l10n_gcc_invoice` + i18n) |
| R13 | VAT, e-invoicing, GCC compliance | **Standard** (`l10n_ae`, `l10n_sa_edi`) |
| R14 | AML thresholds, KYC status, screening | **Custom** — no standard equivalent |
| R15 | WhatsApp and client app | **Custom integration** (no Community module) |
| R16 | AI agents with autonomy levels and audit | **Custom** |
| R17 | Premium front end over the Odoo engine | **Custom — the largest decision open** |

## 2. Standard capability, by area

| Area | Module (19.0 Community) | What you get free |
| --- | --- | --- |
| Pieces | `stock` | `stock.lot` serial identity, quants, valuation, multi-warehouse |
| Counter | `point_of_sale` | Offline (service worker + IndexedDB), serial per line, shift close with cash variance, manager-only price control, barcode |
| Sales pipeline | `crm`, `sale_management` | Leads, opportunities, stages, activities, quotations |
| Client record | `base`, `mail` | `res.partner`, chatter, activities, record rules, followers |
| Repairs | `repair` | Repair orders, parts, warranty |
| Workshop | `mrp` | BoM, work orders, components |
| Loyalty | `loyalty`, `pos_loyalty` | Programmes, coupons, gift cards, eWallet |
| Messaging | `mail`, `sms` | Email, SMS, templates, scheduled activities |
| Automation | `base_automation` | No-code triggers and server actions |
| VAT / GCC | `l10n_ae`, `l10n_gcc_invoice` | UAE chart; **Arabic secondary language on invoices** |
| E-invoicing | `l10n_sa_edi`, `account_edi_ubl_cii` | ZATCA UBL 2.1, certificates, clearance |
| Who served | `pos_hr` | Cashier ↔ employee |

**Not in Community** (do not design around these): `web_studio`, `whatsapp`,
`documents`, `sign`, `approvals`, `quality`, `iot`, `pos_iot`.

## 3. Gap analysis — what is genuinely yours to build

Only these have no standard path:

1. **The pricing engine and the approved-rate gate** (R1). Odoo prices from a
   pricelist; a jewellery piece prices from net weight × purity × an approved
   rate plus wastage, making, stones, VAT. Correctly custom, correctly a pure
   library.
2. **Old gold** (R3). Odoo has no concept of buying metal back from a customer
   mid-sale.
3. **Gram-level reconciliation** (R8). Odoo reconciles value and quantity, not
   fine-weight grams across stores.
4. **AML/KYC** (R14). No standard model for screening status, risk band or a
   cash threshold per client per year.
5. **The AI layer** (R16). No standard equivalent.
6. **WhatsApp and the client app** (R15). Custom integration.
7. **The front end** (R17). Discussed below.

Everything else on the roadmap should start by configuring a standard module
and extending it, not by writing a new one.

## 4. Solution options for the open decisions

### R17 — the premium front end (the big one)

**A. Standard configuration.** Use the Odoo web client with a branded theme
plus the POS UI for the counter. Cost: low. Ceiling: it will always look like
Odoo, and the counter is the only screen you can meaningfully restyle.

**B. Studio.** *Not available.* `web_studio` is Enterprise.

**C. Custom.** Two sub-options, and they are very different:

- **C1 — OWL components inside Odoo.** Custom views and client actions in
  Odoo's own framework. You get the look you want on the screens that matter,
  while every read and write still goes through Odoo's ORM, record rules and
  ACLs. Upgrades hurt at the view layer only.
- **C2 — a separate web app against an API.** The prototype as drawn. Full
  design freedom, and a second application to secure, authenticate, deploy,
  and keep in step with the model. **Every record rule you rely on for Private
  and Royal clients has to be re-proved on that boundary**, because the app
  talks to an API, not to a form.

**Recommendation: C1 for the counter and the owner screen; C2 only for the
client-facing tray and the eventual client app**, where the audience is
outside the business and a public, non-Odoo surface is appropriate anyway.
C2 for internal screens doubles your security surface for a visual gain, and
the confidentiality rules are the part of this product you least want to
re-implement.

### R14 — AML and KYC

**A. Configuration.** Partner fields and a filter; no workflow. Insufficient.
**B.** Not available.
**C. Custom, small.** A `jewellery.kyc` record on the partner holding status,
document expiry, screening date, risk band, and a computed year-to-date cash
figure. Use `base_automation` for the expiry reminders rather than writing a
cron. Keep every threshold in `ir.config_parameter`, dated and owner-set, as
the current code already does for VAT and the exchange limit.

### R11 — tray, viewing, reservation

**A. Configuration.** A `crm.lead` per tray, stages Draft → Shared → Viewing →
Reserved → Won, with activities for follow-up. Reservation is a `sale.order`
in draft with the lot assigned. **This is almost entirely standard** and the
roadmap currently reads as if Slice 2B builds it from nothing. Build only the
tokenised public link and the eligibility ranking; everything behind it is CRM.

## 5. Technical design notes for what stays custom

- Keep the pricing engine a **pure library with no Odoo imports** — it already
  is, which is what let it be tested without a database. Do not let it reach
  into models.
- Price onto a POS line **server-side**, not by setting `price_type = manual`
  in JS: a manual price is indistinguishable from a staff override, and you
  lose the control you built.
- For the rate inside an offline session, store a **signed snapshot with an
  explicit expiry** on `pos.config` at session open, and refuse to sell
  against an expired one. The expiry is a business decision; make it a
  configuration parameter.
- Multi-company: `jewellery.owner.card` has no `company_id` (see
  FUNCTIONAL_REVIEW.md). Add it before a second company exists, with a
  company rule. Every new model should carry `company_id` from the start.
- GCC: install `l10n_ae` for the chart and `l10n_gcc_invoice` for Arabic
  invoices early, because tax configuration is painful to retrofit once there
  are posted entries.

## 6. Risks and considerations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| C2 front end re-implements confidentiality on an API boundary | **High** | Prefer C1 internally; if C2, every record rule gets an API-level test as a release gate |
| WhatsApp assumed to be a module; it is not | **High** | Plan Meta Cloud API integration with template approval and opt-in; do not promise a date before an account exists |
| Studio assumed available | Medium | Replan those items as views + `base_automation` |
| Scale at the counter assumed available | Medium | `iot`/`pos_iot` are Enterprise. Weigh something on real hardware before promising it |
| Slice 2B rebuilding CRM | Medium | Map tray to `crm.lead`; build only the link and the ranking |
| Bilingual invoice built by hand | Low | Install `l10n_gcc_invoice` |
| Multi-company gaps surface late | Medium | Add `company_id` now; make it a review checklist item |
| Odoo 19 is young; 19→20 upgrade | Medium | Keep customisation in inherited models and separate modules, which the current structure already does well |

## 7. What I would not change

The three addons are structured the way a reviewer would want: a pure
pricing library, thin models that extend standard ones rather than replacing
them, `ir.config_parameter` for every compliance value, record rules for
confidentiality, and maker-checker enforced in the model rather than the view.
The standard-first discipline has been followed where it counts. The risk in
this project is not the code written so far — it is the surface area the
roadmap is about to add.
