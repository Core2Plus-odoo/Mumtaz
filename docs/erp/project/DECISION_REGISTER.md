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
