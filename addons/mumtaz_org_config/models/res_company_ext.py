"""Extend res.company with the mumtaz_org_slug field for subdomain routing."""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    mumtaz_org_slug = fields.Char(
        string="Mumtaz Slug",
        index=True,
        copy=False,
        help="Subdomain slug that routes to this company (e.g. 'acme' → acme.mumtaz.digital).",
    )
    mumtaz_org_id = fields.Many2one(
        "mumtaz.org",
        string="Mumtaz Organisation",
        compute="_compute_mumtaz_org_id",
        store=False,
    )

    def _compute_mumtaz_org_id(self):
        for company in self:
            org = self.env["mumtaz.org"].sudo().search(
                [("company_id", "=", company.id)], limit=1
            )
            company.mumtaz_org_id = org
