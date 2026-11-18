{
    "name": "Pharma Reconciliation Hub",
    "summary": "COD / gateway / bank matching, exception queue with maker-checker, Distribution Partner stock roll-forward, scenario gate",
    "version": "19.0.1.0.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["pharma_core"],
    "data": [
        "security/ir.model.access.csv",
        "views/pharma_recon_views.xml",
        "views/pharma_partner_views.xml",
        "views/pharma_recon_menus.xml",
    ],
    "installable": True,
}
