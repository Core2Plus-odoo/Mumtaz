{
    "name": "C2P Proposal Maker",
    "version": "19.0.13.0.0",
    "summary": "One-click proposal builder — tick the services a client needs and "
               "generate a complete, branded, narrative Odoo ERP proposal (PDF).",
    "description": """
C2P Proposal Maker
==================
A single window where a salesperson ticks the required modules/services and a
complete, formatted proposal is generated: cover page, executive summary,
understanding of requirements, in-scope modules, 8-phase implementation
methodology, deliverables, roles, assumptions, commercial pricing table, AMC,
why-choose-C2P and an acceptance/signature block — all rendered as a branded
QWeb PDF on top of a real Odoo quotation.
""",
    "category": "Sales",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["sale_management", "crm"],
    "data": [
        "security/ir.model.access.csv",
        "report/proposal_report.xml",
        "views/proposal_wizard_views.xml",
        "views/crm_lead_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
