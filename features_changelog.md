# IG Square Pakistan — Odoo 19 Finance Build
## Functionalities delivered (for a demo video)

**Context:** Two custom modules were built on top of standard Odoo 19 Accounting
for IG Square Pakistan (Private) Limited. Nothing in core accounting was
replaced — everything is additive, so existing data and standard reports keep
working. Database: `Mumtaz_IG2`. Company: IG Square Pakistan (Private) Limited.

There are **two modules** plus **data setup**:
1. `mumtaz_financial_reports` — Pakistani financial statements.
2. `c2p_pk_vouchers` — PK-format vouchers + withholding tax + intercompany.
3. Data setup — withholding ledgers/bindings and expense products.

---

## Module 1 — Mumtaz Financial Statements (`mumtaz_financial_reports`)

A single wizard drives six financial reports, each with branded PDF and
single-page Excel output.

**Reports:**
- **Profit & Loss** — revenue, cost of sales, expense groups, net profit.
- **Balance Sheet** — assets, liabilities, equity as at a date.
- **Trial Balance** — every ledger with opening / debit / credit / closing; ties out.
- **General Ledger** — every transaction per account with a running balance.
- **Aged Receivable** — open customer balances bucketed by age (current / 30 / 60 / 90+).
- **Aged Payable** — same for vendors.

**Controls on the wizard:**
- Date range (and "as of" date for balance-type reports).
- **Account filter** — run the whole ledger or just selected accounts.
- **Partner filter** — narrow to a single customer/vendor.
- **Branded PDF** — company header, period, clean statement layout.
- **Excel export set to fit on a single page** for clean printing/sharing.

**Why it matters:** management- and auditor-ready statements on demand, without
exporting to spreadsheets and reformatting.

---

## Module 2 — C2P Pakistan Vouchers (`c2p_pk_vouchers`)

### 2a. All-in-one Payment / Receipt Voucher
A single screen to pay vendors or receive from customers:
- Choose **Payment (Send)** or **Receipt (Receive)**, pick the party.
- **Load Open Items** — pulls that party's unpaid bills/invoices with their
  open balances, each selectable, with an editable "To Pay" amount.
- **Bank/Cash journal**, **Cheque / Instrument No.**, **Cheque Date**, Narration.
- **Post Voucher** — creates the journal entry and knocks the invoices off
  (reconciles them) in one step.

### 2b. Dual withholding tax — the key feature
Two withholdings are handled on every payment, shown as **per-invoice columns**:
- **Income Tax WHT** (e.g. u/s 153) — charged on the amount paid.
- **Sales Tax WHT (WHST)** — charged on the **full GST** portion of the bill.
- **Net** column = To-Pay − both withholdings.

Each withholding is **bound to the vendor/customer** (set once) and posts to its
**own ledger**:
- Income-tax WHT payable ledger.
- Sales-tax WHT payable ledger.

So a payment produces correct double-entry automatically:
**Dr Trade Creditors (full invoice) / Cr Bank (net paid) / Cr Income-WHT ledger /
Cr Sales-WHT ledger**, with the bill marked Paid and reconciled.

### 2c. Withholding configuration at the vendor/customer level
On the partner's **Accounting** tab:
- Purchase WHT – Income Tax (+ rate + ledger)
- Purchase WHT – Sales Tax (+ rate + ledger)
- The customer-side equivalents (what a customer withholds from our receipts)

Set the rule once on the partner; every voucher uses it automatically.

### 2d. Withholding Codes master
A master list of PK withholding codes (section, scope income/sales, rate,
ledger). Seeded with common rates: 153(1)(a) Goods 4.5%, 153(1)(b) Services 10%,
153(1)(c) Contracts 7.5%, Sales-Tax Withholding 2%, 153 on-receipt 8%.

### 2e. PK-format voucher print
Payment / Receipt / Journal / Payable / Receivable vouchers print in the
Pakistani format: A/c Code · A/c Name · Cost Center · Job Code · Debit · Credit,
amount in words, "POSTED", and signature blocks.

### 2f. Invoice knock-off report
A report showing exactly which invoices/bills a given payment settled.

### 2g. WHT Deduction Certificate
A printable withholding-tax certificate to issue to the vendor for their records.

### 2h. Intercompany transfer
A toggle on the voucher to move funds to a group company's **Due-from / Due-to**
current account (balanced entry, no invoice knock-off).

### 2i. Journal Voucher control
A journal flagged as a "Journal Voucher" is blocked from carrying bank/cash
lines — so payments stay in the payment vouchers where they belong.

### 2j. Cost Center / Job Code
Analytic plans (Cost Center and Job Code) available for tagging, and shown on
the printed voucher.

---

## Data setup done in Mumtaz_IG2

- **WHT ledgers created & wired:** `WHT Payable – Income Tax (u/s 153)` and
  `WHT Payable – Sales Tax`, attached to the seeded withholding codes.
- **Sample vendor bound:** A.F.Ferguson & Co. — Income Tax WHT 153(1)(b)
  Services @ 10%, Sales Tax WHT @ 2%.
- **Expense products:** one purchasable Service product per expense ledger so
  the team picks a product on a vendor bill and the correct expense GL fills in
  automatically. Trimmed to ~102 genuinely billable expenses (payroll,
  depreciation, income tax, FX and contra accounts archived).

---

## Suggested demo flow (≈ 8 minutes)

1. **Intro** — IG Square finance on Odoo 19; two custom modules, all on top of
   standard Odoo.
2. **Financial statements** — run Profit & Loss (PDF), Trial Balance, Balance
   Sheet, General Ledger (with account/partner filter), Aged Receivable/Payable;
   show single-page Excel export.
3. **Vendor withholding config** — open A.F.Ferguson, Accounting tab; show the
   income-tax and sales-tax WHT bindings with their ledgers.
4. **Payment voucher** — pick the vendor, Load Open Items, show the per-line
   Income WHT / Sales WHT / Net columns, enter cheque details, Post.
5. **The posted entry** — Dr Creditors / Cr Bank (net) / Cr the two WHT ledgers;
   bill marked Paid/reconciled.
6. **Prints** — PK-format Payment Voucher, Invoice Knock-off, WHT Certificate.
7. **Extras** — Journal Voucher control (bank/cash blocked), Intercompany
   transfer toggle, expense products auto-filling the ledger on a bill.
8. **Close** — Pakistani statements on demand + withholding end-to-end +
   vouchers in the familiar format, all on standard Odoo.

### Example numbers to show (from the test bill)
- Open bill balance: 113,000.00
- Income Tax WHT @ 10% = 11,300.00
- Sales Tax WHT @ 2% of the bill's GST portion
- Net paid = 113,000 − 11,300 − (sales WHT)
