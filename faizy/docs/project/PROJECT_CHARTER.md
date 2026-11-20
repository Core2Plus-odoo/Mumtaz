# ERP Project Charter — Faizy

**Status:** AS-BUILT retrospective charter, written from the live codebase and git history, not a
green-field plan. Faizy already exists, is deployed, and has real customers; this charter documents
what is actually true today and flags what is genuinely unknown rather than inventing it. See
`faizy/docs/00-decisions.md` for the detailed decision history this charter summarizes.

**Project ID:** FAIZY
**Sponsor and sign-off authority:** Muhammad (product owner; referred to as "Umer" in commit history
and as the `C2P Consultants` account owner — same person, not verified which name he prefers in
writing).
**Business process owners:** Unconfirmed job titles in code/docs reference "Raza" (Operations
approver), "Mashood" (Communications approver) — see `faizy_ai` security groups. No formal org chart
exists in the repo.
**Platform path:** **Odoo 19 Community**, confirmed — not Enterprise (the product description in
`faizy_core/__manifest__.py` explicitly notes "Odoo Community has no Subscriptions app (Enterprise
only), so recurring invoicing is built here on a scheduled action").
**Target stack and framework versions:** Odoo 19.0, Python (Odoo's bundled runtime), PostgreSQL
(standard Odoo backend, version unconfirmed in this repo). No separate frontend framework — the
website/portal is server-rendered Odoo website + QWeb; a React Native mobile app is planned but not
yet started (see Decision Register, ADR-013).
**Legal entities, countries, branches:** One legal entity confirmed in code: **C2P Consultants FZC
LLC** (`faizy_core/company_setup.py`), trading as "Faizy". Registered country, VAT/TRN, and
registered address are explicitly **not set** in code — `company_setup.py`'s own comment states
"Still needed from him: ... the registered address, and the TRN if C2P is VAT-registered... if
Muhammad has not said it, it is not here." Single company (`res.company`); no branch/multi-company
structure exists or is implied anywhere in the models.
**Operating business units / shared services:** None — single product, single team as far as the
repo shows.
**ERP hosting and data residency:** Hostinger VPS, IP `187.77.128.199`, Faizy's own Odoo instance
(`faizy-odoo` service, ports 8079/8078) separate from other products on the same box; console at
`https://myfaizy.com`. Data residency/backup region not documented in this repo.
**Environment names and access ownership:** Production only, as far as this repo evidences
(`/opt/faizy/src` on the VPS). No staging/UAT Odoo instance is referenced in deploy docs. `faizy_ai`'s
own README explicitly states it is "NOT yet installed on faizy_prod" and must go to staging first —
implying a staging environment is expected to exist or be created, not that one currently does.
**Existing systems and data sources:** None — Faizy was built directly in Odoo; no legacy
system/migration source is referenced anywhere in the repo.
**Transaction volumes, concurrency and data history:** Unknown/unmeasured. No load figures, user
counts or order volumes are recorded in the repo. **Do not assume scale** — treat as a small,
early-stage operation until real numbers are provided.
**Target user roles and language needs:** Customer (Pakistanis living abroad — the stated target
market), Family member (care recipient in Pakistan, not a system user), Faizy/Worker (ground-staff
contractor), Vendor (pharmacy/kiryana/lab/courier), Ops/Comms/Manager (internal staff), AI agents
(draft-only, never posting). Language: English + Urdu (`lang` Selection on
`faizy.whatsapp.message`); Roman Urdu used deliberately on invoices (no Nastaliq font available to
the PDF engine, per `company_setup.py`).
**Accounting policies and localization review owner:** `l10n_pk` (Pakistan - Accounting) is a hard
dependency of `faizy_core`, chosen specifically so Invoicing can post at all. No named accountant or
tax-localization reviewer is recorded in the repo. Company currency/country are unset in code (see
above) — **this is a real gap**, not an oversight to paper over: Odoo cannot post correctly without
a resolved company currency and chart of accounts, and nothing in this repo confirms that configuration
has actually been completed on production.
**Security, SSO, MFA, retention, RPO/RTO and audit:** Standard Odoo auth only (no SSO/MFA layer
found). `mail.thread` audit trail (chatter) on most transactional models. No documented backup
RPO/RTO. No data retention policy found.
**Integrations:** WhatsApp (Meta Cloud API direct, Twilio fallback — built this session, not yet
live; see Decision Register ADR-006 and `faizy/docs/00-decisions.md` §2/§12). No payment gateway
integration exists yet (Stripe was recommended in `00-decisions.md` §3 but never built — subscriptions
invoice via `account.move` with no automated collection). No accounting/ERP integration beyond Odoo
itself (single system of record).
**Milestones, commercial constraints and acceptance parties:** No formal milestone plan exists in the
repo beyond `faizy/docs/01-milestones.md` (not re-audited in this charter) and this session's own
`faizy/docs/00-decisions.md` build log.

## Expected measurable outcomes

| Metric | Source/baseline | Target | Owner | Evidence |
|---|---|---|---|---|
| *(none recorded)* | — | — | — | No KPI baselines exist in the repo. Per blueprint principle 1.1, **do not invent baselines** — this table stays empty until the product owner supplies real numbers (MRR, order volume, churn, etc. are computable from `faizy.dashboard` and `faizy.plan.mrr` once there is real data to point at). |

## Module scope

See `faizy/docs/project/FIT_GAP_REGISTER.md` for the full canonical-module classification. Summary:

| ID | Module | Standard / Configure / Extend / Integrate / Defer / Exclude | Owner | Notes |
|---|---|---|---|---|
| PLT-01..08 | Platform (company, security, party, catalog, currency/tax, docs, workflow, data) | Standard + Extend | — | Built on native Odoo; `faizy_core`/`faizy_ai` extend `res.partner`/`res.company` rather than inventing parallel models |
| FIN-01/02 | GL, AR/customer invoicing | Standard | — | Native `account.move`, `l10n_pk` chart of accounts, subscriptions post invoices via cron |
| FIN-03 | AP, vendor bills | **Gap** | — | Vendor commission is tracked as a reporting figure only; no vendor bill is ever posted automatically |
| SLS-01 | Quotation/orders | Extend (narrow) | — | `faizy.order` is a care-task order, not a generic multi-line sales order; no quotation step |
| SRV-01/02 | Service/field work | Extend (this *is* the core product) | — | `faizy.order` + `faizy.worker` is a lightweight field-service model |
| INV-01..03, MFG-01, HRM-01/02, OMC-01 | Inventory, Manufacturing, HR/Payroll, POS/e-commerce | **Out of scope** | — | No inventory, manufacturing, payroll or POS exists or is planned; Faizy buys nothing it stocks |
| AI-01 | Governed AI agents | Extend | — | `faizy_ai` — draft/approve, never auto-posts |
| VRT-01 | Industry extension | N/A | — | Faizy itself *is* a single-purpose vertical; there is no further vertical layer on top of it |

## Critical business cycles

**AS-IS, as evidenced by code (no TO-BE redesign proposed without a signed decision):**

1. **Signup → free trial → paywall:** `/start` creates a portal user + `res.partner` with
   `faizy_free_activities` (default 3, from `res.company.faizy_free_activity_grant`). First 3 care
   requests that consume an activity are free; the 4th requires an active `faizy.subscription`
   (`action_confirm` on `faizy.order` raises `UserError` otherwise).
2. **Care request lifecycle:** `faizy.order` states `pending → assigned → scheduled → in_progress →
   completed` (or `cancelled`). Each transition queues a WhatsApp notification
   (`_notify_whatsapp`) to the customer and, on assignment, to the worker. `faizy_order_alert.py`
   additionally alerts ops (WhatsApp + email + chatter note) on every new order.
3. **Vendor-fulfilled orders:** an order may route through an approved `faizy.vendor` (pharmacy,
   kiryana, lab, courier); `purchase_value`, `platform_fee` (5%, company-configurable) and
   `vendor_commission` (10%, company- or vendor-configurable) are computed, never entered. Vendor
   commission accrues as a number; **no automated AP bill is raised** — this is a documented gap, not
   a missing requirement nobody noticed (see FIT_GAP_REGISTER FIN-03).
4. **Subscription billing:** `faizy.subscription._cron_recurring_invoice` posts `account.move`
   customer invoices on each `next_invoice_date`. No payment gateway is wired to collect them
   automatically.
5. **Worker onboarding:** `faizy.application` (public form with CNIC/selfie images, code-of-conduct
   acceptance) → manager review → `faizy.worker` created on approval.
6. **AI-drafted actions:** `faizy_ai.draft` lets named agents (CoS, Insights, Rabta, etc.) propose a
   customer WhatsApp message, a new order, or an order update; nothing executes until a human in the
   right approval group (`Mashood`/Comms for customer messages, `Raza`/Ops for orders, `Umer`/Manager
   for anything) approves it. Customer messages additionally hold until Faizy working hours
   (10am–9pm Asia/Karachi).

No TO-BE process changes are proposed in this charter. Section 6 of `FIT_GAP_REGISTER.md` lists the
concrete, evidence-based gaps a future increment could close.

## Assumptions / dependencies / unresolved decisions

| ID | Description | Impact | Owner | Due | Status |
|---|---|---|---|---|---|
| ASM-01 | Company country/currency/TRN are unset in code; unconfirmed whether they are set by hand on production | Accounting correctness (tax, invoice numbering) cannot be fully verified from the repo alone | Muhammad | — | **Open** |
| ASM-02 | No real WhatsApp (Meta/Twilio) credentials exist anywhere; nothing sends yet despite the transport now being built | Every customer/ops notification this product has ever queued has never been delivered | Muhammad | — | **Open** (see `00-decisions.md` §12) |
| ASM-03 | No Meta template is registered/approved for any of the 5 business-initiated message types | Even with credentials, booking confirmations etc. will be rejected by Meta outside a session window | Muhammad | — | **Open** |
| ASM-04 | No payment gateway exists; subscription invoices post but nothing collects them automatically | Revenue collection is manual today | Muhammad | — | **Open, deferred per `00-decisions.md` §3** |
| ASM-05 | Vendor commission never becomes an AP bill automatically | Vendor payouts require a human to create a Vendor Bill by hand every time | Muhammad | — | **Open** |
| ASM-06 | No staging/UAT Odoo instance evidenced; `faizy_ai` explicitly says it is not yet installed on `faizy_prod` | Risk of testing new modules directly against production | Muhammad | — | **Open** |

## Approvals

| Stage gate | Business approver | IT/technical approver | Financial approver | Date |
|---|---|---|---|---|
| G0 — Discovery & audit (this charter + fit-gap register) | *pending* | — | — | — |
| G1 — Architecture & fit-gap | *pending* | — | — | — |

This charter and the accompanying `FIT_GAP_REGISTER.md` are the G0/G1 deliverables requested under
the ERP Master Development Directive. Per the directive's own methodology ("Use the templates and
stage-gates rather than telling Claude to generate the entire ERP in a single run"), detailed module
specs, a field-level data dictionary and a prioritized backlog are deferred until this read of scope
is approved.
