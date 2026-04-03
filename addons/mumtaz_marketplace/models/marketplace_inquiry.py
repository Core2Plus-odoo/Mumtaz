from odoo import api, fields, models


class MumtazMarketplaceInquiry(models.Model):
    _name = "mumtaz.marketplace.inquiry"
    _description = "Mumtaz Marketplace Inquiry"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    listing_id = fields.Many2one(
        "mumtaz.marketplace.listing",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="cascade",
        default=lambda self: self.env.company,
    )
    inquirer_name = fields.Char(required=True)
    inquirer_email = fields.Char(required=True)
    inquirer_phone = fields.Char()
    inquirer_company = fields.Char()
    message = fields.Text(required=True)
    state = fields.Selection(
        [
            ("new", "New"),
            ("in_progress", "In Progress"),
            ("responded", "Responded"),
            ("closed", "Closed"),
        ],
        default="new",
        required=True,
        tracking=True,
    )
    response = fields.Text(tracking=True)
    responded_date = fields.Datetime(readonly=True)

    @api.depends("listing_id", "inquirer_name")
    def _compute_name(self):
        for rec in self:
            listing = rec.listing_id.name or ""
            inquirer = rec.inquirer_name or ""
            rec.name = f"Inquiry: {listing} — {inquirer}"

    def action_mark_in_progress(self):
        self.write({"state": "in_progress"})

    def action_respond(self):
        self.write({"state": "responded", "responded_date": fields.Datetime.now()})
        self.message_post(body=f"Response sent: {self.response}")

    def action_close(self):
        self.write({"state": "closed"})
