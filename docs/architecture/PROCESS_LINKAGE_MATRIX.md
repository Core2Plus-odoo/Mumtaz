# Deliverable 5 — End-to-end business process linkage matrix

Blueprint §6's seven mandatory processes, scored against this repository's source.
"Link exists" means a field, model or method in `addons/` actually carries the
relationship — not that Odoo *could* do it natively.

---

## 1. Lead-to-cash (blueprint §6.1)

`Lead → Opportunity → Quotation → Approval → Sales Order → Delivery/Service → Customer Invoice → Payment → Bank Rec → GL → Margin Report`

| Hop | Mechanism available | Link in `addons/`? | Status |
|---|---|---|---|
| Lead → Opportunity | `crm` standard | 6 `crm.lead` refs from the growth layer | **Standard, integrated** |
| Opportunity → Quotation | `sale_management` standard | none | **Standard, untouched** |
| Quotation → Approval | — | **no approval model exists** | **MISSING** |
| Quotation → Sales Order | `sale` standard | none | **Standard, untouched** |
| Sales Order → Delivery | `stock` standard | none | **Standard, untouched** |
| Sales Order → Invoice | `account` standard | none | **Standard, untouched** |
| Invoice → Payment | `account` standard | none | **Standard, untouched** |
| Payment → Bank reconciliation | `account` standard | `mumtaz_cfo_ingestion` ingests statements but does not reconcile | **PARTIAL / unclear (DEC-004)** |
| GL → Margin report | — | `mumtaz_financial_reports` renders without lineage | **PARTIAL, no drill-down** |

**Verdict: the chain is unbroken in Odoo standard and completely unproven here.**
Blueprint §6.1's required variants — partial delivery, multiple deliveries, down
payment, split invoice, credit hold, backorder, discount approval, tax exemption,
return, refund, multi-currency settlement — have **no test covering any of them**,
in any module. §19 Wave 2 says a reference transaction must prove the whole flow
before operations work begins. That reference transaction has never been run.

The one custom participant is `media.plan`, which holds `sale_order_id` and
`purchase_order_ids` and computes `net_revenue` — but with no link to
`account.move` it cannot tell invoiced from planned (see
`ENTITY_RELATIONSHIPS.md` §2.1).

---

## 2. Procure-to-pay (blueprint §6.2)

`Requisition → Budget Check → RFQ → Bid → PO → Receipt → 2/3-Way Match → Vendor Bill → Payment → Bank Rec → GL`

| Hop | Link in `addons/`? | Status |
|---|---|---|
| Requisition | none — no model | **MISSING** |
| Budget check | none — no budget model | **MISSING** |
| RFQ | `mumtaz.marketplace.po.rfq.wizard` → `purchase.order` | **PARTIAL** (marketplace-specific) |
| Bid comparison | none | **MISSING** |
| PO approval | none — no approval model | **MISSING** |
| Goods receipt | `stock` standard, untouched | **Standard, unproven** |
| 2/3-way match | none | **MISSING** |
| Vendor bill | `mumtaz_vendor_portal` has 7 posting references, 0 models | **PARTIAL, controller-only** |
| Payment / bank rec / GL | `account` standard | **Standard, unproven** |

**Verdict: P2P is the weakest process in the solution.** Four mandatory controls
(requisition, budget check, bid comparison, 3-way match) have no code at all.
A 3-way match is the single most important AP control in any ERP and its absence
means vendor bills can be posted against nothing.

---

## 3. Inventory-to-finance (blueprint §6.3)

`Demand → Reservation → Picking → Stock Move → Lot Trace → Balance → Valuation Layer → Accounting → COGS/GRNI Rec`

**Status: entirely standard, entirely untouched, zero custom links** — 0 of 978
fields reference `stock.picking`, `stock.move` or a valuation layer.

**[DECISION DEC-005]** For a consulting and services business this may be
correct — a services ERP legitimately needs no stock valuation. But
`mumtaz_marketplace`, `mumtaz_customer_portal` and `mumtaz_vendor_portal` all
depend on `stock`, which implies goods *are* in scope. The contradiction must be
resolved before Wave 2 scope is fixed: either inventory is in scope and needs the
full §6.3 treatment, or it is out and those three `stock` dependencies should be
removed.

---

## 4. Record-to-report (blueprint §6.4)

`Subledgers + Journals → GL → Trial Balance → Tax Reports → Period Close → BS/P&L/CF → Consolidation`

| Element | Status |
|---|---|
| Journals, GL, TB | **Standard** (`account`) |
| Tax reports | **Partial** — `mumtaz_einvoicing` handles submission, not reporting |
| Period close / lock dates | **Unknown** (DEC-001) — no code configures them |
| BS / P&L / Cash flow | **Partial** — `mumtaz_financial_reports`, no lineage |
| Consolidation / eliminations | **MISSING** |
| Subledger-to-control-account reconciliation | **MISSING** — and this is the one §6.4 calls non-negotiable |

**The CFO stack is the open question.** `mumtaz_cfo_base` / `_ingestion` /
`_transactions` / `_toolkit` hold 11 models and 969 lines beside standard
`account`. If they are a staging area for bank/statement ingestion, they are
correct and valuable. If they maintain balances of their own, they are a second
ledger and violate §4.2's single-authoritative-owner invariant. **DEC-004.**

---

## 5. Project/service-to-cash (blueprint §6.5)

`Contract → Project → Budget/Resource Plan → Time/Material/Expense → Approval → Billing → Collection → Profitability`

**This is the repository's strongest process — and still unproven.**
`c2p_project_tracker` implements:

| Element | Status |
|---|---|
| Contract → Project | **Existing** — `project.project.c2p_sale_order_id` |
| Project → Milestones | **Existing** — milestones as `project.task` with an `M\d+` code convention, `c2p.milestone.history` baselines |
| Budget / resource plan | **Partial** — `allocated_hours`, no resource plan |
| Timesheets | **MISSING** — no `hr_timesheet` dependency |
| Delivery hygiene controls | **Existing** — `_check_delivery_hygiene` enforces assignee + deadline + milestone on leaving Backlog; `_check_blocked_reason` |
| RAID / change control | **Existing** — `c2p.raid.item`, `c2p.change.request` |
| Approval | **MISSING** — `action_reset_baseline` is manager-gated, but there is no approval *record* |
| Billing | **MISSING** — no invoice link |
| Collection | **Hand-entered** — `amount_received` typed by a human, not read from payments |
| Profitability | **Existing but unreconciled** — `consultants_margin`, 60/40 split configurable per project, `groups=`-protected |
| Cross-company aggregation | **Existing, well designed** — controlled `sudo()` returning aggregates only, `_check_member()` on every entry point, money keys *omitted* (not zeroed) for non-managers |

**Verdict:** the delivery-control half is genuinely good engineering. The
cash half is disconnected from the ledger, so project profitability is currently
an assertion rather than a reconciliation. Fixing that one link —
`amount_received` computed from reconciled payments — converts the whole module
from a tracker into a financial instrument. `BACKLOG.md` `FIN-002`.

---

## 6. HR-to-finance (blueprint §6.6)

`Employee → Contract/Attendance/Leave/Advance → Payroll Inputs → Calculation → Review → Posting → Disbursement → GL`

**Status: MISSING in its entirety.** No `hr`, `hr_payroll`, `hr_holidays`,
`hr_expense` or `hr_timesheet` dependency exists anywhere in 38 modules.

This matters more than it looks for a consultancy: with no timesheets, project
cost is unknowable, so `consultants_margin` in `c2p_project_tracker` is a revenue
figure masquerading as a margin. It subtracts subcontract cost but not labour.

**[DESIGN]** `hr_timesheet` is standard Odoo Community and integrates with
`project` out of the box. This is a configuration task, not development, and it
is the highest-value-per-hour item in the whole backlog — `PRJ-001`.

---

## 7. Intercompany / shared services (blueprint §6.7)

`Service Request → Shared Time/Expense → Cost Pool → Allocation Rule → Approved Recharge → Mirror Entries → Reconciliation → Group Reporting`

| Element | Status |
|---|---|
| Cross-company visibility | **Existing** — `c2p_project_tracker` aggregation, `c2p_counterpart_id` pairing a Consultants project to its Solutions counterpart |
| 60/40 split | **Existing** — configurable per project |
| Allocation rules (versioned, effective-dated) | **MISSING** — the split is a percentage field, not a versioned rule |
| Intercompany mirror entries | **MISSING** — no `account.move` link, so no mirror postings |
| Reconciliation | **MISSING** |
| Group reporting with eliminations | **MISSING** |

C2P's own group model is also encoded outside Odoo, in the
`c2p-intercompany-reserve-close` skill. **[DESIGN]** That skill is the de-facto
specification for FIN-05; it should become the module spec rather than being
re-derived.

---

## 8. Summary

| Process | Standard available | Custom links present | Tested | Verdict |
|---|---|---|---|---|
| L2C | Yes, complete | 2 (`sale.order`) | No | Unproven |
| P2P | Yes, complete | 2 (`purchase.order`) | No | **4 controls missing** |
| Inventory→Finance | Yes | 0 | No | Scope undecided (DEC-005) |
| Record→Report | Yes | CFO stack, role unclear | No | **DEC-004 blocks** |
| Project→Cash | Yes + strong custom | 7 | 57 tests, **NOT RUN** | Best candidate for first slice |
| HR→Finance | Yes (Community) | 0 | No | **Entirely absent** |
| Intercompany | Partial | 1 (`c2p_counterpart_id`) | No | Design exists outside Odoo |

**The one sentence that matters:** every process in this matrix is either standard
Odoo that nobody has exercised, or custom code that stops short of the ledger.
There is no process in this repository that has been demonstrated end to end, and
the fastest route to having one is Project→Cash, because it is the only process
where the custom work is already done.
