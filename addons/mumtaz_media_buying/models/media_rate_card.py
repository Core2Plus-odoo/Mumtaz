# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .media_outlet import MEDIA_CHANNELS

RATE_UNITS = [
    ("spot", "Spot (broadcast)"),
    ("insertion", "Insertion (print)"),
    ("cpm", "CPM (digital)"),
    ("cpc", "CPC (digital)"),
    ("site_month", "Site / Month (OOH)"),
    ("day", "Day"),
    ("package", "Package"),
    ("other", "Other"),
]


class MediaRateCard(models.Model):
    """A vendor's price list for media inventory, with a validity window.
    Negotiated rates live here so plans always price from an agreed card."""

    _name = "media.rate.card"
    _description = "Media Rate Card"
    _inherit = ["mail.thread"]
    _order = "date_from desc, id desc"

    name = fields.Char(required=True, tracking=True)
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain=[("is_media_vendor", "=", True)],
        tracking=True,
    )
    date_from = fields.Date(string="Valid From", required=True,
                            default=fields.Date.context_today)
    date_to = fields.Date(string="Valid Until")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("expired", "Expired"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )
    line_ids = fields.One2many("media.rate.card.line", "rate_card_id",
                               string="Rates")
    line_count = fields.Integer(compute="_compute_line_count")
    notes = fields.Text()

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(
                    self.env._("Valid Until must be after Valid From."))

    def action_activate(self):
        self.write({"state": "active"})

    def action_expire(self):
        self.write({"state": "expired"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})


class MediaRateCardLine(models.Model):
    """One purchasable format on one outlet: '30-sec prime-time spot on
    GEO TV', 'Full page colour in Dawn', 'Meta feed CPM', 'Site 12 / month'."""

    _name = "media.rate.card.line"
    _description = "Media Rate Card Line"
    _order = "rate_card_id, outlet_id, name"
    _rec_name = "display_label"

    rate_card_id = fields.Many2one(
        "media.rate.card", required=True, ondelete="cascade", index=True
    )
    outlet_id = fields.Many2one("media.outlet", required=True)
    channel = fields.Selection(
        MEDIA_CHANNELS, related="outlet_id.channel", store=True
    )
    vendor_id = fields.Many2one(
        related="rate_card_id.vendor_id", store=True
    )
    name = fields.Char(
        string="Format",
        required=True,
        help="What is being bought, e.g. '30-sec prime-time spot', "
             "'Full page colour', 'Feed CPM'.",
    )
    unit = fields.Selection(RATE_UNITS, required=True, default="spot")
    gross_rate = fields.Monetary(
        currency_field="currency_id",
        help="Published / card rate before negotiation.",
    )
    rate = fields.Monetary(
        string="Negotiated Rate",
        currency_field="currency_id",
        required=True,
        help="The rate the agency actually pays per unit.",
    )
    currency_id = fields.Many2one(related="rate_card_id.currency_id")
    state = fields.Selection(related="rate_card_id.state", store=True)
    display_label = fields.Char(compute="_compute_display_label")

    @api.depends("outlet_id.name", "name")
    def _compute_display_label(self):
        for rec in self:
            rec.display_label = (
                f"{rec.outlet_id.name} — {rec.name}"
                if rec.outlet_id and rec.name else (rec.name or "")
            )

    @api.constrains("rate")
    def _check_rate(self):
        for rec in self:
            if rec.rate < 0:
                raise ValidationError(
                    self.env._("A rate cannot be negative."))
