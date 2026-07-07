# -*- coding: utf-8 -*-
{
    "name": "Mumtaz Financial Statements",
    "version": "19.0.1.0.0",
    "summary": "Standard-format P&L, Balance Sheet, Trial Balance and Aged "
               "Partners — on-screen, foldable, drill-down, printable.",
    "description": """
Mumtaz Financial Statements
===========================
Clean, standard-format financial statements rendered on-screen as an OWL client
action, computed live from the chart of accounts and posted journal entries:

* Statement of Profit & Loss — Revenue, Cost of Sales, Gross Profit, Operating
  Expenses, Operating Profit, Other Income, Net Profit — with prior-period
  comparison and variance %.
* Statement of Financial Position (Balance Sheet) — Assets / Equity &
  Liabilities, current vs non-current, with a live balance check.
* Trial Balance — closing debit/credit per account, footed.
* Aged Partners — receivables & payables in Current / 1-30 / 31-60 / 60+ buckets.

Interactive: date-range picker, foldable sections, drill-down from any line into
the underlying journal items, and Print / PDF. Grouping is by Odoo account type,
so it works with any chart of accounts. Depends only on ``account`` + ``web``.
""",
    "author": "Core2Plus",
    "website": "https://mumtaz.digital",
    "category": "Accounting/Reporting",
    "license": "LGPL-3",
    "depends": ["web", "account"],
    "data": [
        "views/financial_reports_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mumtaz_financial_reports/static/src/scss/financial_reports.scss",
            "mumtaz_financial_reports/static/src/xml/financial_reports.xml",
            "mumtaz_financial_reports/static/src/js/financial_reports.js",
        ],
    },
    "installable": True,
    "application": True,
}
