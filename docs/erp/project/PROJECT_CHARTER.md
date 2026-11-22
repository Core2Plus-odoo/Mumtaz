# ERP project charter — C2P Group / Mumtaz platform (draft)

**Status:** Draft from repository evidence. Every "To confirm" needs the
sponsor. No scope in this charter is signed.

| Item | Value |
| --- | --- |
| Project ID | ERP-2026-01 |
| Sponsor and sign-off authority | To confirm (Managing Partner, C2P Group) |
| Business process owners | To confirm per domain (sales, finance, operations) |
| Platform path | **Odoo 19 Community** (A) with ERP-connected applications (Jawhar web, C2P Agency OS, zaki-server) [VERIFIED] |
| Target stack and versions | Odoo 19.0 Community; PostgreSQL 15 (production compose) / 16 (CI and sandbox); Python 3.12 (Odoo image); React 18, TypeScript, Vite 5, Node 22; FastAPI [VERIFIED] |
| Legal entities, countries | C2P Consultants FZC LLC and C2P Solutions (UAE) [VERIFIED by `c2p_project_tracker`]; tenants in UAE, KSA, Pakistan [VERIFIED by e-invoicing scope]; others To confirm |
| Business units / shared services | Consulting delivery (C2P), SaaS platform (Mumtaz), jewellery edition (Jawhar), media buying; shared services allocation policy To confirm |
| Hosting and data residency | Hostinger VPS, single host, Docker Compose; residency requirements To confirm |
| Environments | local/CI (disposable databases), Jawhar staging (`jewel.mumtaz.digital`), production (`erp.mumtaz.digital` and siblings); a staging for the platform ERP To confirm |
| Existing systems and data | Odoo databases `Mumtaz_ERP`, `Mumtaz_C2P` (41,182 leads), tenant databases; SQLite stores in two services; spreadsheets for jewellery stock (import built) |
| Volumes and concurrency | Leads: 41k; Jawhar demo: 60 pieces, 38 clients; real tenant volumes To confirm |
| User roles and languages | Owner, manager, staff, finance, VIP manager (Jawhar); platform admin; English and Arabic (RTL) required for Jawhar; Urdu To confirm |
| Accounting policy owner | **To confirm (named finance manager)**: VAT, chart of accounts, valuation, lock dates, AML thresholds |
| Security, SSO, MFA, retention, RPO/RTO | Odoo auth + HMAC SSO + JWT; MFA not enforced; RPO/RTO To confirm |
| Integrations | Stripe, ZATCA (KSA), FBR (PK), UAE QR, gold-rate JSON feeds, ElevenLabs, Anthropic, GitHub, WhatsApp (hand-over link only) |
| Milestones and constraints | Wave-based (see `ROADMAP.md`); no calendar commitments made here |

## Expected measurable outcomes (baselines not invented)

| Metric | Baseline | Target | Owner |
| --- | --- | --- | --- |
| Modules with install test + fresh-DB CI | 14 of 52 | 52 of 52 | Engineering |
| Business logic outside git (server actions) | 25 on `crm.lead` | 0 | Engineering |
| Trial balance reconciles to subledgers on `Mumtaz_ERP` and C2P | Not measured | Monthly, signed | Finance |
| Quote-to-cash proven end to end with tests (non-jewellery) | No | Yes | Engineering |

## Module scope (initial proposal; disposition in `01-CAPABILITY_MATRIX.md`)

In scope now: platform foundation, CRM (versioned), sales, purchase, stock,
finance core with localisation, projects (C2P), jewellery vertical (built),
reporting, governed AI. Deferred: HR/payroll, manufacturing, service,
rental, consolidation. Excluded: Enterprise-only modules.

## Assumptions, dependencies, unresolved decisions

See `DECISION_REGISTER.md` (ADR-001..012, D-01..D-08).

## Approvals

| Stage gate | Business | Technical | Financial | Date |
| --- | --- | --- | --- | --- |
| G0 charter and scope | | | | |
| G1 architecture | | | | |
