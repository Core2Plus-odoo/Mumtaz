from odoo import api, fields, models

from .secret_guard import refuse_secret


class C2pClientInstance(models.Model):
    """One system the client runs or C2P runs for them.

    An inventory row, not a provisioning record: it describes where an instance
    is, never how to get into it.
    """

    _name = "c2p.client.instance"
    _description = "C2P Client Instance"
    _order = "partner_id, environment, name"

    name = fields.Char(string="Instance", required=True)
    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, index=True,
        ondelete="cascade", domain="[('c2p_is_client', '=', True)]")
    project_id = fields.Many2one(
        "project.project", string="Solutions Project", index=True,
        domain="[('c2p_layer', '=', 'delivery'), ('partner_id', '=', partner_id)]")
    # Empty by default: a client is shared by Consultants and Solutions, and
    # the Solutions delivery owner must see what Consultants recorded. Set a
    # company to restrict a row to it.
    company_id = fields.Many2one("res.company", index=True)
    environment = fields.Selection(
        [("production", "Production"), ("staging", "Staging / UAT"),
         ("development", "Development"), ("training", "Training")],
        required=True, default="production")
    system = fields.Selection(
        [("odoo", "Odoo"), ("website", "Website"), ("integration", "Integration"),
         ("other", "Other")], required=True, default="odoo")
    version = fields.Char(help="For example: Odoo 19.0 Community.")
    hosting = fields.Selection(
        [("client", "Client-hosted"), ("c2p", "C2P-hosted"),
         ("odoo_sh", "Odoo.sh"), ("odoo_online", "Odoo Online"),
         ("other", "Other")])
    url = fields.Char(string="Address")
    database_name = fields.Char(string="Database")
    state = fields.Selection(
        [("planned", "Planned"), ("active", "Active"), ("retired", "Retired")],
        default="planned", required=True)
    notes = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        # Prefill the Solutions project when the client has exactly one, so
        # the common case needs no lookup.
        for vals in vals_list:
            if vals.get("partner_id") and not vals.get("project_id"):
                delivery = self.env["project.project"].search(
                    [("partner_id", "=", vals["partner_id"]),
                     ("c2p_layer", "=", "delivery")], limit=2)
                if len(delivery) == 1:
                    vals["project_id"] = delivery.id
        return super().create(vals_list)

    @api.constrains("name", "url", "database_name", "notes", "version")
    def _check_no_secret(self):
        for row in self:
            for fname in ("name", "url", "database_name", "notes", "version"):
                refuse_secret(row._fields[fname].string, row[fname])
