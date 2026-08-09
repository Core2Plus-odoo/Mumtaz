{
    "name": "Faizy Core",
    "summary": "Family care subscriptions, ground network and service delivery for Faizy",
    "description": """
Faizy — WhatsApp-first family care for Pakistanis living abroad.

Runs the whole operation inside Odoo Community:

* Subscription plans (Lite / Standard / Family Pro) with activity metering,
  a three-activity free grant and per-activity overage billing. Odoo Community
  has no Subscriptions app (Enterprise only), so recurring invoicing is built
  here on a scheduled action.
* A published price per currency on each plan. Subscribers live anywhere, so a
  plan carries a real local price per market instead of an FX conversion.
* Family members with permanent FMB IDs.
* The ground network — Faizies, their coverage and performance.
* A worker application pipeline feeding the roster.
* Service orders with assignment, proof of delivery and a stage kanban.
* Bridge requests and product-sourcing requests with a customer approval gate.
* Wallet ledger and WhatsApp notification queue.

Revenue model: subscriptions, a 5% platform fee on purchase value charged to the
customer, and 10% vendor commission retained from vendor-fulfilled orders.
""",
    "version": "19.0.1.4.1",
    "category": "Services",
    "author": "C2P Consultants FZC LLC",
    "website": "https://faizy.pk",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "contacts",
        "product",
        "account",
    ],
    "data": [
        "security/faizy_security.xml",
        "security/ir.model.access.csv",
        "data/faizy_sequences.xml",
        "data/faizy_plan_data.xml",
        "data/faizy_service_data.xml",
        "data/faizy_cron.xml",
        "views/faizy_plan_views.xml",
        "views/faizy_subscription_views.xml",
        "views/faizy_family_member_views.xml",
        "views/faizy_worker_views.xml",
        "views/faizy_application_views.xml",
        "views/faizy_order_views.xml",
        "views/faizy_request_views.xml",
        "views/faizy_document_views.xml",
        "views/faizy_wallet_views.xml",
        "views/faizy_whatsapp_views.xml",
        "views/res_partner_views.xml",
        "views/faizy_sample_data_views.xml",
        "views/faizy_dashboard_views.xml",
        "views/faizy_menus.xml",
    ],
    # A fresh Odoo database defaults its company to USD, which would make the
    # AED figures in faizy_plan_data.xml silently mean something else.
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": True,
}
