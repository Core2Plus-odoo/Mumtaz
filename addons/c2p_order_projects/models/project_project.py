from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    c2p_source_order_id = fields.Many2one(
        "sale.order", string="Source Order", copy=False, readonly=True,
        index="btree_not_null", ondelete="restrict",
        help="The confirmed order this project was made for.")
    c2p_project_role = fields.Selection(
        [("oversight", "Oversight (Consultants)"),
         ("delivery", "Delivery (Solutions)")],
        string="Order Project Role", copy=False, readonly=True,
        help="Which of the two projects of the order this is.")

    # One oversight and one delivery project per order. Templates and rows
    # without an order are outside the key. Archived projects are inside it.
    _c2p_order_role_unique = models.UniqueIndex(
        "(c2p_source_order_id, c2p_project_role) "
        "WHERE c2p_source_order_id IS NOT NULL AND is_template IS NOT TRUE",
        "An order can have only one oversight and one delivery project.")
