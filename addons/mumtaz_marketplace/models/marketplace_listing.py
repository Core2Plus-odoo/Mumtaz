from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MumtazMarketplaceListing(models.Model):
    _name = "mumtaz.marketplace.listing"
    _description = "Mumtaz Marketplace Listing"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "published_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="cascade",
        default=lambda self: self.env.company,
    )
    category_id = fields.Many2one(
        "mumtaz.marketplace.category",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    listing_type = fields.Selection(
        [("product", "Product"), ("service", "Service"), ("partnership", "Partnership")],
        required=True,
        default="service",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("published", "Published"),
            ("closed", "Closed"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    description = fields.Html(required=True)
    short_description = fields.Char(
        help="One-line summary shown in listing cards",
        required=True,
    )
    price = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    price_type = fields.Selection(
        [
            ("fixed", "Fixed Price"),
            ("from", "Starting From"),
            ("negotiable", "Negotiable"),
            ("free", "Free"),
        ],
        default="negotiable",
        required=True,
    )
    contact_name = fields.Char()
    contact_email = fields.Char()
    contact_phone = fields.Char()
    website_url = fields.Char()
    published_date = fields.Datetime(readonly=True)
    inquiry_count = fields.Integer(compute="_compute_inquiry_count")
    tag_ids = fields.Many2many("mumtaz.marketplace.tag", string="Tags")

    def _compute_inquiry_count(self):
        for rec in self:
            rec.inquiry_count = self.env["mumtaz.marketplace.inquiry"].search_count(
                [("listing_id", "=", rec.id)]
            )

    def action_publish(self):
        for rec in self:
            if not rec.description or not rec.short_description:
                raise ValidationError("Please complete description before publishing.")
            rec.write({"state": "published", "published_date": fields.Datetime.now()})
            rec.message_post(body="Listing published to marketplace.")

    def action_close(self):
        self.write({"state": "closed"})
        self.message_post(body="Listing closed.")

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_view_inquiries(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Inquiries",
            "res_model": "mumtaz.marketplace.inquiry",
            "view_mode": "list,form",
            "domain": [("listing_id", "=", self.id)],
            "context": {"default_listing_id": self.id},
        }


class MumtazMarketplaceTag(models.Model):
    _name = "mumtaz.marketplace.tag"
    _description = "Marketplace Tag"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer()
