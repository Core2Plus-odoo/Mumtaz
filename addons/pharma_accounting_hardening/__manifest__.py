{
    "name": "Pharma Accounting Kit Hardening",
    "summary": "Closes two findings in the third-party Community accounting kit (unguarded Excel export route, support form that can send data to the vendor) and removes the vendor support button from the UI.",
    "description": "Installed on top of base_accounting_kit (a third-party Odoo 19 Community accounting add-on, LGPL-3). "
                   "1) /xlsx_report accepted any model name from any authenticated user and ran it as superuser; it now requires an "
                   "accounting group and a model that really is an exporter. 2) cybrosys_support_client lets every internal user "
                   "post free text and attachments to the vendor's server; the form is now administrator-only and its endpoint "
                   "points at a dead loopback address, so nothing can leave the server. Re-applied on every upgrade. 3) The vendor support button (top-bar headset icon and user-menu item) is removed from the web client. "
                   "Uninstall this module only with a written data-protection decision.",
    "version": "19.0.1.1.0",
    "category": "Pharma",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["base_accounting_kit", "base_account_budget", "cybrosys_support_client", "pharma_pk_tax_core"],
    "data": [
        "security/support_access.xml",
        "data/support_endpoint.xml",
    ],
    "assets": {
        "web.assets_backend": ["pharma_accounting_hardening/static/src/js/remove_vendor_support_ui.js"],
    },
    "installable": True,
}
