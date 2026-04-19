from odoo import api, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    marketplace_listing_ids = fields.One2many(
        "mumtaz.marketplace.listing",
        "product_tmpl_id",
        string="Marketplace Listings",
    )
    marketplace_listing_count = fields.Integer(
        compute="_compute_marketplace_listing_count",
        string="Listings",
    )
    marketplace_published = fields.Boolean(
        compute="_compute_marketplace_published",
        string="On Marketplace",
        store=False,
    )

    def _compute_marketplace_listing_count(self):
        for tmpl in self:
            tmpl.marketplace_listing_count = len(tmpl.marketplace_listing_ids)

    def _compute_marketplace_published(self):
        for tmpl in self:
            tmpl.marketplace_published = any(
                l.state == "published" for l in tmpl.marketplace_listing_ids
            )

    # ── Smart button ──────────────────────────────────────────────────
    def action_view_marketplace_listings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Marketplace Listings",
            "res_model": "mumtaz.marketplace.listing",
            "view_mode": "list,form",
            "domain": [("product_tmpl_id", "=", self.id)],
            "context": {
                "default_product_tmpl_id": self.id,
                "default_name": self.name,
                "default_listing_type": "product",
                "default_short_description": self.description_sale or self.name,
                "default_price": self.list_price,
                "default_price_type": "fixed",
            },
        }

    # ── One-click publish ─────────────────────────────────────────────
    def action_publish_to_marketplace(self):
        self.ensure_one()

        # If already linked, open existing listing
        published = self.marketplace_listing_ids.filtered(lambda l: l.state == "published")
        if published:
            return {
                "type": "ir.actions.act_window",
                "name": "Marketplace Listing",
                "res_model": "mumtaz.marketplace.listing",
                "res_id": published[0].id,
                "view_mode": "form",
            }

        # Find best-matching marketplace category from product category
        categ = self.env["mumtaz.marketplace.category"].search(
            [("name", "ilike", self.categ_id.name.split("/")[-1].strip())] if self.categ_id else [],
            limit=1,
        )
        if not categ:
            categ = self.env["mumtaz.marketplace.category"].search([], limit=1)
        if not categ:
            raise UserError(
                "No marketplace categories exist yet. "
                "Please create one under Marketplace → Configuration → Categories."
            )

        listing = self.env["mumtaz.marketplace.listing"].create({
            "name": self.name,
            "product_tmpl_id": self.id,
            "category_id": categ.id,
            "listing_type": "product",
            "short_description": (self.description_sale or self.name or "")[:200],
            "description": f"<p>{self.description_sale or self.name}</p>",
            "price": self.list_price,
            "price_type": "fixed" if self.list_price else "negotiable",
            "min_order_qty": 1.0,
            "lead_time_days": 7,
            "contact_email": self.env.company.email or "",
            "contact_phone": self.env.company.phone or "",
        })

        return {
            "type": "ir.actions.act_window",
            "name": "New Marketplace Listing",
            "res_model": "mumtaz.marketplace.listing",
            "res_id": listing.id,
            "view_mode": "form",
        }
