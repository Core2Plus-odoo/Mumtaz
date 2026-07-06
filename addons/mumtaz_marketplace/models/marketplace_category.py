from odoo import fields, models


class MumtazMarketplaceCategory(models.Model):
    _name = "mumtaz.marketplace.category"
    _description = "Mumtaz Marketplace Category"
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(help="FontAwesome icon class, e.g. fa-shopping-cart")
    description = fields.Text()
    listing_count = fields.Integer(compute="_compute_listing_count")
    active = fields.Boolean(default=True)

    def _compute_listing_count(self):
        for rec in self:
            rec.listing_count = self.env["mumtaz.marketplace.listing"].search_count(
                [("category_id", "=", rec.id), ("state", "=", "published")]
            )
