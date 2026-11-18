{
    "name": "Pharma DEMO Data (fictional)",
    "summary": "FICTIONAL demonstration data. NEVER install on a production database.",
    "description": "Sets pharma.mode=demo and seeds every demonstrable scenario with fictional, "
                   "DEMO-flagged records: demo users (one per Pharma role), tax rules in every state, "
                   "SKU classifications approved/pending/proposed, tax events with a reversal, "
                   "reconciliation runs (clean match, variance, gateway payout, bank vs ledger), "
                   "exceptions in every state, Distribution Partner stock variance and an incomplete "
                   "scenario gate, raw-event duplicate and conflict, and a sale order / invoice pair "
                   "that the tax gate blocks. Idempotent: re-running the seeder adds nothing twice.",
    "version": "19.0.1.1.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["pharma_pk_tax_core", "pharma_reconciliation_hub", "sale_management", "account", "stock"],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
