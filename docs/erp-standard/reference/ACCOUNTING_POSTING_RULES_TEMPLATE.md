# Accounting Posting Rules and Control-Account Reconciliation

**Jurisdiction/accounting policy owner:**  
**Framework/localization:**  
**Valuation method and revenue recognition policy:**  
**Status:** Draft until accountant approved.

| Business event | Preconditions | Debit account category | Credit account category | Tax effect | Dimensions | Reversal/correction | Reconciliation source | Approval |
|---|---|---|---|---|---|---|---|---|
| Customer invoice posted | valid company/customer/tax/period | Receivable | Revenue + applicable tax liability | Based on localization | company/project/cost center | credit note/reversal | customer subledger vs GL | |
| Customer payment reconciled | cleared receipt per bank policy | Bank or clearing | Receivable | no additional tax absent jurisdiction rule | company/partner | authorized reversal | bank + AR | |
| Vendor bill posted | valid supplier and match policy | expense/asset/stock-clearing + eligible input tax | Payable | based on localization | company/project/cost center | supplier credit | supplier subledger vs GL | |
| Inventory receipt/issue | costing and valuation policy met | policy-dependent | policy-dependent | configured policy | warehouse/cost center | return/reversal | valuation report vs GL | |
| Payroll posted | approved pay run | payroll expense/allocated WIP | payroll liabilities/payable | country policy | employee dept/project | controlled adjustment | payroll register vs GL | |
| Intercompany recharge | matching legal companies/policy | due-from or service cost | due-to or service revenue | jurisdiction-reviewed | company/service center | mirrored credit/debit | mirror balances and eliminations | |

**Caution:** The above account categories illustrate patterns and must not be treated as complete statutory entries. Confirm timing, accrual vs perpetual inventory, tax eligibility, FX, withholding, discounts, rounding and recognition with the client accountant before implementation.
