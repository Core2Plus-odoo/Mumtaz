{
    "name": "Pharma Courier COD Ledger",
    "summary": "Cash on delivery by courier: shipment ledger with declared, collected and remitted amounts, ageing, remittance batches with itemised deductions, and statement upload.",
    "description": "Pakistan-oriented cash-on-delivery control for a distributor that ships through couriers. "
                   "One shipment record per parcel; COD tracked from declared to collected to remitted; ageing from the delivery date in the "
                   "0-7 / 8-15 / 16-30 / 31+ day buckets; remittance batches with the deductions kept itemised (freight, COD fee and the "
                   "two withholding taxes, which are recoverable receivables, not costs); batches reconcile through the Pharma "
                   "Reconciliation Hub, so every variance lands in its exception queue with maker-checker. Courier files are uploaded "
                   "through Odoo's own import screen onto staging lines, validated row by row, then built into documents; every row is "
                   "archived in the immutable raw-event log. No rate is hard-coded: deductions are facts reported by the courier, "
                   "checked against an authorized amount when Finance supplies one.",
    "version": "19.0.1.1.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["pharma_core", "pharma_reconciliation_hub", "sale", "base_import"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/pharma_courier_views.xml",
        "views/pharma_shipment_views.xml",
        "views/pharma_remittance_views.xml",
        "views/pharma_statement_views.xml",
        "views/pharma_flow_views.xml",
        "views/pharma_courier_menus.xml",
        "data/ir_cron_data.xml",
    ],
    "installable": True,
}
