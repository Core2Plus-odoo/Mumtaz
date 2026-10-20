{
    "name": "C2P Pakistan Vouchers",
    "version": "19.0.1.0.0",
    "summary": "Payment / Receipt / Journal / Payable / Receivable vouchers "
               "in the Pakistani format, with invoice knock-off and JV controls.",
    "description": """
C2P Pakistan Vouchers
=====================
Presents standard Odoo accounting entries as Pakistani-style vouchers and adds
the controls IG Square requested — standard-first, built on top of
``account.move`` (no models recreated).

- **Voucher print format** (A/c Code · A/c Name · CC · J/C · Debit · Credit,
  amount in words, POSTED, signatures) rendered for:
  Payment Voucher, Receipt Voucher, Payable Voucher, Receivable Voucher and
  Journal Voucher — the title and layout adapt to the journal automatically.
- **Invoice knock-off** report — the invoices offset against a payment/receipt.
- **Cheque / instrument** number and date on bank & cash entries.
- **Journal Voucher control** — a journal flagged as a Journal Voucher cannot
  carry bank/cash lines, so payments/receipts stay in PV/RV only.

Not included yet (separate, quoted scope): the Pakistan income-tax / sales-tax
withholding engine and intercompany auto-mirroring.
""",
    "category": "Accounting/Accounting",
    "author": "C2P Consultants",
    "website": "https://core2plus.com",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
        "report/voucher_reports.xml",
        "report/voucher_templates.xml",
        "report/knockoff_templates.xml",
    ],
    "installable": True,
    "application": False,
}
