# IG Square Pakistan — Odoo Finance Demo
### Narration script + shot list (≈ 7–8 minutes)

Two custom modules on Odoo 19 for IG Square:
- **Mumtaz Financial Statements** — P&L, Balance Sheet, Trial Balance, General Ledger, Aged Receivable/Payable, with branded PDF + single-page Excel.
- **C2P Pakistan Vouchers** — PK-format Payment/Receipt/Journal vouchers, invoice knock-off, dual withholding (income tax + sales tax) bound to the vendor, WHT certificate, intercompany transfer, Cost Center / Job Code.

Record at **1920×1080**, browser full-screen, on `http://187.77.128.199:8071/` (Mumtaz_IG2).
Timings are a guide — pause on each number long enough to read it.

---

## Scene 1 — Intro (0:00–0:25)
**Show:** Accounting dashboard.
**Say:**
> "This is IG Square Pakistan's accounting on Odoo 19. On top of standard Odoo we've added two things your finance team asked for: a full set of Pakistani financial statements, and a voucher system with withholding tax built in. Everything is built *on top of* standard Odoo — no core accounting was replaced — so all your existing data and reports keep working."

---

## Scene 2 — Financial Statements: Profit & Loss (0:25–1:25)
**Show:** Accounting → Reporting → *Mumtaz Financial Statements* (wizard). Pick **Profit & Loss**, set the date range (e.g. 1 Jan – 31 Dec), click **Print / PDF**.
**Say:**
> "First, the financial statements. One screen drives all of them. I'll pick Profit and Loss, choose the period, and generate. The output is a branded PDF — company header, the period, revenue, cost of sales, and the expense groups you just saw in the chart, down to net profit. This is the statement you can hand to management or auditors as-is."

---

## Scene 3 — Trial Balance & Balance Sheet (1:25–2:20)
**Show:** Back to wizard → **Trial Balance** → generate (show opening / debit / credit / closing). Then **Balance Sheet** → generate.
**Say:**
> "The same screen gives the Trial Balance — every ledger with its debit and credit and closing balance, and it ties out at the bottom. And the Balance Sheet — assets, liabilities and equity as at the reporting date. One tool, consistent formatting across all three."

---

## Scene 4 — General Ledger with filters (2:20–3:15)
**Show:** Wizard → **General Ledger**. Set date range, then set the **Accounts** filter to one or two accounts (e.g. a bank and an expense), optionally a **Partner**. Generate; show the per-account movement with running balance.
**Say:**
> "For detail work there's the General Ledger. You can run the whole ledger, or filter to specific accounts — here a bank account and an expense — and even to a single partner. You get every transaction with a running balance, so reconciling or answering an auditor's query is a two-minute job instead of an export-and-filter exercise."

---

## Scene 5 — Aged Receivable / Payable (3:15–3:55)
**Show:** Wizard → **Aged Receivable** → generate (buckets). Then **Aged Payable**.
**Say:**
> "Aged Receivable and Aged Payable bucket every open balance by age — current, 30, 60, 90 and beyond — per customer and per vendor. This is your collections and payables prioritisation list, straight from the live ledger."

---

## Scene 6 — Excel export, single page (3:55–4:20)
**Show:** On any report, click **Excel**; open the file; show it fits on one page (Page Layout / print preview).
**Say:**
> "Every one of these also exports to Excel — and we've set it to fit on a single page, so it prints and shares cleanly without you fixing column widths."

---

## Scene 7 — Vendor withholding configuration (4:20–5:05)
**Show:** Vendors → **A.F.Ferguson & Co.** → **Accounting** tab. Point at **Purchase WHT – Income Tax** (153(1)(b) Services, 10%) with its ledger, and **Purchase WHT – Sales Tax** (2%) with its ledger.
**Say:**
> "Now withholding. The rule is set once, on the vendor. Here A.F.Ferguson is a services provider, so income-tax withholding is 153(1)(b) at ten percent, and we deduct two percent sales-tax withholding on the GST. Each is tied to its own ledger — income-tax WHT payable and sales-tax WHT payable — right here on the vendor. Set it once; every payment uses it automatically."

---

## Scene 8 — Payment Voucher with dual WHT (5:05–6:30)
**Show:** Accounting → **Payment / Receipt Voucher** → Payment (Send) → Party = A.F.Ferguson → **Load Open Items**. Point at the **Income WHT**, **Sales WHT**, **Net** columns on the bill row and the footer totals. Fill **Bank/Cash Journal** (Faysal Bank) + **Cheque No.** + Narration. Click **Post Voucher**.
**Say:**
> "This is the all-in-one payment voucher. I choose the vendor and Load Open Items — every unpaid bill appears. Notice the extra columns: for each bill it computes income-tax WHT at ten percent, sales-tax WHT on the GST portion, and the net payable — all from the vendor setup, no manual tax entry. I pick the bank, enter the cheque number, and post."

---

## Scene 9 — The posted entry (6:30–7:00)
**Show:** The resulting journal entry's Journal Items: Dr Trade Creditors (full bill), Cr Bank (net), Cr WHT Income ledger, Cr WHT Sales ledger. Open the bill and show it as **Paid / reconciled**.
**Say:**
> "And here's the accounting it produced: the vendor is debited for the full invoice, the bank is credited the net amount actually paid, and each withholding goes to its own payable ledger. The bill is knocked off and marked paid — fully reconciled. One screen, correct double-entry, both taxes split to the right accounts."

---

## Scene 10 — Voucher print, knock-off, WHT certificate (7:00–7:40)
**Show:** On the entry: **Print → Payment Voucher** (PK format with amount in words + signatures). Then **Print → Invoice Knock-off**. Then the **WHT Deduction Certificate**.
**Say:**
> "From the same entry you print the voucher in the Pakistani format — account codes, cost centre, amount in words, signature blocks. There's an invoice knock-off showing exactly which bills this payment settled. And a withholding-tax deduction certificate you can issue to the vendor for their records."

---

## Scene 11 — Extras: Journal Voucher control, intercompany, expense products (7:40–8:15)
**Show (briefly):**
- A journal flagged **Journal Voucher** — try adding a bank/cash line → it's blocked.
- The voucher's **Intercompany Transfer** toggle (Due-from/Due-to + amount).
- A new vendor bill: pick an **expense product** (e.g. "Rent") → the expense ledger auto-fills.
**Say:**
> "A few controls to finish. A journal marked as a Journal Voucher can't carry bank or cash lines, so payments stay in the payment vouchers where they belong. The voucher also handles intercompany transfers to a group company's current account. And we've set up expense products — pick 'Rent' on a bill and the correct expense ledger fills in automatically, so data entry is fast and consistent."

---

## Scene 12 — Close (8:15–8:30)
**Show:** Back to dashboard.
**Say:**
> "That's the package: Pakistani financial statements on demand, withholding handled from the vendor through to the certificate, and vouchers in your familiar format — all on standard Odoo, ready for your team to use."

---

### Prep checklist before recording
- Log in on `:8071` (Mumtaz_IG2) as an accounting user.
- Have one **posted, unpaid vendor bill** for A.F.Ferguson with some GST (so Sales WHT shows non-zero).
- Confirm the WHT ledgers + vendor bindings are set (already done).
- Pick a date range that actually contains data for the statements.
- Hard-refresh the browser so the latest module version renders.
