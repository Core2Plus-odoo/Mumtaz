"""Publishes the DEMO products and points the website at the demo home page. Idempotent."""
from odoo import SUPERUSER_ID, api, models
from odoo.addons.pharma_demo_data.models import demo_images

CATEGORIES = {  # public shop category -> SKUs
    "Infusions": ["DEMO-SKU-A", "DEMO-SKU-C", "DEMO-SKU-D"],
    "Blends & Mixes": ["DEMO-SKU-B", "DEMO-SKU-E"],
}
LEGACY_CATEGORIES = {"DEMO Wellness": "Infusions", "DEMO Nutrition": "Blends & Mixes"}   # first build


class PharmaWebsiteDemoSeed(models.AbstractModel):
    _name = "pharma.website.demo.seed"
    _description = "Pharma DEMO website seeder (fictional, idempotent)"

    @api.model
    def seed(self):
        env = api.Environment(self.env.cr, SUPERUSER_ID, {})
        Cat, Prod = env["product.public.category"], env["product.template"]
        for old, new in LEGACY_CATEGORIES.items():
            legacy = Cat.search([("name", "=", old)], limit=1)
            if legacy and not Cat.search_count([("name", "=", new)]):
                legacy.write({"name": new})
            elif legacy:
                legacy.unlink()
        for cat_name, skus in CATEGORIES.items():
            cat = Cat.search([("name", "=", cat_name)], limit=1) or Cat.create({"name": cat_name})
            for sku in skus:
                p = Prod.search([("default_code", "=", sku)], limit=1)
                if not p:
                    continue
                seq = 10 * (ord(sku[-1]) - 64)          # A=10 .. E=50, so the shop lists A..E
                vals = {}
                if not p.is_published:
                    vals["is_published"] = True
                if p.public_categ_ids != cat:
                    vals["public_categ_ids"] = [(6, 0, cat.ids)]
                if p.website_sequence != seq:
                    vals["website_sequence"] = seq
                if vals:
                    p.write(vals)
        P = env["ir.config_parameter"]
        logo = False
        if P.get_param("pharma.demo.logo_version") != demo_images.VERSION:
            logo = demo_images.logo_b64()
        for site in env["website"].search([]):
            vals = {}
            if logo:
                vals["logo"] = logo
            if site.name != "Pharma Demo Co (DEMO)":
                vals["name"] = "Pharma Demo Co (DEMO)"
            if site.homepage_url != "/pharma":
                vals["homepage_url"] = "/pharma"
            if vals:
                site.write(vals)
        if logo:
            P.set_param("pharma.demo.logo_version", demo_images.VERSION)
        return True
