{
    "name": "Pharma Courier COD Accounting",
    "summary": "Draft journal entries for courier COD: the collection (courier holds the customer's cash) and the settlement (courier remits it). Never posts by itself.",
    "description": "Adds the accounts a courier's settlement uses (clearing, bank, freight, COD fee, withholding income "
                   "tax, withholding sales tax, other deductions, difference) and one action on a reconciled remittance: "
                   "Create journal entry. The entry is a DRAFT: credit the courier COD clearing account with the gross "
                   "remitted, debit the bank account with the amount actually received and each deduction to its own "
                   "account, with any difference booked to the difference account. Posting stays with the accountant. A posted entry can be withdrawn: Finance asks "
                   "with a reason, Odoo's own reversal is created as a DRAFT, and once an accountant posts it a corrected "
                   "entry can be created.",
    "version": "19.0.1.3.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["pharma_courier_cod", "account"],
    "data": ["security/ir.model.access.csv", "views/courier_views.xml", "views/remittance_views.xml", "views/shipment_views.xml",
             "views/reverse_wizard_views.xml", "views/flow_views.xml"],
    "installable": True,
}
