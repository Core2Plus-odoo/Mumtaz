# 05. End-to-end business process linkage matrix

Every cycle in the blueprint (§6) is mapped step by step: the **native Odoo 19 model** that carries it, the **custom hook** (if any), the **link and its cardinality**, the **accounting/stock effect**, and an honest **status**: `Standard` (native, not modified), `Built` (custom, in the repo), `Written` (custom, **NOT RUN**), `Gap` (missing), `Unverified` (native, never exercised on a configured test database here). Evidence = path or test.

## 1. Lead-to-cash with courier COD (the pharma reference transaction)

| # | Step | Native model / state | Custom hook | Link to previous step (cardinality) | Effect | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Lead / opportunity | `crm.lead` | none | n/a | none | Standard, Unverified |
| 2 | Quotation → order | `sale.order` draft → `sale` | **tax gate** on `action_confirm`: blocks a product with no approved tax rule; optional equality of line tax to the rule's linked `account.tax` | quotation → order 1:1 | none | Built (30 tests; the tax-link check Written/verified at 176) |
| 3 | Reservation, delivery | `stock.picking` / `stock.move` | none | order line ↔ move **M:N native** | stock out | Standard, Unverified |
| 4 | Parcel booked with courier | none native | `pharma.courier.shipment` created by delivery-report upload (validate → build); `sale_order_id` matched by `order_ref` (client ref or order name); archived raw event | **order 1 : N parcels**; parcel → delivery picking: **no link** | none | Built; **Gap** (no parcel ↔ picking/line link) |
| 5 | Customer invoice | `account.move` `out_invoice` | **tax gate** on post | order line ↔ invoice line **M:N native** | AR, revenue, tax | Built gate; invoicing Standard, Unverified |
| 6 | Courier collects cash | n/a | `cod_collected` from the courier's report (a *claim* until remitted) | parcel carries declared / collected / remitted | none | Built |
| 7 | Collection entry | `account.move` entry | **draft** Dr courier clearing / Cr **customer receivable with the customer set**; strict order feeds step 10 | parcel 1 : 0..1 *active* entry (history `previous_move_ids` M:N) | clearing up, AR down once posted and reconciled | Built (live) |
| 8 | Reconcile the credit to the invoice | native reconciliation (receivable) | none (deliberately) | collection credit ↔ invoice debit **M:N native**, by the accountant | invoice paid | **Gap G-4: never exercised**; parcel ↔ invoice not linked |
| 9 | Remittance slip | none native | statement upload → draft remittance (lines per parcel, itemised deductions); post | slip 1 : N lines; parcel ↔ slip **M:N via lines** (partial remittance supported) | none until entry | Built (live) |
| 10 | Reconcile slip to the bank | hub run | `action_reconcile` (Finance only): exact ref > one-to-many > amount+date; exceptions with maker-checker | slip 1 : 0..1 run | none | Built (live) |
| 11 | Settlement entry | `account.move` entry | **draft** Cr clearing (gross), Dr bank (received), Dr each deduction account, difference line; **strict order**: every parcel needs a *posted* collection entry, else logged written override | slip 1 : 0..1 active entry | clearing down to zero; bank up; deductions booked | Built (live) / strict order Written |
| 12 | Post entries | `account.move.action_post` by an accountant | **Entries to Post** queue (Written) | n/a | GL | Standard, queue Written |
| 13 | Withdraw a posted entry | native reversal | wizard with required reason; reversal **draft**; record released after the reversal posts; old entry kept in history | entry 1 : 0..N reversal | reversal entry | Written (14 tests, NOT RUN) |
| 14 | Period close | lock dates | none | n/a | locks | **Gap** (not configured; ADR-011) |
| 15 | Reports | pivots; accounting kit reports | Pipeline / Ageing pivots; Exception Queue | drill to parcels, slips, entries | none | Partial |

**Variants required by the blueprint, status:** partial delivery (native; **parcel not tied to delivery line**), multiple parcels per order (supported), partial remittance (supported: parcel stays "remitted in part", queue shows next step), customer paid less / courier remitted less (exceptions, supported), returned parcel with COD held (exception + flow step; **no refund entry**, gap), cancelled order after parcel booked (parcel `cancelled`; **no automatic downstream effect**, `[P]` backlog), credit note / refund (native, not linked to parcel), multi-currency (**not supported**, single currency, gap G-2), discounts (native), tax exemption (rule engine; `[A]` not scoped), duplicate upload (idempotent: dedupe keys; second identical row = no-op), unauthorised role (server-side group checks in every action; Finance-only build/reconcile).

## 2. Other mandatory cycles

| Cycle (blueprint §6) | Native carrier | Custom hook here | Status | What a verified slice would prove |
| --- | --- | --- | --- | --- |
| Procure-to-pay: requisition, RFQ, PO, receipt, 2/3-way match, bill, payment, bank rec | `purchase`, `stock`, `account` | none for pharma; marketplace uses `purchase` | Standard, **Unverified** here | PO partial receipt → bill → payment → GL, with lot/expiry for pharma (backlog PHA-P2P-001) |
| Inventory-to-finance: demand, reservation, move, lot, balance, valuation layer, entries, GRNI/COGS rec | `stock`, `stock_account` | `pharma_partner_stock` (reads done moves) | Standard / Built; valuation policy **undecided** (ADR-005) | on-hand and valuation reconcile to the GL control accounts |
| Record-to-report: subledgers, journals, TB, tax reports, close, statements | `account` + third-party kit | draft COD entries | Partial; **no localization, no lock policy, no tax returns** | TB balanced, AR/AP subledgers = control accounts, period locked and reversal enforced |
| Project/service-to-cash | `project`, (`hr_timesheet` absent) | `c2p_project_tracker` | Partial, out of pharma scope `[D-002]` | n/a until scoped |
| HR-to-finance | `hr*` (absent) | none | **Gap / Defer** | local payroll expert approval first |
| Intercompany / shared services | none | none | **Gap / Defer** unless 2+ entities `[D-003]` | mirror entries and eliminations |
| Returns and refunds | native returns + credit notes | parcel `returned`, returned-COD exception | Partial | COD refund entry + tax-event reversal (PHA-RET-001) |

## 3. Link integrity rules (checked against the code)

| Rule (blueprint §7.3, §8) | Pharma implementation |
| --- | --- |
| Reconcile quantities and amounts at integration boundaries | Upload validation rejects negatives, delivered-before-booked, over-remittance (cumulative per parcel), unknown parcel on a slip, duplicate rows in a file |
| Never cascade-delete posted history | COD entry links `ondelete="set null"`; Odoo forbids deleting posted entries; reversal creates a new entry |
| Status vs fulfilment vs settlement independent | parcel `state` (courier), `cod_state` (money), computed `flow_stage`/`flow_next` (process) |
| Drill-down from a number to records | Pipeline/Ageing pivots → parcels; parcel form → remittance lines; remittance → run → exceptions; parcel/remittance → entry (accountants) |
| One authoritative owner per fact | courier owns delivery status claims; Odoo owns entries; tax rule owns *approval*, `account.tax` owns the rate |
