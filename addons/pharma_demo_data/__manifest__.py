{
    "name": "Pharma DEMO Data (fictional)",
    "summary": "FICTIONAL demonstration data. NEVER install on a production database.",
    "description": "Sets pharma.mode=demo, creates DEMO products, DEMO-rate tax rules (placeholders, not real rates), "
                   "reconciliation runs, Distribution Partner stock lines and exceptions. Every record is flagged DEMO.",
    "version": "19.0.1.0.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["pharma_pk_tax_core", "pharma_reconciliation_hub"],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
