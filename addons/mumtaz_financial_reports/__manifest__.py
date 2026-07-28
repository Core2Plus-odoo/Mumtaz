{
    "name": "Mumtaz Financial Statements",
    "version": "19.0.1.0.0",
    "summary": "Profit & Loss, Balance Sheet and Trial Balance as branded PDF reports.",
    "description": """
Mumtaz Financial Statements
===========================
A lightweight financial-reporting toolkit for Odoo Community:

- **Profit & Loss** (income statement) for a date range
- **Balance Sheet** as of a date, with current-year earnings
- **Trial Balance** with debit / credit / balance per account

Each is produced as a clean, branded PDF from a simple wizard. Figures are read
directly from posted (or all) journal items, respect the selected company and
currency, and can hide zero-balance accounts. Depends only on ``account``.
""",
    "category": "Accounting/Accounting",
    "author": "Mumtaz",
    "website": "https://core2plus.com",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "report/financial_report_templates.xml",
        "report/report_action.xml",
        "views/financial_report_wizard_views.xml",
    ],
    "application": False,
    "installable": True,
}
