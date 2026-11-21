# 4. Data model, field dictionary and entity relationships

Physical schema is Odoo's. This document records (a) the custom entities that
exist [VERIFIED], (b) the universal entity contract every new entity must
satisfy [PROPOSED], and (c) the relationship catalogue with cardinality and
delete policy. `DATA_DICTIONARY.csv` lists the fields of the custom
transactional entities in the pack's column format; standard Odoo fields are
not re-listed.

## 4.1 Universal entity contract, mapped to Odoo [PROPOSED]

| Blueprint field | Odoo provision | Rule for custom models |
| --- | --- | --- |
| `id` | `id` | never a business key |
| `tenant_id` | the database | no field |
| `company_id` | `company_id` Many2one, required, default `env.company`, with `_check_company_auto` where it links to other company-scoped records | **mandatory on every transactional and master extension model** (Jawhar: done; platform: to audit) |
| `branch_id` / `department_id` | `warehouse_id` or analytic distribution / `hr.department` | per ADR-003 |
| `code`, `sequence` | `name` from `ir.sequence` | sequence per company |
| `status` | `state` Selection with explicit transitions in a method, never written from the UI | tests per transition |
| `document_date`, `effective_date` | `date` / `date_approve` | `Date` for business dates, `Datetime` for instants |
| `created_at/by`, `updated_at/by` | `create_date/uid`, `write_date/uid` | free |
| `version` | `write_date` + optimistic check in methods that change state | row lock (`FOR UPDATE`) on commit paths (Jawhar counter does this) |
| `currency_id`, `exchange_rate` | `currency_id`; `account.move` stores rate | money fields `Monetary`, never `Float` for totals |
| `source_system`, `source_record_id` | `x_source_system` Char + `x_source_ref` Char, unique together per model | required on imported/migrated rows (PLT-REQ-004) |
| `approval_state/by/at` | fields on the model + chatter tracking | maker ≠ checker enforced in code |
| `active` | `active` | posted or confirmed records never deleted; `ondelete='restrict'` on their links |
| audit | `mail.thread` with `tracking=True` on state and money fields; product audit models for access | required |

## 4.2 Custom entities in the repository [VERIFIED]

| Family | Entity (`_name`) | Owner scope | Purpose |
| --- | --- | --- | --- |
| Jewellery | `jewellery.gold.rate` | company | approved 24K rate, maker-checker |
| | `stock.lot` (ext.) | company | the piece: weights, karat, making, RFID, certificate, cost, price |
| | `product.template` (ext.) | company | design: category, cutout, physical size |
| | `jewellery.old.gold` | company | exchange intake with threshold approval |
| | `res.partner` (ext.) | company | tiers, RM/deputy, consent, KYC, phones |
| | `jewellery.vip.access.log` | company | who looked at a restricted client |
| | `jewellery.occasion`, `jewellery.approval.memo`, `jewellery.offer.suggestion` | company | occasions, pieces on approval (stock moves), ranking |
| | `sale.order` (ext.) | company | frozen rate per line, counter commit, discount limit |
| | `jewellery.tray`, `.tray.line`, `crm.lead` (ext.) | company | private tray, client link, viewing, reservation |
| | `jewellery.ai.agent/draft/run` | company | governed agents, drafts, audit |
| | `jewellery.kiosk.request` | company | viewing/delivery request with fit notes |
| | `jewellery.api.audit` | company | every API call |
| | `jewellery.aml.event` | company | identity, screening, threshold events |
| | `jewellery.transfer`, `jewellery.gold.reconciliation(.line)` | company/store | custody and fine-gram counts |
| | `jewellery.rate.feed(.log)` | company | feed adapter |
| | `jewellery.client.session` | company | client one-time-code sessions |
| | `jewellery.piece.import` | company | stock-book import runs |
| | `jewellery.owner.card` | company | decision cards |
| C2P | `project.project/.task` (ext.), `c2p.milestone.history`, `c2p.raid.item`, `c2p.change.request`, `c2p.dashboard`, `c2p.command.center` | company (two) | portfolio ↔ delivery |
| Platform | `mumtaz.tenant`, `.module.bundle`, `.provision.wizard` | control plane DB | tenants |
| | `mumtaz.plan`, `.plan.feature`, `.feature`, `.tenant.feature`, `.subscription(.billing.record/.lifecycle.*/.notification.*)`, `.usage.metric`, `.commercial.*`, `.erp.module.access` | control plane | entitlements and billing |
| | `mumtaz.stripe.client/.event/.settings` | control plane | Stripe |
| | `mumtaz.api.key`, `.api.usage.log`, `.async.job` | control plane | gateway |
| | `mumtaz.marketplace.listing/.category/.inquiry/.tag/.access` + `sale/purchase/product` ext. | tenant | B2B marketplace |
| | `media.outlet`, `media.rate.card(.line)`, `media.plan(.line)` | tenant | media buying |
| | `mumtaz.cfo.workspace/.category/.data.source/.mapping.profile/.upload.batch/.transaction/.review.item` | tenant | CFO ingestion (analysis only) |
| | `mumtaz.ai.session/.message/.service/.provider.*`, `mumtaz.voice.*`, `zaki.*` | tenant | AI layers (to consolidate) |
| | `mumtaz.einvoice.config` + `account.move` ext. | tenant/company | e-invoicing |
| | `lead.scraper.*`, `lead.nurture.*`, `lead.whatsapp.*` | tenant | lead engine |
| | `mumtaz.org`, `.organization`, `.sme.signup`, `.sme.profile`, `.onboarding.checklist` | control plane | SME lifecycle |

## 4.3 Relationship catalogue (cardinality, integrity, delete policy)

| Parent → child | Cardinality | Invariant | Delete policy | Tag |
| --- | --- | --- | --- | --- |
| `res.company` → every custom transactional record | 1:N | `company_id` required; `_check_company` on links | restrict | [PROPOSED rule; VERIFIED for Jawhar] |
| `res.partner` → `sale.order`, `account.move`, `jewellery.tray`, `crm.lead` | 1:N | partner of the order's company or shared | restrict | standard |
| `crm.lead` → `sale.order` | 1:N | opportunity kept on the order (`opportunity_id`) | restrict | standard |
| `sale.order` → `sale.order.line` | 1:N | no confirmed order with an empty or unpriced line (Jawhar: engine price required) | cascade in draft, restrict after | standard + Jawhar |
| `sale.order.line` ↔ `stock.move` | M:N (`sale_line_id` on move; several moves per line) | delivered qty = sum of done moves | restrict | standard |
| `sale.order.line` ↔ `account.move.line` | M:N (`sale_line_ids` on invoice line) | invoiced qty by policy | restrict | standard |
| `purchase.order.line` ↔ `stock.move` / `account.move.line` | M:N | received/billed qty; 3-way match tolerance | restrict | standard |
| `stock.move` → `stock.valuation.layer` | 1:N | valuation reconciles to the stock account | restrict | standard (`stock_account`) |
| `account.move` → `account.move.line` | 1:N | balanced per company currency when posted | restrict when posted | standard |
| `account.move` ↔ `account.payment` | M:N via `account.partial.reconcile` | residual = total − allocations | restrict | standard |
| `stock.lot` (piece) → `jewellery.tray.line`, `kiosk.request`, `transfer` lines, `reconciliation.line` | 1:N | one live sale per piece (row lock + live-order check) | restrict | [VERIFIED] |
| `jewellery.gold.rate` → priced lines | 1:N (snapshot copied to the line) | price never recomputed after confirmation | restrict | [VERIFIED] |
| `project.project` (portfolio) ↔ `project.project` (delivery) | 1:1 reciprocal across companies | counterpart link is symmetric | set null | [VERIFIED] |
| `project.task` (milestone) → `project.milestone` | 1:1 | reached state derives portfolio progress | set null | [VERIFIED] |
| `mumtaz.tenant` → `mumtaz.subscription`, `.tenant.feature`, `.stripe.*` | 1:N | effective feature = plan then override | restrict | [VERIFIED] |
| `account.move` → e-invoice state | 1:1 | UUID immutable after submission; cancel only through the authority's flow | n/a | [VERIFIED exists; to test] |

## 4.4 Field dictionary

`DATA_DICTIONARY.csv` (this folder) lists the custom fields of the
transactional entities above with type, precision, requiredness, scope,
security class, audit flag and the test that covers each. Standard Odoo
fields are referenced by the Odoo 19 documentation and not duplicated. Every
new slice appends its rows before the pull request is opened.
