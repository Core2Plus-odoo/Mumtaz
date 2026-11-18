{
    "name": "Pharma Courier COD DEMO Data (fictional)",
    "summary": "FICTIONAL courier COD scenarios. NEVER install on a production database.",
    "description": "Seeds two fictional couriers (Courier A, Courier B) with every COD scenario the ledger handles: "
                   "a clean batch, a customer who paid less, a courier that remitted less, a bank variance, "
                   "deductions above the authorized amount, one shipment per ageing bucket, a returned parcel with "
                   "COD collected, a parcel with no matching sale order, an upload with row errors and an upload "
                   "that was built. Points the courier accounts at fictional accounts and creates DRAFT settlement and collection "
                   "journal entries. Ships two sample CSV files for the live upload demonstration. Idempotent.",
    "version": "19.0.1.2.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["pharma_courier_cod", "pharma_courier_cod_accounting", "pharma_demo_data"],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
