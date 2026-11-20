# 09. UI/UX design system and dashboard architecture

Principle (blueprint §11): clean, modern, high-trust, **task-first**; accessibility and dense-data readability beat decoration. Use Odoo's standard list/form/pivot/search/chatter components; custom UI only where a standard component cannot do the job. What exists today is labelled `[V]`; everything else is `[P]`.

## 1. Information architecture

`[V]` One **app per business area** in the app switcher, each with its own icon and menus, each owned by its module: Tax Centre · Reconciliation · Distribution Partner · Courier COD · Pharma Admin (written, not yet deployed), beside the standard Sales, Website, Inventory, Purchase, Accounting. `[P]` Grow by the same rule (Inventory & Quality, Reporting) instead of adding items to one menu.

Every app follows one shape `[P]`:

| Section | Purpose | Courier COD today |
| --- | --- | --- |
| **Overview** (first menu) | Where things stand | Pipeline pivot (stage × courier, money outstanding) |
| **Work** | What needs me, by owner | Work Queue grouped by next step; Entries to Post (accountants) |
| **Records** | The documents | Shipments, Remittances, Statement Uploads |
| **Reports** | Analysis with drill-down | COD Ageing |
| **Configuration** | Rare, restricted | Couriers (Administrator) |

## 2. Navigation, search and filters

- App switcher is the only top-level navigation; deep links open records, never summary pages.
- Every work list has a **search view** with: owner filters (Operations / Finance Controller / Accountant), a "needs action" filter, status filters, and group-bys that match the process (next step, courier, stage). `[V]` Work Queue (written).
- Global search is Odoo's; do not build a second one `[P]`.
- Forms show the **next step banner** with its owner, the document state, source and target documents, the chatter timeline and the attachment zone. `[V]` parcel and remittance forms (written).

## 3. Design tokens `[P]`

Backend uses Odoo's standard theme; custom colour appears in **app icons** and **semantic status** only. Tokens already chosen for the app icons: teal `#0f766e` (tax), blue `#1d4ed8` (reconciliation), violet `#6d28d9` (partner), terracotta `#c2410c` (courier), slate `#475569` (admin). The wellness storefront has its own theme (terracotta ribbon `DEMO ENVIRONMENT`, soft pastel pack art) and **does not share CSS with the backend**.

| Semantic | Use | Rule |
| --- | --- | --- |
| Danger (red) | overdue, variance, blocked, deductions above authorized | always paired with text; never colour alone |
| Warning (amber) | customer paid less, open finding | |
| Info (blue) | next step banner | |
| Muted | cancelled, returned | |

Typography/spacing: Odoo defaults; keep numeric columns right-aligned with sums in list footers; show currency explicitly once multi-currency exists (gap G-2).

## 4. Forms, lists and states

- Primary action is one button, shown only when valid; invalid actions are hidden *and* refused server-side with a specific message naming the cause and the fix (parcels, missing accounts, required reason).
- Empty states state what appears there and why (`No COD entries are waiting`); errors never show stack traces; drafts are recoverable.
- Bulk actions (list Action menu) are **all or nothing** and name each failing record.
- Entries are **draft-first**: the UI always shows "created as draft, an accountant posts it".

## 5. Role homes and dashboards `[P]`

Dashboards read from **approved models or read-only SQL views with a written definition**; each tile states its definition, filters (company, period, currency) and drills to the records. No tile without lineage.

| Role | Home | Tiles (definition → source) |
| --- | --- | --- |
| Operations | Work Queue filtered to Operations | Parcels awaiting delivery; no-matching-order findings |
| Finance Controller | Pipeline + Work Queue (Finance) | COD outstanding by courier and ageing bucket (`cod_outstanding` by `cod_ageing_bucket`); overdue count; slips to reconcile; open exceptions by category |
| Accountant | Entries to Post | draft COD entries by kind and age |
| Tax Approver | Tax Centre | rules and classifications pending approval; blocked SKUs |
| Owner / CFO | KPI page | courier shortfall % (`Σ remittance variance ÷ Σ collected`), remittance speed (days from delivery to posted slip), return rate, DSO once AR is wired; each with a definition card |
| Group (later) | cross-tenant view | only with a platform-level read model and stated elimination/conversion treatment |

`[P]` KPI definitions live in `docs/erp/` as a metric dictionary (id, formula, source model, filters, owner); a tile may not ship without an entry (backlog BI-001).

## 6. Responsiveness, accessibility, language

- Target WCAG 2.2 AA as a benchmark: keyboard-operable actions, visible focus, text alternatives for icons, colour not the only signal, contrast of status chips.
- Responsive: Odoo's responsive forms/lists; verify the Work Queue and Entries to Post on tablet width `[P]`.
- Language: English now; Arabic/RTL is a requirement for the jewellery product (decision recorded there) and must be tested per screen where in scope.
- The storefront must keep its no-health-claims rule and the DEMO ribbon.

## 7. UX verification `[P]`

| Check | How | Status |
| --- | --- | --- |
| Role journeys (C1–C17 presenter script) | owner browser pass as each login | **NOT RUN** (the only evidence of screen-level correctness) |
| Automated UI | Odoo tours in CI on a throwaway database | not built |
| Accessibility | keyboard walkthrough + automated linter pass | not run |
| Visual regression | screenshots stored with each release | not run; the cloud session cannot open a browser against staging |
