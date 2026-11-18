"""Publishes the DEMO products and points the website at the demo home page. Idempotent."""
from odoo import SUPERUSER_ID, api, models

CATEGORIES = {  # public shop category -> SKUs
    "DEMO Wellness": ["DEMO-SKU-A", "DEMO-SKU-B", "DEMO-SKU-C"],
    "DEMO Nutrition": ["DEMO-SKU-D", "DEMO-SKU-E"],
}


class PharmaWebsiteDemoSeed(models.AbstractModel):
    _name = "pharma.website.demo.seed"
    _description = "Pharma DEMO website seeder (fictional, idempotent)"

    @api.model
    def seed(self):
        env = api.Environment(self.env.cr, SUPERUSER_ID, {})
        Cat, Prod = env["product.public.category"], env["product.template"]
        seq = 10
        for cat_name, skus in CATEGORIES.items():
            cat = Cat.search([("name", "=", cat_name)], limit=1) or Cat.create({"name": cat_name})
            for sku in skus:
                p = Prod.search([("default_code", "=", sku)], limit=1)
                if not p:
                    continue
                vals = {}
                if not p.is_published:
                    vals["is_published"] = True
                if cat not in p.public_categ_ids:
                    vals["public_categ_ids"] = [(4, cat.id)]
                if p.website_sequence != seq:
                    vals["website_sequence"] = seq
                if vals:
                    p.write(vals)
                seq += 10
        for site in env["website"].search([]):
            vals = {}
            if site.name != "Pharma Demo Co (DEMO)":
                vals["name"] = "Pharma Demo Co (DEMO)"
            if site.homepage_url != "/pharma":
                vals["homepage_url"] = "/pharma"
            if vals:
                site.write(vals)
        return True
