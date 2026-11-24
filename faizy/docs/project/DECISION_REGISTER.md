# Faizy — Decision Register (ADR-001..013)

Retrospective register. These decisions were made, mostly implicitly, over the build history in
`faizy/docs/00-decisions.md` and the git log — this register makes them explicit and traceable, per
the ERP Master Blueprint §2 mandatory decision list. Status `Accepted (as-built)` means the decision
is already live in production code, evidenced by a specific file; it is not a new proposal.

---

### ADR-001 — Odoo extension vs greenfield custom ERP vs integration

**Status:** Accepted (as-built)
**Evidence:** `faizy_core/__manifest__.py` depends on `base, mail, contacts, product, account, l10n_pk`;
all three addons (`faizy_core`, `faizy_website`, `faizy_ai`) are Odoo modules, not a separate service.
**Decision:** Odoo 19 Community extension. No custom ERP platform exists or is proposed.
**Rationale (from the manifest's own description):** "Odoo Community has no Subscriptions app
(Enterprise only), so recurring invoicing is built here on a scheduled action" — i.e., deliberately
built *inside* Odoo Community's constraints rather than reaching for Enterprise or a bespoke billing
service.

### ADR-002 — Tenant model

**Status:** Accepted (as-built)
**Evidence:** No `tenant_id` field anywhere; single `res.company` record ("Faizy"); no multi-tenant
module or database-per-tenant logic found.
**Decision:** Single tenant, single company. Not a SaaS-multi-tenant product today.
**Open question:** none raised in the repo. If Faizy ever white-labels for another operator, this
decision needs revisiting — out of scope until that is actually asked for.

### ADR-003 — Company/branch/department/warehouse model

**Status:** Accepted (as-built)
**Evidence:** No `faizy.branch`/`department`/`warehouse` model exists; `faizy.order.city` is a free
Char, not a structured location hierarchy.
**Decision:** No branch/department/warehouse structure. Geography is handled loosely via
`faizy.area` (city + name) for worker coverage, and a plain `city` string on orders/workers.
**Gap flagged:** if Faizy expands to multiple operating cities with separate ops teams, this flat
model will need a real branch/area ownership structure — not needed today, evidenced by current
single-city-style usage (areas are a coverage tag, not an organizational unit).

### ADR-004 — Financial source of truth

**Status:** Accepted (as-built)
**Evidence:** `account.move` (native Odoo Invoicing) is the only ledger; `faizy.subscription` posts
to it via `_cron_recurring_invoice`; `faizy.wallet.transaction` is a separate, **non-accounting**
ledger (no `account.move` link) for a customer-facing wallet balance display.
**Decision:** Odoo's native GL/AR is the financial source of truth for subscription revenue. The
wallet ledger is explicitly informational, not a financial subledger — it is not reconciled to
`account.move` anywhere in the code.
**Gap flagged:** platform fee and vendor commission are *computed and stored* on `faizy.order`
(`platform_fee`, `vendor_commission`, `amount_total`) but **never posted to a journal entry**. The
5% platform fee that is this product's own revenue model is not in the books. See FIT_GAP_REGISTER
FIN-01/FIN-03.

### ADR-005 — Inventory valuation

**Status:** N/A — out of scope
**Evidence:** No `faizy.stock`/inventory model exists; `faizy_core` does not depend on Odoo's
`stock` module.
**Decision:** Faizy does not hold inventory. Orders describe a purchase made *on the customer's
behalf* (groceries, medicine) — the money is tracked (`purchase_value`), not the goods. Correctly
out of scope; do not build an inventory module without a real requirement.

### ADR-006 — Localization

**Status:** Accepted (as-built), partially open
**Evidence:** `l10n_pk` (Pakistan) is a hard `faizy_core` dependency. `faizy.whatsapp.message.lang`
supports `en`/`ur`. Company country/currency/TRN are **not set in code** (`company_setup.py`).
**Decision:** Pakistan accounting localization is installed, but the company's own
country/currency/tax-registration configuration is an open item — this charter does not assume it
has been completed by hand on production. **Do not post real invoices against an unverified fiscal
configuration.**

### ADR-007 — Workflow/approval engine

**Status:** Accepted (as-built)
**Evidence:** `faizy_ai.draft` state machine (`draft → approved → executed/rejected`), group-based
approval routing (`G_COMMS`/`G_OPS`/`G_MANAGER` in `faizy_ai/models/utils.py`), `_check_approver` /
`_check_content` constraints, working-hours hold (`within_hours`).
**Decision:** A purpose-built lightweight approval model for AI-drafted actions, not a generic Odoo
`approval.request` workflow. Reasonable for the narrow set of AI-initiated actions it covers
(customer messages, order create/update); it is **not** a general-purpose approval engine for
human-initiated transactions (e.g. there is no approval gate on a staff member creating an order
directly).

### ADR-008 — Integration strategy

**Status:** Accepted (as-built)
**Evidence:** `faizy_whatsapp_transport.py` (this session) — Meta Cloud API direct + Twilio
fallback, one `faizy_whatsapp_provider` flag on `res.company`. Inbound via a signed Meta webhook
(`faizy_ai/controllers/whatsapp.py`).
**Decision:** WhatsApp is the only external integration. Outbound credentials live as `res.company`
fields (Settings UI); inbound webhook credentials live as `ir.config_parameter` — **two different
credential-storage conventions for the same Meta integration**, flagged as a minor inconsistency
worth unifying in a later pass, not urgent.
**Open:** no payment gateway, no accounting/ERP integration beyond Odoo itself, no e-invoicing
gateway (not required — Pakistan has no mandatory e-invoicing regime for this business type as far
as this repo evidences; unverified, needs a local review per blueprint §24's regulatory caveat).

### ADR-009 — Security and identity

**Status:** Accepted (as-built)
**Evidence:** Three-tier `res.groups` hierarchy in `faizy_core` (`group_faizy_user` →
`group_faizy_ops` → `group_faizy_manager`, each implying the previous), plus `faizy_ai`'s own
`group_ai_agent`/`group_comms`. Standard Odoo session auth; no SSO/MFA found.
**Decision:** Standard Odoo RBAC via groups + record-level ACLs (`ir.model.access.csv`,
`check_portal_access.py` verifies portal-group readability). No SSO/MFA layer. Reasonable for current
scale; revisit if/when staff count or compliance requirements grow.

### ADR-010 — Deployment and disaster recovery

**Status:** Partially accepted (as-built), partially open
**Evidence:** `deploy/` scripts referenced in session history (`faizy-odoo` systemd service on
Hostinger VPS); no backup/RPO/RTO documentation found in this repo.
**Decision:** Single production VPS, systemd-managed Odoo process, git-based deploy. **No documented
backup policy, no disaster-recovery runbook, no staging environment evidenced in this repo** — a
real open item, not something to assume is handled elsewhere without confirmation.

### ADR-011 — Accounting close/correction policy

**Status:** N/A — not yet applicable
**Evidence:** No fiscal-year-end close, no lock-date policy, no reversal/correction procedure found
in `faizy_subscription.py` beyond standard `account.move` behavior.
**Decision:** Relies entirely on Odoo Invoicing's native posting/reversal mechanics; no Faizy-specific
close policy exists. Reasonable while volume is low; needs a real policy once monthly closes start
mattering to the business (tied to ASM-01).

### ADR-012 — Stack or Odoo version and supported dependencies

**Status:** Accepted (as-built)
**Evidence:** `__manifest__.py` version strings are all `19.0.x.y.z`; `odoo/tools/check_core_fields.py`
and `check_view_schemas.py` verify against live Odoo 19.0 core schemas fetched from GitHub.
**Decision:** Odoo 19.0 is the confirmed, continuously-verified target version. This register and the
fit-gap below should be re-checked if the instance is ever upgraded.

### ADR-013 — Mobile customer app platform *(added this session; not in the blueprint's base list)*

**Status:** Accepted in principle, implementation paused
**Evidence:** `faizy_website/controllers/api.py` (JSON API behind `/api/care/*`, built this session)
exists; no React Native project exists in this repo yet.
**Decision:** Cross-platform (React Native) client against a new JSON API on the existing Odoo
backend — explicitly **not** a rewrite, **not** a TWA wrapper, **not** native Kotlin (decided
earlier this session via direct user confirmation). Paused pending a working test login on
production; see Pending Tasks in prior session history. Carried forward here so it is not lost from
the decision record.
