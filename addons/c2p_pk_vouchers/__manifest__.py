{
    "name": "C2P Pakistan Vouchers",
    "version": "19.0.4.1.0",
    "summary": "PK-format Payment/Receipt/Journal/Payable/Receivable vouchers, "
               "invoice knock-off, JV control, withholding tax + certificate, "
               "intercompany marker and Cost Center / Job Code analytic plans.",
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

- **Withholding tax** bound to the partner (Purchase WHT / Sales WHT). On the
  Register Payment screen the applicable code is suggested automatically, the
  net payable and withholding amount are shown, and the deduction is posted to
  its WHT ledger (via the standard payment-difference write-off) while the
  invoice is knocked off in full. A WHT Deduction Certificate can be printed.

Separate, quoted scope not included: intercompany auto-mirroring across
companies.
""",
    "category": "Accounting/Accounting",
    "author": "C2P Consultants",
    "website": "https://core2plus.com",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "data/analytic_plans.xml",
        "data/wht_tax_data.xml",
        "report/voucher_reports.xml",
        "report/voucher_templates.xml",
        "report/knockoff_templates.xml",
        "report/wht_certificate_templates.xml",
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
        "views/res_partner_views.xml",
        "views/account_payment_register_views.xml",
        "views/payment_voucher_views.xml",
        "views/wht_views.xml",
    ],
    "installable": True,
    "application": False,
}
