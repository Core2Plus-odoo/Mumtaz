{
    "name": "C2P Order Projects",
    "summary": "One confirmation creates and pairs the oversight and delivery projects",
    "description": """
C2P Order Projects
==================
When a sale order with a project-creating product is confirmed, this module
makes sure the order has exactly one oversight project and one delivery
project, and pairs them in the Project Tracker.

* The oversight project is the one the standard Sales Project flow creates
  (Consultants). This module tags it with the order and the role "oversight".
* The delivery project is created here, from a template, in the delivery
  company (Solutions), and tagged with the same order and the role "delivery".
* The pair is keyed on the order: a database index allows one oversight and
  one delivery project per order. An archived project still counts as
  existing, so confirming again never creates a replacement. Templates are
  never matched.
* An order with more than one project line gets no delivery project: the
  standard flow already made a second project, and a delivery project on top
  would be a second delivery-shaped project. A note on the order says so.
* Confirming never fails because of this module: a problem is logged and
  written as a note on the order.

Setting up a product (for example T01): the standard template link
("Project Template") is the Consultants oversight template. The delivery
template goes in the product's own "Delivery Project Template" field. Never
link the delivery template as the standard template: the standard flow would
then create the delivery project itself and there would be no oversight one.

Nothing happens until it is switched on with system parameters:

* ``c2p.order_projects.enabled``: 1 to switch on.
* ``c2p.order_projects.delivery_company_id``: id of the delivery company.
* ``c2p.order_projects.default_delivery_template_id``: id of the default
  delivery template project (a product can set its own).
* ``c2p.order_projects.pair_in_tracker``: 0 to skip the Project Tracker
  pairing (default 1).

No emails, no scheduled jobs, no access rules. Community only.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "C2P Consultants",
    "license": "LGPL-3",
    "depends": ["sale_project", "c2p_project_tracker"],
    "data": [
        "views/project_project_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
