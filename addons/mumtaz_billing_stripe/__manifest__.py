{
    "name": "Mumtaz Billing — Stripe",
    "summary": "Stripe Payment Intents billing for tenant subscriptions with "
               "automatic charge, dunning and grace-then-suspend.",
    "version": "19.0.1.0.0",
    "category": "Mumtaz Platform",
    "author": "Mumtaz",
    "license": "LGPL-3",
    "depends": ["mumtaz_control_plane"],
    "data": [
        "security/ir.model.access.csv",
        "data/stripe_cron.xml",
        "views/stripe_settings_views.xml",
        "views/stripe_event_views.xml",
        "views/tenant_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
