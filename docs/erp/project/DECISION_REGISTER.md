# Decision register (ADR index and project decisions)

Status: **Proposed** unless marked Accepted. Each ADR gets its own file under
`docs/erp/project/adr/` when accepted; until then this register is the
record. Owner names are left for the sponsor to fill.

| ADR | Decision | Evidence found | Proposed decision | Status / owner |
| --- | --- | --- | --- | --- |
| ADR-001 | Odoo extension vs custom vs integration | [VERIFIED] Odoo 19 Community with two connected FastAPI apps | Path A: Odoo-based; connected apps keep Odoo as the system of record for every financial and stock fact; the C2P delivery store (SQLite) holds engagement knowledge only | **Accepted by evidence**; confirm |
| ADR-002 | Tenant model | [VERIFIED] one database per tenant, routed by subdomain | Keep database-per-tenant; the control plane never reads tenant data; multi-company inside a tenant only for a group of legal entities under one owner | Confirm |
| ADR-003 | Company / branch / department / warehouse | [VERIFIED] C2P has two legal companies; Jawhar stores are warehouses | Legal entity = `res.company`; store/branch = `stock.warehouse` for stock-holding branches, analytic plan "Branch" for non-stock; department = `hr.department` when HR is installed; cost centre = analytic plan | [DECISION] |
| ADR-004 | Financial source of truth | [VERIFIED] `account.move` for Jawhar invoices; CFO toolkit does not post | Odoo `account` is the only ledger; nothing else posts; e-invoicing reads posted moves | Confirm |
| ADR-005 | Inventory valuation | Unknown in code | Per tenant: jewellery = automated valuation, FIFO per serial (specific identification by lot); trading = FIFO or average; negative stock forbidden | [DECISION] finance manager |
| ADR-006 | Localisation | [VERIFIED] none installed by code; e-invoicing for UAE/KSA/PK exists | Install `l10n_ae` (+ `l10n_gcc_invoice`), `l10n_sa` (+ `l10n_sa_edi` for ZATCA), `l10n_pk` per tenant country; VAT rates and AML thresholds entered by the named finance manager, never defaulted in code | [DECISION] |
| ADR-007 | Workflow / approval engine | [VERIFIED] three product-specific approval patterns (maker-checker, digest-bound AI drafts, change requests) | Keep product patterns; a shared `x.approval` model only when a fourth need appears; discount, purchase and write-off thresholds via standard `sale`/`purchase` approval settings first | Confirm |
| ADR-008 | Integration strategy | [VERIFIED] Stripe, ZATCA, FBR, rate feed, ElevenLabs, Anthropic | Every integration registered in `architecture/INTEGRATION_REGISTER.md` with idempotency key and retry policy; webhooks dedupe on event id | Confirm |
| ADR-009 | Security and identity | [VERIFIED] Odoo sessions; HMAC SSO; JWT in zaki-server; Jawhar record rules tested | Odoo is the identity authority; MFA via `auth_totp` for managers; every `sudo()` justified in a comment and listed; cross-company negative tests per module | [DECISION] |
| ADR-010 | Deployment and DR | [VERIFIED] compose on one VPS; nightly backup workflow; staging separate for Jawhar | Define RPO/RTO; add restore drill; include SQLite stores in backups or retire them | [DECISION] |
| ADR-011 | Close and correction policy | Missing | Lock dates per company; corrections by reversal/credit note only; no write to posted moves | Confirm with finance |
| ADR-012 | Versions and dependencies | [VERIFIED] Odoo 19 Community, Postgres 15 (prod) / 16 (CI), Python per image, Node 22, React 18, Vite 5, MediaPipe 1.2.2 | Pin OCA modules by commit when adopted; record in each ADR | Confirm |

## Project decisions needing an owner

| ID | Decision | Why it matters | Recommendation |
| --- | --- | --- | --- |
| D-01 | Which product is the first ERP vertical slice: the **Mumtaz ERP tenant (financial spine on `Mumtaz_ERP`)** or the **C2P internal ERP** (CRM logic + project costing + intercompany)? | Determines the first module spec and sprint | C2P internal first: it is the group's own books, has the highest-risk finding (R1), and proves P2P/L2C on real volumes without a client in the loop |
| D-02 | Replace `mumtaz_financial_reports` with standard Odoo reports and OCA `mis_builder`? | Untested custom statutory output | Evaluate in Wave 1; keep only if the standard cannot produce the required format |
| D-03 | Retire one of the two AI provider layers (`mumtaz_ai` vs Jawhar's `services/provider.py`) | Duplicate code paths with different safety rules | Adopt the Jawhar policy (levels, grounding, restricted-data exclusion) platform-wide |
| D-04 | OCA adoption (assets, budgets, statement import, helpdesk, quality, payroll) | Licence (LGPL/AGPL) and maintenance | Allowed, pinned, one ADR per module |
| D-05 | Keep SQLite stores in `zaki-server` and the C2P delivery API, or move engagement state into Odoo / Postgres | Backup, isolation, single source of truth | Move to Postgres in Wave 1; Odoo stays the system of record |
| D-06 | Who is the named finance manager for VAT, AML, lock dates, valuation | Blueprint rule: no invented policy | Required before Wave 2 |
| D-07 | Branch model (warehouse vs analytic) | Data model | See ADR-003 |
| D-08 | Jawhar staging promotion cadence | Demo credibility | Promote `main` after each merged slice |
| D-09 | Which marketing site is canonical: `sites/mumtaz.digital/site`, `sites/delivery.mumtaz.digital/landing/index.html` or `platform/marketing`? | Three variants in git; see `REPO_MAP.md` | **Answered by evidence, 21 Nov 2026:** `platform/marketing` is the live source. Archiving the other two still needs a go-ahead. A server check on 22 Nov found the apex proxied to the ERP's Odoo instead (see P-10) |
| D-10 | Which ZAKI application is canonical: `sites/zaki.mumtaz.digital/static`, `sites/zaki.mumtaz.digital/node-app` or `platform/zaki`? | Three variants; four Odoo AI/CFO module families | **Answered by evidence, 21 Nov 2026:** `platform/zaki` is the live source. Retiring the other two still needs a go-ahead. Its back end answers finance requests without credentials (see P-11) |
| D-11 | Which price list is correct: $49/$199 (live site, 21 Nov 2026) or $149/$399/$999 (portal wizard per the previous README)? | Public and in-app prices disagree | One price list, one source file |
| D-12 | Move `faizy/`, `wordpress-sites/` and `c2p-delivery-system/` to their own repositories? | Unrelated products in a public repository that production pulls | Move, with a deployment plan first |
| D-13 | Fold `mumtaz_base` into `mumtaz_core`, and choose one brand source? | Two foundations, three brand sources | Yes, by migration script, tested per tenant database |

## Platform decisions (consolidation directive, 21 Nov 2026)

Raised by the platform consolidation work recorded in `docs/platform/`. They
carry the prefix **P-** so they cannot be confused with the D- series above
or with the infrastructure audit's own D- series
(`docs/infrastructure-audit/15_DECISIONS_AND_APPROVALS.md`). All are **open**
and need the owner. "Built so far" says what the code already assumes, so
that a different answer is known to cost a change.

| ID | Decision | Why it matters | Recommendation | Built so far |
| --- | --- | --- | --- | --- |
| P-01 | Is database-per-tenant (ADR-002) the only tenancy model, and is the company-per-org model (`mumtaz_org_config`, `mumtaz.org`) retired? | Two models and two public signup routes exist; only one leads to an isolated database | Yes. Retire `mumtaz_org_config` after counting its rows on the server | The registration journey uses `mumtaz.tenant` only |
| P-02 | Which control plane is kept, and where does it run? **Two exist** (server check, 22 Nov 2026): a FastAPI control panel on the production branch, whose front end nginx serves for `app.mumtaz.digital` (deleted from `main` in PR #124; no tests), and the Odoo modules on `main` (tested; never run on the server) | Building on the wrong one repeats the duplication this programme is meant to end | First check whether the FastAPI service is running and holds real tenants. If it holds none, keep the Odoo modules on a dedicated instance and database, and retire the FastAPI one with a recorded decision. If it holds real tenants, migrate them before retiring it | Odoo journey built and tested on `main`; nothing server-side |
| P-03 | Where is real provisioning enabled first, and what must be true beforehand? | It creates databases on the PostgreSQL server that holds client ledgers | A staging instance only, after verified backups (audit batch 2B) and a run of `scripts/tenant_journey_ci.sh` on that host | Off by default; needs `MUMTAZ_REAL_PROVISIONING=1` in the service environment |
| P-04 | Is the organization of record a standard `res.partner` in the control database? | Three organization-like models already exist (`mumtaz.org`, `mumtaz.organization`, `mumtaz.sme.profile`) | Yes; fold the others in or keep them for their own purpose (partner directory) | Approval of a registration request creates the partner and links the tenant to it |
| P-05 | What replaces the shared-secret single sign-on (`mumtaz_sso`, audit ODOO-01)? | One secret for every tenant means one leak opens every tenant | A secret or key pair per tenant, or OpenID Connect with the control plane as provider. Until then no SSO | SSO is in no install profile; first access is Odoo's one-time invitation link |
| P-06 | What does the Mumtaz ERP install profile contain, and how is localisation chosen? | The profile is the product. Today: CRM, sales, purchasing, inventory, accounting, financial reports; no chart of accounts | Add localisation by country (ERP backlog item 5, ADR-006); add branding only after the design tokens are agreed (P-14) | `bundle_mumtaz_erp` |
| P-07 | Trial and staging lifecycle: length, what happens at expiry, and whether staging tenants may send email or take payments | A database outlives its trial unless someone decides otherwise | 14 days; then suspend, archive after a notice period, delete only on a named person's approval; staging tenants send no customer email and take no payment | 14-day trial subscription; no expiry handling; no automatic deletion anywhere |
| P-08 | When is public registration opened, and with which protections? | An open form on a public site invites abuse | Only with captcha, email verification and a proxy rate limit; a person approves each request | Route exists, closed by default; creates a pending request only; hourly cap; honeypot |
| P-09 | One price list (extends D-11) | Four sources disagree: the older bundles (49/149/199/299), the website block added in PR #187 ($49/$199), the older static sites, the portal wizard | One source: `mumtaz.plan` in the control plane; the website reads it or shows no price | The trial plan is priced 0 |
| P-10 | Where does the Odoo website for `mumtaz.digital` run? | `docs/mumtaz-website/README.md` gives a command against the `Mumtaz_ERP` database; no decision records that choice | A dedicated instance and database (`docs/platform/MUMTAZ_WEBSITE_IMPLEMENTATION.md`) | Nothing deployed; live homepage untouched |
| P-11 | The single ZAKI architecture (extends D-03, D-10) | No existing implementation is safe to expose | ZAKI inside the tenant's Odoo (`mumtaz_zaki` + an AI core taken from Jawhar's governed stack), a thin client for the standalone site; retire the unauthenticated FastAPI backend | Nothing; catalogue status "planned" |
| P-12 | Marketplace topology | Listings must be visible across tenants; a per-tenant database cannot do that | One shared marketplace database; tenants connect by an authorised API; opt-in | Nothing; catalogue status "planned" |
| P-13 | Delivery OS as a subscribable product | It has no customer accounts, billing or tenant separation today | Keep the FastAPI foundation; evaluate tenancy and billing before any offer | Nothing; catalogue status "planned" |
| P-14 | Sign-off of the design tokens (extends D-13) | Nine sources use the superseded gold palette | Approve the token set in `docs/platform/MUMTAZ_DESIGN_SYSTEM.md`, then re-token website, theme and apps in that order | Nothing |
| P-15 | Remove customer and staff data from reusable and public code | A client's brand, a database name, staff emails and a client knowledge block sit in shared modules of a public repository | Move to system parameters or a private repository; list in `docs/platform/MUMTAZ_REPOSITORY_CONSOLIDATION.md` | Nothing |
| P-16 | Extend the module registry (owner, reusable, disposition, install profiles, checks) | The layer rule cannot see ownership, profiles or control-plane modules leaking into customer databases | Adopt in ratchet style, as `known_violations` works today (`docs/platform/MUMTAZ_MODULE_REGISTRY_REVIEW.md`) | One unit test guards the ERP profile's closure |
| P-17 | A separate PostgreSQL role per tenant database, and verified backups, before the first paying tenant | REPORTED: one role owns every database; no backup has been verified | Yes to both | Nothing |
