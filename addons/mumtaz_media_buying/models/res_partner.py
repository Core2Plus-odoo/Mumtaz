# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_media_vendor = fields.Boolean(
        string="Media Vendor",
        help="This partner sells media inventory (a broadcaster, publisher, "
             "digital platform or outdoor-site owner).",
    )
    media_outlet_ids = fields.One2many(
        "media.outlet", "vendor_id", string="Media Outlets"
    )
