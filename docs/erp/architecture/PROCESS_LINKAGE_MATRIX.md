# 5. End-to-end business process linkage matrix

For each process: the chain of documents, the line-level link, the state that
moves it, the posting effect, the exception paths, and whether the chain is
**proven** (automated test exists in this repository), **standard** (Odoo
native, not yet exercised by a test here) or **missing**.

## 5.1 Lead-to-cash (L2C)

| Step | Document | Link to previous | State change | Stock | Accounting | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Lead | `crm.lead` | — | new → qualified (C2P: scoring in DB actions) | — | — | standard; C2P rules unversioned (R1) |
| Opportunity → Quotation | `sale.order` (draft) | `opportunity_id` | draft | — | — | standard; Jawhar proven (tray → quote with frozen rate) |
| Approval (discount, credit) | `sale.order` | `sale` double validation / Jawhar discount limit on making only | sent | — | — | Jawhar proven (`test_discount_limit`); generic: configure |
| Sales order | `sale.order` | same record | sale | reservation (Jawhar: row lock, one live order per piece) | — | Jawhar proven |
| Delivery | `stock.picking` / `stock.move` | `sale_line_id` | done | on hand ↓, valuation layer (if `stock_account`) | COGS/stock output (automated valuation only) | standard; Jawhar counter proven (commit moves the piece) |
| Customer invoice | `account.move` | `sale_line_ids` on lines; Jawhar copies the rate snapshot | posted | — | AR / revenue / VAT | Jawhar proven (invoice snapshot test); generic: standard |
| Payment | `account.payment` + partial reconcile | reconciliation | paid | — | bank/cash / AR | Jawhar counter proven (one transaction) |
| Bank reconciliation | `account.bank.statement.line` | reconcile model | reconciled | — | bank clearing | standard; **no statement import module installed** |
| Report | margin per order (Jawhar `_margin`), sales analysis | derived | — | — | — | Jawhar proven for cost basis |

Variants and where they stand: partial delivery and partial invoice =
standard policy (`invoice_policy`), **not yet proven by a test here**
(SLS-REQ-001); down payment = standard; credit hold = configure; return and
refund = standard return picking + credit note, Jawhar old-gold exchange
proven; multi-currency = standard, no test; AML threshold at the counter =
Jawhar proven.

## 5.2 Procure-to-pay (P2P)

| Step | Document | Link | Posting | Status |
| --- | --- | --- | --- | --- |
| Requisition | not modelled (purchase `requisition` is Enterprise) | — | — | missing; OCA `purchase_request` if needed [DECISION] |
| RFQ / PO | `purchase.order` | marketplace RFQ wizard creates from inquiry; media plan creates vendor POs | — | exists, untested |
| Approval | `purchase` double validation above an amount | — | — | configure |
| Receipt | `stock.picking` | `purchase_line_id` | stock ↑, GRNI (interim) with automated valuation | standard |
| Vendor bill | `account.move` (in_invoice) | `purchase_line_id` on lines; `bill_control` = received quantities | AP / expense or stock interim / input VAT | standard, 3-way match by configuration |
| Payment | `account.payment` | reconcile | bank / AP | standard |
| Landed cost | `stock.landed.cost` | picking | valuation adjustment | standard, not installed |

## 5.3 Inventory-to-finance

| Event | Physical effect | Valuation | Accounting | Status |
| --- | --- | --- | --- | --- |
| Receipt | quant ↑ at `lot_stock` | layer created at PO cost | stock valuation / GRNI | standard (requires `stock_account` automated valuation: ADR-005) |
| Internal transfer (Jawhar store to store) | via `location_in_transit`, two-sided | none (same company) | none | proven (9 tests) |
| On approval (memo) | to `location_on_approval` and back | none | none | proven |
| Sale / delivery | quant ↓ | layer consumed | COGS / stock output | Jawhar proven for the move; posting depends on configuration |
| Count / reconciliation | Jawhar: variance in fine grams, serials missing, manager closes | adjustment through standard inventory adjustment only | per adjustment account | proven (count), adjustment posting standard |
| Import (opening stock) | quant set by inventory mode, cost on the piece | opening layer at cost (when valuation on) | opening stock journal | proven (import), posting to configure |

## 5.4 Record-to-report

| Element | Where | Status |
| --- | --- | --- |
| Chart of accounts, taxes | `l10n_*` per tenant | **not installed by code** (ADR-006) |
| Journals, lock dates | `account` configuration | to configure (ADR-011) |
| Subledger reconciliation (AR, AP, bank, stock) | standard reports + reconciliation widget | to prove monthly (FIN-REQ-003) |
| Statements (TB, P&L, BS, aged) | `account` standard reports; custom `mumtaz_financial_reports` | custom untested (D-02) |
| Tax report / e-invoicing | `account` tax report; `mumtaz_einvoicing`; native `l10n_sa_edi` | custom untested; decision on ZATCA path |
| Period close | manual | document the close checklist (quality folder) |

## 5.5 Project/service-to-cash (C2P)

| Step | Document | Link | Status |
| --- | --- | --- | --- |
| Signed proposal | `crm.lead` won → `sale.order` (C2P delivery system drives this over XML-RPC) | opportunity | exists by docs |
| Portfolio project | `project.project` (portfolio layer, C2P Consultants) | contract value, 60/40 split, received, outstanding | proven (tracker tests) |
| Delivery project | `project.project` (delivery layer, C2P Solutions) | reciprocal `c2p_counterpart_id` | proven |
| Milestones | `project.task` (`c2p_is_milestone`) ↔ `project.milestone` | reached → progress, billing % | proven |
| Change request | `c2p.change.request` | moves contract value once | proven |
| Time and cost | `hr_timesheet` / analytic lines | **not linked to tracker margin** | missing (PRJ-REQ-001) |
| Customer billing | `account.move` from milestone | invoice_status on the milestone task | partial (status field; invoice creation standard) |
| Intercompany recharge | C2P Consultants ↔ C2P Solutions | **operational split only, no mirrored accounting** | missing (FIN-05) |

## 5.6 HR-to-finance

Missing entirely (no `hr` dependency). Deferred until scoped; payroll
localisation requires a qualified local expert (blueprint §6.6).

## 5.7 Cross-cutting exceptions required by the blueprint, status

| Exception | Handling today | Status |
| --- | --- | --- |
| Duplicate vendor invoice | standard `ref` duplicate warning | standard |
| Concurrent reservation of the same piece | row lock + live-order check | proven (Jawhar) |
| Insufficient stock | standard reservation | standard |
| Closed fiscal period | lock dates | to configure |
| Integration timeout / retry | Jawhar LLM retry/backoff; Stripe/ZATCA **to verify** | partial |
| Unauthorised cross-company read | Jawhar: tested (404 not 403); platform: untested | partial |
| Self-approval | gold rate maker ≠ checker; AI draft approver ≠ author; exchange threshold | proven (Jawhar) |
