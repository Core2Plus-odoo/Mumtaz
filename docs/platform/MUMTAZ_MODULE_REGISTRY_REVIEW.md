# Mumtaz Module Registry Review

Reviewed at commit `ff1c797` (`main`, 21 Nov 2026). 60 Odoo modules: 58 in `addons/`, 2 in `faizy/odoo/addons/`.

## 1. Conclusion

- The six-layer model works for what it checks. Recomputed from all 60 manifests, the only upward dependency is `mumtaz_portal_routing → mumtaz_cfo_base`, which is the one entry in `known_violations`. No reusable module depends on an internal or venture module.
- The model ranks layers. It cannot see **who owns a module**, **which product it belongs to**, **which modules go into which kind of database**, or **dependencies written in code instead of the manifest**. Those four gaps are where the real problems are.
- The most serious consequence: control-plane modules are installed into customer databases. Five tenant-side modules pull `mumtaz_tenant_manager` (two also pull `mumtaz_control_plane`) into any database they are installed in, and four of the five existing bundles install at least one of them. This was confirmed by running the provisioner (section 5.6).
- Three bundles list `account_accountant`, an Enterprise module that does not exist in Odoo 19 Community. The provisioner skips it silently, so those bundles promise features they cannot deliver.
- Eight groups of modules overlap (portals, tenancy registries, APIs, AI, foundation, brand, websites, CFO). Each has a clear survivor, but none can be merged safely until someone records which modules are installed in which live database.

**Three highest-value fixes**

1. Record what each live database has installed (`installed_in`). Every merge, retirement and rename is blocked on it. No risk.
2. Add `owner` and `profiles` to the registry with existence and closure checks. Small, no runtime effect, and it turns the bundle defects into CI failures.
3. Fix the bundles and keep control-plane models out of tenant databases. A first clean profile, `mumtaz_erp`, is added in this branch (section 7.3).

## 2. Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code at `ff1c797`, or executed in this session. Execution is stated where it happened |
| **REPORTED** | Stated in a repository document or by an earlier session; not re-checked here |
| **PROPOSED** | A recommendation. Nothing has been changed |
| **UNKNOWN** | Could not be determined from the repository |

Rules for reading this document:

- Every "what it does", dependency, line count and file reference in sections 4–6 is **VERIFIED** by reading code unless a cell says otherwise.
- Every "owner", "reusable?" and "disposition" value is **PROPOSED**.
- Statements about what is installed on a live server are **REPORTED** or **UNKNOWN**. No server was inspected.
- `python3 scripts/module_registry.py --check` was run at `ff1c797` and printed `registry ok: 60 modules, 1 known layering violation(s)` (VERIFIED). No module was installed or tested for this review, apart from the provisioning run in section 5.6.

Related documents (not duplicated here): [`REPO_MAP.md`](../../REPO_MAP.md), [`registry.yaml`](../../registry.yaml), [`registry/classification.json`](../../registry/classification.json), [`docs/erp/architecture/MODULE_DEPENDENCY_MAP.md`](../erp/architecture/MODULE_DEPENDENCY_MAP.md), [`docs/erp/project/DECISION_REGISTER.md`](../erp/project/DECISION_REGISTER.md), [`docs/infrastructure-audit/06_ODOO_INSTANCES_AUDIT.md`](../infrastructure-audit/06_ODOO_INSTANCES_AUDIT.md).

## 3. Governance rules

These come from the platform consolidation directive. They apply to every change that follows from this review.

1. **Prefix.** A new reusable addon is named `mumtaz_*`. A customer-specific addon is not.
2. **No direct renames.** An installed module is never renamed in place. A rename needs (a) an inventory of every database where the module is installed, (b) a migration that moves `ir_model_data`, tables and foreign keys, and (c) a tested upgrade on a copy of each affected database.
3. **Customer code is not reusable code.** Anything that names a client, a client database, client staff or a client's chart of accounts belongs to that customer's deployment. It is kept out of every reusable profile.
4. **Layer rule (existing).** A module may depend only on its own layer or a lower one. CI enforces this through `scripts/module_registry.py --check`.
5. **No automatic change to a client deployment.** IG2 is an external client. Nothing here is applied to its database without compatibility testing and approval.

## 4. Module table

Versions omit the `19.0.` prefix. LOC is the registry's `python_lines`, which includes tests. Tests is the number of test files. CSV is the access file: Y, N, or "empty" (header only). Conf is the reviewer's confidence in the disposition: H high, M medium.

Short names: tm = `mumtaz_tenant_manager`, cp = `mumtaz_control_plane`, core = `mumtaz_core`, br = `mumtaz_branding`, sme = `mumtaz_sme_profile`, pr = `mumtaz_portal_routing`, j = `mumtaz_jewellery`.

Layer counts (VERIFIED): foundation 4, platform 18, product 12, edition 15, internal 9, venture 2.

### 4.1 Foundation (4)

| Module | Ver | Local deps | LOC | Tests | CSV | What it does | Owner | Reusable? | Disposition | Conf |
|---|---|---|---|---|---|---|---|---|---|---|
| mumtaz_core | 1.2.0 | – | 664 | 0 | Y | Per-company AI and text-to-speech credentials and feature toggles (`mumtaz.core.settings`), action log, daily credential pull, `auth=none` push endpoint, six groups the portals key on | platform-core | needs work: it is really an AI-settings module; platform URL default is hard-coded (`models/mumtaz_core_settings.py:10`) | split (groups and log stay; AI settings move to zaki-ai); keep+tests | H |
| mumtaz_base | 1.2.0 | – | 46 | 0 | empty | Adds unique `x_mumtaz_code` on `res.partner`; nothing else reads it | platform-core | yes | merge into mumtaz_core | H |
| mumtaz_branding | 1.0.0 | core | 95 | 0 | Y | `mumtaz.brand` record (logo, colours, email and report text). No code applies it; only Many2one references exist | platform-core | needs work: data only | keep; absorb mumtaz_theme and render from the record | H |
| mumtaz_theme | 1.0.0 | – | 23 | 0 | N | Fixed Mumtaz CSS and favicon; Google Fonts link on every page (`views/webclient_templates.xml:16-18`) | platform-core | no for white-label or Jawhar | merge into mumtaz_branding | H |

### 4.2 Platform (18)

| Module | Ver | Local deps | LOC | Tests | CSV | What it does | Owner | Reusable? | Disposition | Conf |
|---|---|---|---|---|---|---|---|---|---|---|
| mumtaz_tenant_manager | 1.0.0 | br | 900 | 0 | Y | `mumtaz.tenant`, `mumtaz.module.bundle`, provision wizard, 5-minute provisioning cron (active), dry-run or environment-gated real provisioner | platform-saas | yes, control database only; `erp.mumtaz.digital` default (`services/provisioning.py:302`); help text says `mumtaz.io` (`models/mumtaz_tenant.py:31`) | keep+tests | H |
| mumtaz_control_plane | 1.0.0 | tm | 1955 | 0 | Y | Plans, features, subscriptions, lifecycle crons, billing records, usage, feature-access service, ERP group toggling | platform-saas | yes | keep+tests | H |
| mumtaz_billing_stripe | 1.0.0 | cp | 804 | 0 | Y | Stripe client, webhook, card page, daily charge cron | platform-saas | yes | keep+tests before real charges | H |
| mumtaz_api_gateway | 1.0.1 | tm, core, cp | 343 | 0 | Y | API-key model, usage log, async job, six ping/health/auth stubs. `create()` hashes a generated key and discards the raw value (`models/api_key.py:40-46`), so a key is unusable until `rotate_key()` | platform-saas | yes | keep+tests, or retire-candidate (no business endpoint uses it) | M |
| mumtaz_api | 1.0.0 | core | 173 | 0 | N | Public CORS lead API for the static site (`/api/mumtaz/v1/demo`, `/contact`) creating `crm.lead` | website | no: origins fixed to mumtaz.digital (`controllers/api_v1.py:10-11`) | merge into mumtaz_website_builder, or retire with the static site | H |
| mumtaz_sso | 1.0.0 | – | 109 | 0 | N | HMAC token login at `/mumtaz/sso`, `auth=none` | platform-saas | yes; Critical flaw (REPORTED, ODOO-01) | keep+tests after repair | H |
| mumtaz_subdomain_routing | 1.0.0 | tm | 297 | 0 | N | `post_load` patch of `http.db_filter`; host to tenant database via the control database | platform-saas | yes; base domain default at `patch.py:39-40` | keep+tests | H |
| mumtaz_portal_routing | 1.0.0 | core, tm, mumtaz_cfo_base | 833 | 1 | Y | Login-redirect override, `/mumtaz/portal/*` dashboards, `/mumtaz/api/org`. Access file grants `res.users` read to the analyst group (`security/ir.model.access.csv:2`) | platform-saas | needs work: reads five other modules' models behind try/except | merge into mumtaz_app_portal | H |
| mumtaz_app_portal | 1.0.0 | core, pr | 654 | 1 | empty | `/app*` customer app (ERP stats, ZAKI, marketplace, account) | platform-saas | needs work: 12+ undeclared models; mailto addresses hard-coded (`views/app_account.xml:112,119,128`) | keep+tests (portal survivor) | H |
| mumtaz_org_config | 1.0.0 | core, br, pr | 322 | 0 | Y | `mumtaz.org`: company-per-organisation tenancy; public signup creates a `res.company` (`models/mumtaz_org.py:126-138`) | platform-saas | no: contradicts ADR-002; `.mumtaz.digital` hard-coded (`mumtaz_org.py:85`) | retire-candidate after migrating to `mumtaz.tenant` | M |
| mumtaz_organization | 1.0.1 | – | 309 | 0 | Y | Public partner-organisation directory `/org/<slug>` and `mumtaz.sme.signup` join requests | marketplace | needs work: GCC copy hard-coded (`views/org_portal_templates.xml:317,433`); unthrottled public creates (REPORTED) | keep+tests; not a duplicate of `mumtaz.org` | M |
| mumtaz_sme_profile | 1.1.0 | br, tm | 226 | 0 | Y | `mumtaz.sme.profile` (legal and tax data, onboarding stage, a plan selection that duplicates the control plane) | platform-saas | needs work: pulls tm into any database it is installed in | merge into tm | M |
| mumtaz_onboarding | 1.0.0 | sme | 172 | 0 | Y | Per-company 12-task setup checklist | platform-saas | needs work: a tenant-side feature chained to control-database models | split: drop the sme dependency; it then becomes erp-generic | M |
| mumtaz_portal | 1.0.0 | – | 12 | 0 | N | Empty manifest | platform-saas | n/a | retire-candidate | H |
| mumtaz_customer_portal | 1.0.0 | – | 21 | 0 | empty | QWeb overrides of portal home, invoice and order; e-invoice QR via `hasattr` (`views/portal_invoice_override.xml:15,28`) | erp-generic | yes | keep | M |
| mumtaz_vendor_portal | 1.0.0 | – | 488 | 0 | empty | `/vendor/*`: purchase orders, RFQ reply, bill upload, payments, all via `sudo()` | erp-generic | needs work: literal "AED" (`views/portal_vendor_dashboard.xml:62`, `portal_vendor_payments.xml:78`) | keep+tests | H |
| mumtaz_website | 1.0.0 | – | 55 | 0 | N | `/mumtaz*` marketing pages; reads `mumtaz.plan` softly | website | no | retire-candidate after cutover | H |
| mumtaz_website_builder | 1.0.0 | – | 211 | 1 | N | Website Builder snippets, `/mumtaz-native-preview`, CRM tags, demo-form validation | website | no, by design | keep | H |

### 4.3 Product (12)

| Module | Ver | Local deps | LOC | Tests | CSV | What it does | Owner | Reusable? | Disposition | Conf |
|---|---|---|---|---|---|---|---|---|---|---|
| mumtaz_ai | 1.2.0 | core | 450 | 0 | Y | Chat sessions, keyword intent router, OpenAI and Anthropic providers | zaki-ai | yes; no tests or policy | merge into one ZAKI stack (D-03) | M |
| mumtaz_voice | 1.0.0 | mumtaz_ai, core, cp | 665 | 0 | Y | Voice CFO: `mumtaz.cfo.service` builds context from `account`; text-to-speech; sessions | zaki-ai | needs work: hard-depends on cp, so tm and cp land in the tenant database | merge into mumtaz_ai; drop cp | M |
| mumtaz_zaki | 1.0.0 | – | 418 | 1 | Y | `zaki.connector.get_snapshot` for the external ZAKI backend, hourly briefing emails, board pack | zaki-ai | needs work (all-company figures, REPORTED) | keep+tests (ZAKI bridge survivor) | M |
| mumtaz_cfo_base | 1.0.0 | sme, tm | 320 | 0 | Y | CFO workspace and categories; entitlement via cp if present | zaki-ai | needs work: hard-depends on tm | keep; cut tm | M |
| mumtaz_cfo_ingestion | 1.0.0 | mumtaz_cfo_base | 282 | 0 | Y | CSV upload batch, mapping profile, data source; `auto_install: True` | zaki-ai | yes | merge into one `mumtaz_cfo`; remove auto_install | H |
| mumtaz_cfo_transactions | 1.0.0 | mumtaz_cfo_ingestion | 332 | 0 | Y | Staged transactions and review queue; `auto_install: True` | zaki-ai | yes | merge into `mumtaz_cfo` | H |
| mumtaz_cfo_toolkit | 1.0.0 | three cfo modules | 18 | 0 | N | Meta-installer | zaki-ai | n/a | retire-candidate | H |
| mumtaz_super_toolkit | 1.0.0 | mumtaz_base, mumtaz_cfo_toolkit | 17 | 0 | N | Meta-installer | zaki-ai | n/a | retire-candidate | H |
| mumtaz_einvoicing | 1.0.0 | – | 2197 | 0 | Y | UAE QR, KSA ZATCA, PK FBR on `account.move`; the `action_post` override does network I/O; two crons; `/api/v1/einvoice/*` | erp-generic | needs work: untested statutory output; country chosen from the company (fine) | keep+tests; split per country | H |
| mumtaz_financial_reports | 1.0.0 | – | 371 | 0 | N | OWL profit and loss, balance sheet, trial balance, aged partners, with drill-down, scoped to `env.company` | erp-generic | yes; in production for IG2 (REPORTED) | keep+tests (D-02 open) | H |
| mumtaz_crm_starter | 1.0.0 | – | 31 | 0 | N | Seven `crm.stage` records and two lead fields | erp-generic | yes | keep | H |
| mumtaz_marketplace | 1.0.0 | sme, cp | 735 | 1 | Y | Listings, categories, inquiries, purchase-order-to-RFQ wizard, entitlement | marketplace | needs work: hard-depends on cp and tm; cross-company write (REPORTED, ODOO-08) | keep+tests | M |

### 4.4 Edition — Jawhar (15)

All are version 1.0.0, proposed owner `jawhar`.

| Module | Local deps | LOC | Tests | CSV | What it does | Reusable? | Disposition | Conf |
|---|---|---|---|---|---|---|---|---|
| mumtaz_jewellery | – | 1798 | 5 | Y | Piece fields on lot and product, gold rate, pricing, old-gold exchange, xlsx import | yes; VAT default 5 in `data/config.xml:6-8` (configurable) | keep | H |
| mumtaz_jewellery_vip | j | 803 | 4 | Y | Client tiers, global `res.partner` rule, occasions, approval memos, access log | yes | keep | H |
| mumtaz_jewellery_owner | vip | 218 | 1 | Y | Owner cards | yes | keep | H |
| mumtaz_jewellery_sale | j | 1579 | 4 | empty | Line pricing with frozen rate, discount limit, counter commit | needs work: uses `jewellery.approval.memo` (vip) without depending on it (`models/sale_order.py:296`) | keep; add the dependency | H |
| mumtaz_jewellery_crm | vip, sale | 764 | 1 | Y | Trays, viewing, reservation; public tray link | yes | keep | H |
| mumtaz_jewellery_ai | crm, owner | 1395 | 1 | Y | Governed agents, runs, drafts; own Anthropic provider (`services/provider.py:18,24`) | yes | keep; AI policy survivor (D-03) | H |
| mumtaz_jewellery_kiosk | crm, ai | 586 | 1 | Y | Public kiosk endpoints and requests | yes | keep | H |
| mumtaz_jewellery_api | seven Jawhar modules | 2302 | 1 | Y | `/jawhar/v1` JSON door and audit | yes | keep | H |
| mumtaz_jewellery_outreach | ai, api | 737 | 1 | N | Outreach drafts, consent, occasions cron (inherits only) | yes | keep | H |
| mumtaz_jewellery_aml | sale, vip, owner, api | 741 | 1 | Y | AML events and KYC flags | yes | keep | H |
| mumtaz_jewellery_stores | vip, owner, api | 765 | 1 | Y | Stores on warehouses, transfers, gold reconciliation | yes | keep | H |
| mumtaz_jewellery_channels | kiosk, owner, api | 443 | 1 | Y | Rate feed (hourly, draft only), web shelf | yes | keep | H |
| mumtaz_jewellery_client | sale, crm, kiosk, outreach, api | 559 | 1 | Y | Client-app sessions | yes | keep | H |
| mumtaz_jewellery_website | j | 285 | 1 | Y | Demo-request door for the vendor's own site, creating `crm.lead` | needs work: depends on `mumtaz_jewellery` but uses nothing from it except a parameter key string | keep; drop the dependency; belongs to the marketing-site profile | H |
| mumtaz_jewellery_demo | twelve Jawhar modules | 815 | 0 | N | `post_init_hook` seeder; sets `client_code_echo=1` (`hooks.py:636`) | no (demo only) | keep; forbid in every production profile | H |

### 4.5 Internal (9)

| Module | Ver | Local deps | LOC | Tests | CSV | What it does | Owner | Reusable? | Disposition | Conf |
|---|---|---|---|---|---|---|---|---|---|---|
| c2p_project_tracker | 1.0.0 | – | 2492 | 6 | Y | Portfolio and delivery layers on `project`, RAID, change requests, split and margin | c2p-customer | no: the hook hard-codes project ids and client names (`hooks.py:9-22`) and ten staff email addresses (`hooks.py:23-33`); "C2P Solutions" in views | keep; move the hook data out of code | H |
| c2p_command_center | 1.0.0 | – | 452 | 1 | N | One-RPC owner dashboard across CRM, projects, receivables, crons | c2p-customer | no: a C2P mailbox address (`models/command_center.py:7`), board name (`:8`), UTC+4 (`:9`), stage names (`:148`), AED fallback (`:183,219`), cron-name match (`:341`) | keep; constants to system parameters | H |
| c2p_proposal | 17.0.0 (full string; not a `19.0.` version) | – | 1402 | 0 | Y | Proposal wizard and branded PDF on `sale.order`; C2P service catalogue | c2p-customer | no: C2P methodology and text in Python (`models/sale_order.py:365,597,718`, `wizards/proposal_wizard.py:128-129`) | keep+tests | H |
| c2p_appointment | 1.0.0 | – | 582 | 0 | Y | Public booking pages creating a lead and a calendar event | c2p-customer | needs work: C2P text in `data/mail_template.xml:17,50,52` and `controllers/main.py:134,139,143`; otherwise generic | keep; candidate to generalise later; REVIEW-05 open | M |
| c2p_master_agent | 1.0.0 | – | 272 | 0 | Y | Transient chat form calling Ollama or Anthropic over Odoo data | c2p-customer | no: staff names, client names, an active proposal and a price list are in source (`models/master_agent.py:7-75`) | move out of repo (private); REVIEW-05 open | H |
| mumtaz_lead_scraper | 1.0.0 | – | 2666 | 1 | Y | Scraper sources, jobs, records; DIFC register parser; overrides `mail.message` | internal-tooling | needs work: DIFC and Dubai defaults (`services/difc_parser.py:689`, `models/lead_scraper_source.py:28`); SSRF (REPORTED) | keep internal; remove from tenant portals | M |
| mumtaz_lead_nurture | 1.0.0 | mumtaz_lead_scraper | 1494 | 1 | Y | Nurture campaigns, steps, rules, WhatsApp providers, "ERP need" tags | internal-tooling | needs work: seed data is for selling Odoo ERP | keep internal | M |
| mumtaz_media_buying | 1.0.4 | – | 1045 | 1 | Y | Media vendors, outlets, rate cards, plans to sales order and purchase orders; serves `/mumtaz_ceo_dashboard/data` | erp-generic (media industry pack) | needs work: seed targets the IG2 database by name (`scripts/seed_demo.py:9`); PKR fallback (`controllers/dashboard.py:189`); owns a route in another module's namespace (`dashboard.py:41`) | keep+tests | M |
| mumtaz_ceo_dashboard | 1.1.2 | – | 45 | 0 | N | OWL dashboard with built-in sample data; live only if media_buying answers | ig2-customer as shipped | no: IG2 brand names (`static/src/js/ceo_dashboard.js:18,20`), PKR (`:43,54,110,162`), fixed date (`:29`), menu open to every internal user (`views/ceo_dashboard_views.xml:21`) | merge into mumtaz_media_buying after de-branding | H |

### 4.6 Venture (2)

| Module | Ver | Local deps | LOC | Tests | CSV | What it does | Owner | Reusable? | Disposition | Conf |
|---|---|---|---|---|---|---|---|---|---|---|
| faizy_core | 1.7.1 | – | 3478 | 1 | Y | Family-care: workers, services, orders, subscriptions, wallet, WhatsApp queue | faizy | no (PKR and Pakistan throughout) | move out of repo | H |
| faizy_website | 1.5.0 | faizy_core | 646 | 0 | N | Public site, signup, `/my/*` portal; takes over `/` | faizy | no | move out of repo | H |

### 4.7 Not on `main`

- **Pharma:** no module on `main`. The code is on `pharma-*` branches (REPORTED).
- **Delivery OS:** FastAPI, not Odoo; no module.
- **IG2:** no IG2-only module is on `main` except `mumtaz_ceo_dashboard` as shipped. `c2p_pk_vouchers`, the IG2 report variants and third-party `base_accounting_kit` are not on `main` (REPORTED).

## 5. Layering findings

### 5.1 The manifest rule holds (VERIFIED)

Recomputed from all 60 manifests. The only upward dependency is `mumtaz_portal_routing → mumtaz_cfo_base` (platform → product), which matches `known_violations`. Nothing outside the internal and venture layers depends on them.

### 5.2 What the rule cannot see

It ranks layers, not products. A dependency between two products in the same layer passes silently. A dependency from Jawhar to Pharma would pass too, once Pharma is classified as an edition.

Current same-layer oddities (VERIFIED):

- `mumtaz_branding → mumtaz_core`: branding requires the AI-settings module.
- `mumtaz_super_toolkit → mumtaz_base`.

### 5.3 Soft and undeclared dependencies (VERIFIED)

These are references in code to models, routes or groups owned by a module that is not in `depends`.

| From | To (not in `depends`) | Where | Kind |
|---|---|---|---|
| mumtaz_tenant_manager | `mumtaz.sme.profile` | `models/mumtaz_tenant.py:239,245,270` | circular: sme depends on tm; unguarded in `action_create_sme_profile` |
| mumtaz_tenant_manager | `mumtaz.cfo.workspace` | `models/mumtaz_tenant.py:259,276` | circular and upward |
| mumtaz_control_plane | `mumtaz.core.settings` | `models/feature_access_service.py:130` | `in self.env` |
| mumtaz_cfo_base | cp models | `models/cfo_workspace.py:85,112,144,189` | `in self.env`; the entitlement check passes when cp is absent |
| mumtaz_portal_routing | cp | `controllers/routing.py:241,252,273` | try/except |
| mumtaz_portal_routing | marketplace | `routing.py:369,512,548,563`; `models/res_users_portal.py:26-27` | try/except, group xmlids |
| mumtaz_portal_routing | lead_scraper, lead_nurture (internal layer) | `routing.py:341-356,379` | try/except; platform reaching into internal |
| mumtaz_portal_routing | mumtaz_ai, cfo_transactions, `crm` | `routing.py:457`, `437`, `323` | try/except |
| mumtaz_portal_routing | route `/mumtaz/cfo` | `views/portal_zaki_template.xml:19,90,157,211` | no controller defines it; dead links |
| mumtaz_app_portal | `account`, `sale`, `purchase`, `stock`, `hr_holidays`, `crm` | `controllers/app.py:153,200,211,221,238,255,337` | undeclared standard apps |
| mumtaz_app_portal | cp, lead_*, mumtaz_ai, marketplace, cfo_transactions | `app.py:77,546`; `346-363`; `433`; `480-506`; `414` | try/except |
| mumtaz_api | `lead.nurture.campaign` | `controllers/api_v1.py:111` | try/except |
| mumtaz_website | `mumtaz.plan` | `controllers/main.py:20` | try/except |
| mumtaz_voice | `sale.order` | `services/cfo_service.py:157` | `in self.env` |
| mumtaz_zaki | `hr.payslip`, `crm.lead` | `models/zaki_connector.py:50,56` | `in self.env`. No model `hr.payslip` exists in Odoo 19.0 Community (VERIFIED, section 7.1), so the payroll figure is always skipped on Community |
| mumtaz_customer_portal | mumtaz_einvoicing fields | `views/portal_invoice_override.xml:15,28` | `hasattr` in QWeb |
| mumtaz_ceo_dashboard | route owned by mumtaz_media_buying | `static/src/js/ceo_dashboard.js:136` | undeclared in both directions |
| mumtaz_jewellery_sale | `jewellery.approval.memo` (vip) | `models/sale_order.py:296` | **hard**, unguarded, on the availability-check path |

Because of the first two rows, the statement "No dependency cycles" in `MODULE_DEPENDENCY_MAP.md` is true for manifests and false in code.

Redundant guards (the dependency is declared but the code still checks for the model): `mumtaz_marketplace/models/marketplace_access.py:45`, `marketplace_listing.py:92,110`, `marketplace_inquiry.py:48`, `mumtaz_voice/services/voice_service.py:81`, `mumtaz_jewellery_demo/hooks.py:612,633`.

`mumtaz_app_portal` reads `mumtaz.sme.profile` and `mumtaz.subscription` (`app.py:67,77`) and `account.move` (`app.py:153`) from one environment. The portal therefore assumes that control-plane records and tenant ledgers share a database. That contradicts ADR-002 (database per tenant).

### 5.4 Questionable layers (PROPOSED reclassification)

- `mumtaz_ceo_dashboard` is not "internal" (C2P group tooling). It is a customer-branded artefact.
- `mumtaz_media_buying` is a reusable industry pack, not internal.
- `mumtaz_lead_scraper` and `mumtaz_lead_nurture` are correctly classed as business-development tooling, but both platform portals expose them to tenants as a feature. Either the layer or the portals is wrong.
- `mumtaz_website_builder`, `mumtaz_website` and `mumtaz_api` are the vendor's marketing site, not platform. They must never reach a tenant.
- `mumtaz_cfo_*` is the ZAKI product: the portal maps the CFO groups to the "ZAKI AI Portal" (`mumtaz_portal_routing/models/res_users_portal.py:13-16`). "Product" is the right layer, but the tm dependency makes it uninstallable in a clean tenant.
- `mumtaz_customer_portal`, `mumtaz_vendor_portal` and `mumtaz_onboarding` are tenant ERP features, not platform.
- `mumtaz_core` is AI settings. `mumtaz_organization` belongs with marketplace.
- `mumtaz_jewellery_website` is vendor marketing sitting in the edition layer.

### 5.5 `auto_install` (VERIFIED)

Only `mumtaz_cfo_ingestion` and `mumtaz_cfo_transactions` set it. Installing `mumtaz_org_config`, `mumtaz_app_portal` or `mumtaz_portal_routing` therefore brings `mumtaz_cfo_base` (hard dependency) and, through auto-install, both others, plus sme, tm, br and core. tm brings its active 5-minute provisioning cron.

### 5.6 Control plane leaking into tenant databases

**From manifests (VERIFIED).** `mumtaz_sme_profile`, `mumtaz_onboarding`, `mumtaz_cfo_base`, `mumtaz_marketplace` and `mumtaz_voice` each pull tm into whatever database they are installed in. The last two also pull cp. Four of the five existing bundles install at least one of them.

**From execution (VERIFIED on a local Odoo 19 rig, 21 Nov 2026).** The existing real provisioner was run with the `starter` bundle against a throwaway control database:

| Check | Result |
|---|---|
| Isolated PostgreSQL database created | Yes |
| Administrator could sign in with the given login | Yes; a wrong password was refused |
| Mumtaz modules installed in the tenant database | `mumtaz_base`, `mumtaz_branding`, `mumtaz_core`, `mumtaz_onboarding`, `mumtaz_sme_profile`, **`mumtaz_tenant_manager`** |
| `mumtaz_tenant` table present in the tenant database | Yes (0 rows) |
| `mumtaz_module_bundle` rows in the tenant database | 5 — the full bundle list with prices |

`mumtaz_tenant_manager` was not in the bundle. It arrived because `mumtaz_sme_profile` depends on it. So a customer database provisioned from today's `starter` bundle holds the tenant registry model, the bundle price list and the provisioning cron. This confirms the manifest finding.

### 5.7 Jawhar and the platform (VERIFIED)

No `mumtaz_jewellery*` manifest depends on a foundation or platform module. For a control plane to provision, brand and bill a Jawhar tenant, the following are needed (PROPOSED):

1. A `jawhar` bundle. None exists.
2. A sign-on bridge in the tenant. No bundle includes `mumtaz_sso`, although provisioning plants its secret; and `mumtaz_sso` must be repaired first (ODOO-01).
3. A thin tenant-side bridge, for example `mumtaz_jewellery_platform`, depending only on `mumtaz_jewellery` plus a small tenant-agent module (not tm or cp). It would hold the tenant code and token, read entitlements, gate Jawhar agents, report usage and apply brand values.
4. Brand rendering, which does not exist anywhere today.
5. Entitlements fetched over an API, because `feature_access_service` currently resolves `mumtaz.tenant` locally.

## 6. Overlap groups and survivors (PROPOSED)

| Group | What each member really is | Survivor | Migration a merge needs |
|---|---|---|---|
| **Portals** | `mumtaz_portal`: nothing. `mumtaz_portal_routing`: login redirect, `/mumtaz/portal/*`, non-stored `res.users.mumtaz_portal_type`. `mumtaz_app_portal`: `/app*`, where `PORTAL_URLS` already sends ERP, ZAKI and marketplace users (`res_users_portal.py:31-36`). The customer and vendor portals serve the tenant's own partners, a different audience | `mumtaz_app_portal` for SaaS subscribers. Keep the customer and vendor portals separate under erp-generic | Neither SaaS portal has tables. Move the override and the admin page; redirect `/mumtaz/portal/*`; QWeb xmlids and one access row disappear on uninstall; drop the cfo_base dependency. `mumtaz_portal` only needs its module row removed where installed |
| **Tenancy registries** | `mumtaz.tenant`: database per tenant. `mumtaz.org`: company per organisation in one database. `mumtaz.sme.profile`: legal profile hanging off the tenant. `mumtaz.organization`: partner directory, a different concept | `mumtaz.tenant` (ADR-002) | Map `mumtaz.org` rows to tenants (slug, admin, plan, state, trial, brand, domain); drop `res.company.mumtaz_org_slug` and `mumtaz_org_id`; companies created by signup stay. Fold `mumtaz.sme.profile` into tm by reassigning `ir_model_data.module` and the `mumtaz_cfo_workspace` and `mumtaz_onboarding_checklist` foreign keys; pick one plan field. Row counts are UNKNOWN |
| **APIs** | `mumtaz_api`: public lead forms. `mumtaz_api_gateway`: key infrastructure with stub routes. `mumtaz_einvoicing` controller: `/api/v1/einvoice/*` with session auth, sharing the gateway's prefix but not its decorator. `mumtaz_jewellery_api`: `/jawhar/v1`, session, audited. Three more ad-hoc JSON routes exist (zaki, voice, financial reports) | No single survivor. Jawhar's door is the pattern; the gateway is the only key-auth candidate; fold `mumtaz_api` into the website module | The gateway holds `mumtaz_api_key`, `mumtaz_api_usage_log`, `mumtaz_async_job`. `mumtaz_api` has no data, but its URL is called by `sites/mumtaz.digital/site` |
| **AI** | `mumtaz_ai`: chat and providers. `mumtaz_voice`: a second CFO context builder and text-to-speech. `mumtaz_zaki`: bridge for the external app. `mumtaz_jewellery_ai`: the only governed and tested stack. `c2p_master_agent`: a fifth, ungoverned path | Policy and provider: `mumtaz_jewellery_ai`, extracted to a shared `mumtaz_ai_core` and renamed only with a migration. Tenant bridge: `mumtaz_zaki` | `mumtaz_ai_session`, `mumtaz_ai_message`, `mumtaz_voice_session`, `mumtaz_voice_message`; credentials in `mumtaz_core_settings` versus Jawhar's parameters. Extraction must keep the `jewellery.ai.*` model names, which are tested and audited |
| **Foundation** | `mumtaz_base`: one partner field. `mumtaz_core`: AI settings, log, groups | `mumtaz_core` | Move the field; pre-migration `UPDATE ir_model_data SET module='mumtaz_core' WHERE module='mumtaz_base'`; keep the column and constraint names; remove the dependency in `mumtaz_super_toolkit` and the name in all five older bundles |
| **Brand** | `mumtaz_branding`: a record nobody renders. `mumtaz_theme`: static CSS and Google Fonts. `docs/design/brand-tokens-v3/tokens.css`: design tokens | `mumtaz_branding`, with the theme assets moved in and driven by the record | The theme has no tables; only a view and asset xmlids move. The branding → core dependency direction should flip |
| **Websites** | `mumtaz_website`: controller pages. `mumtaz_website_builder`: native blocks, tested. `mumtaz_jewellery_website`: Jawhar demo-request door. Three static copies outside Odoo (D-09) | `mumtaz_website_builder`. Keep the Jawhar door as a satellite without its jewellery dependency | Retire `mumtaz_website` after cutover (no tables). `jewellery.demo.request` rows and the tag stay |
| **CFO** | Stack A: `mumtaz_cfo_base`, `_ingestion`, `_transactions` — staging uploaded files, never posting. Stack B: `mumtaz_voice` and `mumtaz_zaki` — reading the live ledger. Two installer shells | A becomes one `mumtaz_cfo`. B collapses onto `mumtaz_zaki` | Same-named models keep their tables; reassign `ir_model_data.module` for three modules; remove auto_install; rebind the two CFO groups |

None of these merges may start before the installed-module inventory (section 9, action 1) exists, and each is subject to rule 2 in section 3.

## 7. Installation profiles

### 7.1 Standard apps in Odoo 19.0 Community (VERIFIED)

Checked against an Odoo 19.0 Community checkout (head `da89d33`, 21 Nov 2026) by listing its `addons/` directory.

| Module | In Odoo 19.0 Community? |
|---|---|
| `account_accountant` | **Absent** (Enterprise) |
| `hr_payroll` | **Absent** (Enterprise); no model `hr.payslip` anywhere in the Community tree |
| `l10n_ae`, `l10n_sa`, `l10n_sa_edi`, `l10n_gcc_invoice`, `l10n_pk` | Present |
| `sale`, `sale_management`, `purchase`, `stock`, `account`, `crm`, `contacts`, `analytic` | Present |
| `hr`, `project`, `mrp`, `portal`, `calendar`, `utm` | Present |
| `website`, `website_crm`, `website_blog` | Present |

### 7.2 Profiles (PROPOSED)

A profile is the set of modules that may be installed in one kind of database.

**1. control-plane.**
`base, web, mail` → `mumtaz_core` → `mumtaz_branding` → `mumtaz_tenant_manager` → `mumtaz_control_plane` → `mumtaz_billing_stripe` → `mumtaz_sme_profile` → `mumtaz_api_gateway` (optional) → `mumtaz_subdomain_routing` → `mumtaz_theme`.
Leave out the portals and `mumtaz_org_config` until they are decoupled (section 5.5). `app.mumtaz.digital` today is a static portal whose API was deleted (REPORTED). Which Odoo database is the control database is UNKNOWN.

**2. mumtaz-erp-tenant.**
- Standard: `base, web, mail, contacts, account, sale_management, purchase, stock, crm, portal`; optional `hr, project, mrp, website`.
- Localisation by company country: AE `l10n_ae, l10n_gcc_invoice`; SA `l10n_sa, l10n_gcc_invoice` (plus `l10n_sa_edi` or `mumtaz_einvoicing`, not both); PK `l10n_pk`.
- Mumtaz, target state: `mumtaz_theme, mumtaz_sso, mumtaz_crm_starter, mumtaz_financial_reports, mumtaz_customer_portal`; optional `mumtaz_vendor_portal` (after the AED fix), `mumtaz_einvoicing` (after tests), `mumtaz_zaki`.
- Forbidden today: sme, onboarding, cfo, marketplace, voice (all drag tm or cp), anything `c2p_*`, lead_*, the website modules, `mumtaz_jewellery_demo`.
- The first implemented cut of this profile is the `mumtaz_erp` bundle in section 7.3. It is narrower than the target: it leaves out `mumtaz_theme` and `mumtaz_sso` until they are fixed.

**3. jawhar-tenant.**
`stock, sale_management, account, crm` plus localisation, then in the `jewel_ci.sh` order: `mumtaz_jewellery, _vip, _owner, _sale, _crm, _ai, _kiosk, _api, _outreach, _aml, _stores, _channels, _client`. Add the sign-on bridge and the future platform bridge (section 5.7). Exclude `_website` and `_demo`.

**4. zaki-standalone.**
Not a sensible standalone Odoo profile. ZAKI is an external app with three implementations (D-10). On the Odoo side it is an add-on to profile 2: `account` + `mumtaz_zaki`, optionally `mumtaz_core` + `mumtaz_ai`. A file-upload mode for customers without an ERP would be the merged `mumtaz_cfo`, once it no longer needs tm.

**5. marketplace.**
Listings must be visible across tenants, which a per-tenant database cannot do. It therefore belongs in one shared database (the control database or its own): control-plane profile + `sale, purchase` + `mumtaz_marketplace` + `mumtaz_organization` + `mumtaz_vendor_portal`. Tenants connect by API. This needs an owner decision.

**6. c2p-deployment (`Mumtaz_C2P`).**
`crm, project, sale_management, account, hr, calendar, website, website_blog, utm` + `l10n_ae, l10n_pk` + `c2p_project_tracker, c2p_command_center, c2p_proposal, c2p_appointment, c2p_master_agent` (REPORTED as installed). Probably the two lead modules (UNKNOWN). Not on `main`: 25 CRM server actions held only in the database (REPORTED).

**7. ig2-deployment (`Mumtaz_IG2`).**
`account, sale, purchase`, a Pakistan localisation (inferred), `mumtaz_financial_reports` (on `main`; REPORTED as used). Not on `main` (REPORTED): `c2p_pk_vouchers`, the IG2 report variants (branch `claude/resume-help-95ne9v`), third-party `base_accounting_kit` (not in the repository; version pin unrecorded). Whether `mumtaz_media_buying` and `mumtaz_ceo_dashboard` are installed is UNKNOWN; the seed target and the branding suggest they were built for it. `c2p_pk_vouchers` carries a C2P prefix for an IG2 or Pakistan-generic function. This profile describes what exists; it authorises no change to the client's database.

**8. faizy.**
`base, mail, contacts, product, account, website, portal` → `faizy_core` → `faizy_website`. `faizy_ai` is reported but not on `main`.

**9. marketing-website.**
`website, crm, website_crm` → `mumtaz_website_builder`; `mumtaz_jewellery_website` after its dependency is dropped; `mumtaz_api` only while the static site posts to it.

### 7.3 New install profile `mumtaz_erp` (added in this branch)

File: `addons/mumtaz_tenant_manager/data/mumtaz_bundle_data.xml`, record `bundle_mumtaz_erp` (VERIFIED by reading the file on the working branch):

```xml
<record id="bundle_mumtaz_erp" model="mumtaz.module.bundle">
    <field name="name">Mumtaz ERP (General)</field>
    <field name="code">mumtaz_erp</field>
    <field name="sequence">5</field>
    <field name="description">General business ERP on standard Odoo 19 Community: contacts, CRM, sales, purchasing, inventory, accounting and financial reports.</field>
    <field name="base_modules">base,mail,contacts,crm,sale_management,purchase,stock,account,mumtaz_financial_reports</field>
    <field name="optional_modules">hr,project,mrp,mumtaz_crm_starter,mumtaz_customer_portal</field>
    <field name="monthly_price">0</field>
    <field name="max_users">0</field>
</record>
```

What it deliberately leaves out, and why:

| Left out | Reason |
|---|---|
| Every control-plane module (`mumtaz_tenant_manager`, `mumtaz_control_plane`, and anything that pulls them: sme, onboarding, cfo, marketplace, voice) | A customer database must not hold the tenant registry or the price list (section 5.6) |
| `mumtaz_core`, `mumtaz_branding`, `mumtaz_theme` | Until they are reworked: `mumtaz_core` is an AI-settings module with a daily credential pull from a control panel that is not in the repository; `mumtaz_theme` ships a fixed palette and a third-party font link; nothing renders `mumtaz.brand` |
| `mumtaz_sso` | Until the shared-secret flaw (ODOO-01) is fixed |
| Localisation | Chosen by company country at provisioning; not yet wired |

Every name in `base_modules` and `optional_modules` exists on disk or in Odoo 19.0 Community (section 7.1). The price is 0 until the price list is decided (D-11). The record is `noupdate`, so an existing control database receives it on upgrade only if the xmlid is new, which it is.

### 7.4 Today's five older bundles against the profiles (VERIFIED)

- `account_accountant` appears in `finance`, `ai_cfo` and `enterprise_partner`. It is absent from Odoo 19.0 Community (section 7.1) and is silently skipped, because `_install_modules` installs only what it finds (`services/provisioning.py:253-262` at `ff1c797`). The "Finance" bundle description promises budgeting and reconciliation it cannot deliver.
- Every older bundle installs `mumtaz_base` (merge candidate), `mumtaz_core` and `mumtaz_branding`.
- `starter`, `growth` and `enterprise_partner` install sme and onboarding, so tm lands in the tenant. `ai_cfo` and `enterprise_partner` install `mumtaz_voice`, so cp lands too.
- No older bundle contains `mumtaz_sso`, `mumtaz_theme`, any localisation, `mumtaz_einvoicing`, `mumtaz_financial_reports`, `mumtaz_zaki`, `mumtaz_crm_starter` or any Jawhar module.
- The older bundles use `sale`, not `sale_management`.
- Prices 49/149/199/299 are a third price list beside the two in D-11.
- All other bundle names exist on disk or are Community apps.

### 7.5 CI against the profiles (VERIFIED)

- `scripts/platform_ci.sh` installs every non-Jawhar folder in `addons/` into one database (43 modules, including C2P and website modules). That proves the modules can be installed together. It does not prove any real profile, and it hides missing dependencies, because a module's undeclared dependency is always present.
- `scripts/jewel_ci.sh` installs 14 modules including `_website`, then seeds `_demo`. That matches profile 3 plus two extras that should be declared as extras.

## 8. Registry schema additions and checks (PROPOSED)

### 8.1 What `--check` enforces today (VERIFIED)

- Classification completeness in both directions (every module classified; no classification without a module).
- The layer is a valid one.
- No manifest dependency points upward unless listed in `known_violations`.
- No stale entry in `known_violations`.
- `registry.yaml` matches what `--write` would generate.

### 8.2 What it does not enforce

- Ownership, customer, profiles, bundle contents, CI module lists.
- Disposition values (free text).
- Code-level and soft dependencies; `auto_install`; cross-product edges inside a layer.
- Customer hard-coding; the `mumtaz_` prefix rule.
- Tests: the count is recorded, never required.
- Access-file content: `access_csv` is an `exists()` check only, and five files are header-only (`mumtaz_app_portal`, `mumtaz_base`, `mumtaz_customer_portal`, `mumtaz_jewellery_sale`, `mumtaz_vendor_portal`).
- `python_lines` includes tests.

### 8.3 Additions to `registry/classification.json`

- `owners`: the 13 values used in section 4 — `platform-core`, `platform-saas`, `erp-generic`, `website`, `zaki-ai`, `marketplace`, `jawhar`, `pharma`, `c2p-customer`, `ig2-customer`, `internal-tooling`, `faizy`, `delivery-os`.
- Per module, required: `owner`; `reusable` (`yes|no|needs-work`); `disposition`, validated against `^(keep|keep\+tests|merge:<module>|split|retire-candidate|relocate:<repo>)$`.
- Per module, optional: `customer` (`c2p|ig2`, required when the owner ends in `-customer`); `soft_depends`; `installed_in` (database names from the server inventory); `legacy_name` (true for installed modules that break the prefix rule).
- `owner_may_depend_on`, a matrix:

| Owner | May depend on |
|---|---|
| platform-core | nothing local |
| platform-saas, erp-generic, website | platform-core |
| zaki-ai, jawhar, pharma | platform-core, erp-generic |
| marketplace | platform-core, erp-generic, platform-saas |
| c2p-customer, ig2-customer | anything except another customer |
| — | Nothing may depend on a customer owner, internal-tooling, website or faizy |

- `profiles`: `{name: {standard: [...], modules: [ordered], optional: [...], l10n: {AE: [...]}, allowed_owners: [...], forbidden: [...]}}`.
- `registry/odoo19_ce_modules.txt`: generated once from the Community tree.
- `known_untested`, `auto_install_allowed`, `hardcoding_allowlist`: ratchet lists, like `known_violations`.

### 8.4 New checks

1. **Enums.** `owner`, `reusable` and `disposition` hold valid values; a `merge:` target exists.
2. **Owner matrix.** Every `depends` edge satisfies `owner_may_depend_on`.
3. **Profile existence.** Each name in a profile is on disk or in the Community list. This catches `account_accountant`.
4. **Profile closure.** The transitive local closure of a profile (plus auto-install modules whose dependencies are all present) is inside `modules ∪ optional`, contains nothing in `forbidden`, and has owners inside `allowed_owners`. This catches tm in a tenant.
5. **Profile order.** Each module's local dependencies appear earlier in the list.
6. **Bundle parity.** Parse `base_modules` and `optional_modules` from the bundle XML and apply checks 3 and 4 against the profile named by the bundle's `code`.
7. **CI parity.** The `MODULES=` line in `jewel_ci.sh` equals the Jawhar profile plus declared extras.
8. **Soft dependencies.** Scan for `env['x.y']`, `'x.y' in env` and `module.xmlid` strings. If the owning module is outside the dependency closure, it must be listed in `soft_depends` and satisfy check 2.
9. **Hard-coding lint** for non-customer owners: deny `IG2`, `Mumtaz_[A-Z0-9]+`, `@core2plus\.com`, `C2P`, `-d Mumtaz_`, and literal `AED`/`PKR` in `.xml`/`.js`, with a file:line allowlist carrying a reason (the `check_sudo.py` pattern).
10. **Prefix rule.** Customer owners do not start with `mumtaz_`; reusable owners do, unless `legacy_name`.
11. **Tests required** for platform-saas, erp-generic, zaki-ai, marketplace, jawhar and customer owners, unless listed in `known_untested`.
12. **`auto_install: True`** only if listed in `auto_install_allowed`.
13. **Access files.** Flag a header-only access file, and a module that defines a concrete model without an access file.

### 8.5 Suggested order of introduction

Each step starts with today's failures recorded in a ratchet list, so CI is green on the day the check lands and can only get stricter. This is how `known_violations` already works.

| Step | Add | Starts with | Why this order |
|---|---|---|---|
| 1 | `owner`, `reusable`, `disposition` on all 60 modules; check 1 | No exceptions needed | Pure metadata; no runtime effect |
| 2 | `odoo19_ce_modules.txt`, `profiles`; checks 3, 5 | Old bundles listed as known failures | Makes `account_accountant` visible |
| 3 | Checks 4, 6 (closure, bundle parity) | Four older bundles in a `known_profile_violations` list; `mumtaz_erp` must pass | Turns "tm in a tenant" into a CI failure for anything new |
| 4 | `owner_may_depend_on`; check 2 | Today's cross-owner edges listed | Stops new product-to-product coupling |
| 5 | Checks 12, 13, 11 | `auto_install_allowed` = the two CFO modules; `known_untested` = today's untested modules | Cheap ratchets |
| 6 | Checks 8, 9, 10 | `soft_depends` from section 5.3; `hardcoding_allowlist` from section 4 | Needs a scanner; most work |
| 7 | Check 7; `installed_in` | — | Needs the server inventory |

## 9. Top actions, by value over risk (PROPOSED)

1. **Record what each database has installed** and store it as `installed_in`. Every merge, retirement and rename below is blocked on it. No risk.
2. **Remove client and staff data from reusable or shared code.** The IG2 brand in `mumtaz_ceo_dashboard`, the client database name in `seed_demo.py`, the knowledge block in `c2p_master_agent`, and the staff email addresses and project ids in the `c2p_project_tracker` hook. The repository is described as public (D-12).
3. **Add `owner`, `profiles` and checks 1–6** to the registry. Small, no runtime effect, and it turns the bundle defects into CI failures.
4. **Fix the bundles.** Drop `account_accountant`; use `sale_management`; add localisation; remove sme, onboarding and voice from tenant bundles until they are decoupled. This is data only. The records are `noupdate`, so existing control databases need a manual edit. The new `mumtaz_erp` bundle is the first clean one.
5. **Declare `mumtaz_jewellery_vip` in `mumtaz_jewellery_sale`.** One line.
6. **Break the CFO auto-install chain.** Remove both flags and the `portal_routing → cfo_base` dependency. This clears the one known violation.
7. **Decide the tenancy model in writing** and retire `mumtaz_org_config`. Higher risk if `mumtaz.org` rows exist.
8. **Keep control-plane models out of tenants.** Introduce a small tenant-agent module and cut tm and cp from `mumtaz_cfo_base`, `mumtaz_marketplace`, `mumtaz_voice` and `mumtaz_onboarding`. This is also the prerequisite for the Jawhar bridge.
9. **Bring IG2 code under control.** Put `c2p_pk_vouchers`, the report variants and a pinned `base_accounting_kit` in a private client repository, with an `ig2-deployment` profile. No change to the client's database without testing and approval.
10. **Consolidate after the inventory.** Portals into `mumtaz_app_portal`; retire the three shells and `mumtaz_base`; choose the AI survivor (D-03); add tests to `mumtaz_einvoicing` before any filing relies on it.

## 10. Stale statements in existing governance documents (VERIFIED)

| Document | Statement | What the code shows |
|---|---|---|
| `REPO_MAP.md` (line 26) | "57 Odoo 19 modules" in `addons/` | 58 folders in `addons/`, plus 2 Faizy modules: 60 in the registry |
| `REPO_MAP.md` (line 52) | 17 platform modules | 18 |
| `REPO_MAP.md` (line 14) | "Nothing in this repository names IG2" | `mumtaz_ceo_dashboard` and `mumtaz_media_buying` name it, and `sites/ig2.mumtaz.digital/` exists |
| `docs/erp/architecture/MODULE_DEPENDENCY_MAP.md` (line 63) | "No dependency cycles" | True for manifests. False in code: `mumtaz_tenant_manager` uses models from `mumtaz_sme_profile` and `mumtaz_cfo_base`, both of which depend on it (section 5.3) |
| `CLAUDE.md`, `README.md` | "57 Odoo 19 Community addons" / "Odoo modules (57)" | Same count drift |
| `c2p_proposal/__manifest__.py` | version `17.0.…` | Every other module is `19.0.…` |

These documents were not edited as part of this review.

## 11. Could not determine

- Which modules are installed in which live database, and from which checkout. All "installed" statements above are REPORTED.
- Whether `Mumtaz_IG2` has `mumtaz_media_buying` or `mumtaz_ceo_dashboard`, and whether `Mumtaz_C2P` has the lead modules.
- Which database is the control plane, and whether any tenant was ever provisioned through `mumtaz.tenant` on the server.
- Row counts in `mumtaz_org`, `mumtaz_organization`, `mumtaz_sme_profile`, `mumtaz_tenant` and `mumtaz_api_key`. These decide the migration effort in section 6.
- Whether the shells (`mumtaz_portal`, `mumtaz_cfo_toolkit`, `mumtaz_super_toolkit`, `mumtaz_base`) are installed anywhere.
- The content of code not on `main`: the `pharma_*` modules, `c2p_pk_vouchers`, the IG2 reports, `faizy_ai`, `base_accounting_kit`.
- Whether every module installs cleanly on its own. The audit reports that four platform modules failed a fresh install before PR #172; which ones, and whether all are fixed, was not confirmed here. In this session only `mumtaz_tenant_manager`, `mumtaz_control_plane` and the `starter` bundle's modules were installed (successfully).
- Whether the repository is actually public (stated only in D-12).
- The security findings quoted from the audit (ODOO-01, ODOO-08, ODOO-31, the scraper SSRF, the ZAKI all-company figures) were not re-verified.
- Whether the installed-app choices in profiles 6 and 7 match the live C2P and IG2 databases.
