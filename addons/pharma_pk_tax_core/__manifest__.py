{
    "name": "Pharma Pakistan Tax Core",
    "summary": "Effective-dated, approved-only tax rule engine; SKU tax classification; immutable tax events; posting gate",
    "description": "No rate is hardcoded. Unresolved treatment blocks posting. Rates must come from approved, sourced, effective-dated rules.",
    "version": "19.0.1.1.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["pharma_core", "account", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "data/pharma_tax_params.xml",
        "views/pharma_tax_rule_views.xml",
        "views/pharma_tax_event_views.xml",
        "views/product_views.xml",
        "views/pharma_tax_menus.xml",
    ],
    "installable": True,
}
