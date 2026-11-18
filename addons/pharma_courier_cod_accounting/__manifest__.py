{
    "name": "Pharma Courier COD Accounting",
    "summary": "Draft journal entry for a reconciled courier COD remittance. Never posts by itself.",
    "description": "Adds the accounts a courier's settlement uses (clearing, bank, freight, COD fee, withholding income "
                   "tax, withholding sales tax, other deductions, difference) and one action on a reconciled remittance: "
                   "Create journal entry. The entry is a DRAFT: credit the courier COD clearing account with the gross "
                   "remitted, debit the bank account with the amount actually received and each deduction to its own "
                   "account, with any difference booked to the difference account. Posting stays with the accountant.",
    "version": "19.0.1.0.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["pharma_courier_cod", "account"],
    "data": ["views/courier_views.xml", "views/remittance_views.xml"],
    "installable": True,
}
