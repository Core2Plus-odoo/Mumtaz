# 8b. Accounting posting rules and control-account reconciliation

**Status: Draft until the named finance manager approves (D-06).** Account
*categories* below are Odoo's standard behaviour with automated valuation
and the country chart installed; they are patterns, not statutory entries.
Nothing in code posts outside `account`'s own methods [VERIFIED].

| Business event | Preconditions | Debit | Credit | Tax | Dimensions | Correction | Reconciliation source | Approval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Customer invoice posted (incl. Jawhar sale with frozen rate) | posted by accountant; lock date open; tax from fiscal position | Receivable | Revenue + VAT payable | per `l10n_*` | company, analytic (branch), salesperson | credit note | AR aged vs receivable control | accountant |
| Customer payment (counter cash/card, bank) | journal open | Bank / cash / card clearing | Receivable | none | company, journal | authorised reversal | bank statement vs bank account | counter (Jawhar) / accountant |
| Old-gold exchange credit (Jawhar) | valuation approved above threshold | Old-gold stock (interim) | Customer credit / receivable | per policy | company | reversal of intake | old-gold register vs interim account | manager (threshold) |
| Vendor bill posted | PO/receipt match within tolerance | Expense or stock interim (GRNI) + input VAT | Payable | per `l10n_*` | company, analytic | supplier credit | AP aged vs payable control; GRNI clearing | accountant |
| Goods receipt (automated valuation) | PO cost known | Stock valuation | GRNI (stock input) | none | warehouse | return | valuation report vs stock account | warehouse |
| Delivery / counter sale (automated valuation) | piece or quantity on hand | COGS | Stock valuation (stock output) | none | warehouse | return picking | valuation vs stock account | warehouse / counter |
| Inventory adjustment (reconciliation variance, Jawhar) | count closed by manager | Inventory loss / gain | Stock valuation | none | store | reverse adjustment | count record vs adjustment | manager |
| Inter-store transfer (Jawhar) | same company | none | none | none | — | lost → write-off entry by finance | transfer vs count | finance for loss |
| Intercompany recharge (C2P Consultants ↔ Solutions) | matching mirrored documents | Due-from / service cost | Due-to / service revenue | jurisdiction review | company pair | mirrored credit | mirror balances | finance [DECISION] |
| Subscription billing of tenants (Stripe) | Stripe event | Bank / Stripe clearing | Revenue + VAT | per company | platform company | refund event | Stripe payouts vs clearing | platform finance |
| Payroll | out of scope (deferred) | | | | | | | |

Rules that bind the code [PROPOSED → DEVELOPMENT_STANDARDS]:

1. No custom module creates `account.move` lines directly; it calls the
   standard document flows (invoice from order, payment register, inventory
   adjustment) so the posting rules above hold by configuration.
2. Money is `Monetary` with the company currency and the document currency
   both stored; the Jawhar engine computes with fixed decimals and the rate
   snapshot is stored on the line and the invoice line.
3. Posted moves are corrected by reversal or credit note only (ADR-011).
4. Monthly: AR, AP, bank and stock subledgers reconciled to control accounts;
   the signed reconciliation goes into `docs/erp/quality/` (FIN-REQ-003).
