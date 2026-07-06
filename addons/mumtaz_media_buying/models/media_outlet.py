# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Channel taxonomy shared by outlets, rate-card lines and plan lines.
# The CEO dashboard buckets radio together with tv.
MEDIA_CHANNELS = [
    ("tv", "TV"),
    ("radio", "Radio"),
    ("print", "Print"),
    ("digital", "Digital & Social"),
    ("ooh", "Outdoor (OOH)"),
]


class MediaOutlet(models.Model):
    """A property media is bought on: a TV channel, a newspaper, a digital
    platform, a billboard site — always owned by one media vendor."""

    _name = "media.outlet"
    _description = "Media Outlet"
    _order = "channel, name"

    name = fields.Char(required=True)
    channel = fields.Selection(MEDIA_CHANNELS, required=True, default="tv")
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain=[("is_media_vendor", "=", True)],
        ondelete="restrict",
    )
    audience = fields.Char(
        help="Audience descriptor, e.g. 'National, urban 18-45' or "
             "'Lahore ring-road traffic'.",
    )
    notes = fields.Text()
    active = fields.Boolean(default=True)
    rate_line_count = fields.Integer(compute="_compute_rate_line_count")

    def _compute_rate_line_count(self):
        # grouped read keeps this cheap even with large rate cards
        data = self.env["media.rate.card.line"]._read_group(
            [("outlet_id", "in", self.ids)], ["outlet_id"], ["__count"]
        )
        counts = {outlet.id: count for outlet, count in data}
        for rec in self:
            rec.rate_line_count = counts.get(rec.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        outlets = super().create(vals_list)
        outlets._ensure_vendor_flag()
        return outlets

    def write(self, vals):
        res = super().write(vals)
        if "vendor_id" in vals:
            self._ensure_vendor_flag()
        return res

    def _ensure_vendor_flag(self):
        """A partner used as a media outlet's vendor is, by definition, a
        media vendor. Set the flag on create/write (not onchange, which would
        persist even if the user discards the form)."""
        vendors = self.mapped("vendor_id").filtered(
            lambda p: not p.is_media_vendor)
        if vendors:
            vendors.is_media_vendor = True
