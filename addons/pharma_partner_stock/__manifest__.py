{
    "name": "Pharma Partner Stock from Stock Moves",
    "summary": "Fills the Distribution Partner stock roll-forward from real Odoo stock moves instead of typed numbers",
    "description": "For a run of type Distribution Partner stock, pick the partner's stock location and a period. "
                   "Opening, inward, sold/issued, returns and documented scrap are derived from done stock move lines that cross "
                   "the location's boundary. Approved adjustments and the partner's reported count stay manual. "
                   "Inventory-loss moves that are not documented scrap are never added silently: they show up as variance.",
    "version": "19.0.1.0.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["pharma_reconciliation_hub", "stock"],
    "data": ["views/pharma_recon_run_views.xml"],
    "installable": True,
}
