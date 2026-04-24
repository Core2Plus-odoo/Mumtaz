from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    marketplace_demand_count = fields.Integer(
        compute="_compute_marketplace_demand_count",
        string="Market Demand Signals",
    )

    def _compute_marketplace_demand_count(self):
        Inquiry = self.env["mumtaz.marketplace.inquiry"].sudo()
        for order in self:
            order.marketplace_demand_count = Inquiry.search_count(
                order._market_demand_domain()
            )

    def _market_demand_domain(self):
        product_ids = self.order_line.mapped("product_id.product_tmpl_id").ids
        categ_ids = self.order_line.mapped("product_id.categ_id").ids

        listing_domain = [("state", "=", "published")]
        if product_ids:
            mkt_categ_ids = self._so_matching_categ_ids(categ_ids)
            listing_domain += [
                "|",
                ("product_tmpl_id", "in", product_ids),
                ("category_id", "in", mkt_categ_ids),
            ]

        matching_listings = self.env["mumtaz.marketplace.listing"].sudo().search(listing_domain)
        return [
            ("listing_id", "in", matching_listings.ids),
            ("state", "in", ["new", "in_progress"]),
        ]

    def _so_matching_categ_ids(self, product_categ_ids):
        product_categs = self.env["product.category"].browse(product_categ_ids)
        keywords = [c.name.split("/")[-1].strip() for c in product_categs]
        mkt_categs = self.env["mumtaz.marketplace.category"].search([
            ("name", "in", keywords),
        ])
        return mkt_categs.ids

    def action_view_market_demand(self):
        self.ensure_one()
        domain = self._market_demand_domain()
        return {
            "type": "ir.actions.act_window",
            "name": "Market Demand Signals",
            "res_model": "mumtaz.marketplace.inquiry",
            "view_mode": "list,form",
            "domain": domain,
            "context": {},
        }
