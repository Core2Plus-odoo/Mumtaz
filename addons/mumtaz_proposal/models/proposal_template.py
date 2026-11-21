from odoo import fields, models


class MumtazProposalTemplate(models.Model):
    _name = "mumtaz.proposal.template"
    _description = "Proposal Template"
    _order = "name"

    name = fields.Char(string="Template Name", required=True)
    description = fields.Text(string="Description")
    line_ids = fields.One2many(
        "mumtaz.proposal.template.line",
        "template_id",
        string="Lines",
        copy=True,
    )
    terms_conditions = fields.Html(string="Terms & Conditions")
    active = fields.Boolean(string="Active", default=True)
