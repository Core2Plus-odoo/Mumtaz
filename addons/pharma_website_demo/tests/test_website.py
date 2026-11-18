from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "pharma")
class TestPharmaWebsiteDemo(HttpCase):
    """The public demo storefront, fetched over HTTP exactly as a visitor would. This is the only place the
    QWeb home page is actually rendered before it reaches staging."""

    NAMES = ("Green Leaf Infusion", "Golden Chai Blend", "Rose Petal Tea", "Lavender Evening Infusion", "Warm Spice Mix")

    def test_home_page_renders_with_ribbon_and_products(self):
        res = self.url_open("/pharma")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Everyday wellness", html)
        self.assertIn("DEMO ENVIRONMENT", html)                       # ribbon, injected into website.layout
        self.assertIn("A demonstration, clearly marked", html)
        for name in self.NAMES:
            self.assertIn(name, html, name)                           # featured products come from the database
        self.assertNotIn("Traceback", html)

    def test_home_page_makes_no_health_claims(self):
        html = self.url_open("/pharma").text.lower()
        for word in ("cure", "treat ", "heals", "prevents", "clinically proven", "detox"):
            self.assertNotIn(word, html, word)
        self.assertIn("no product makes any health claim", html)

    def test_shop_lists_products_and_ribbon(self):
        res = self.url_open("/shop")
        self.assertEqual(res.status_code, 200)
        for name in self.NAMES:
            self.assertIn(name, res.text, name)
        self.assertIn("DEMO ENVIRONMENT", res.text)

    def test_product_page_opens(self):
        prod = self.env["product.template"].search([("default_code", "=", "DEMO-SKU-A")], limit=1)
        res = self.url_open(f"/shop/{prod.id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Green Leaf Infusion", res.text)

    def test_stylesheet_is_in_the_frontend_bundle(self):
        """Find the frontend CSS bundle the page really links, fetch it, and look for the wellness variables."""
        import re
        html = self.url_open("/pharma").text
        urls = re.findall(r'href="(/web/assets/[^"]*web\.assets_frontend[^"]*\.css)"', html)
        self.assertTrue(urls, "no web.assets_frontend CSS link in the rendered page")
        css = "".join(self.url_open(u).text for u in urls)
        self.assertIn("--pw-forest", css)
        self.assertIn("o_pharma_demo_ribbon", css)

    def test_seeded_state(self):
        env = self.env
        site = env["website"].search([], limit=1)
        self.assertEqual(site.homepage_url, "/pharma")
        self.assertEqual(site.name, "Pharma Demo Co (DEMO)")
        self.assertTrue(site.logo)
        prods = env["product.template"].search([("default_code", "=like", "DEMO-SKU-%")])
        self.assertEqual(len(prods), 5)
        self.assertTrue(all(p.is_published for p in prods))
        cats = {c.name for c in prods.mapped("public_categ_ids")}
        self.assertEqual(cats, {"Infusions", "Blends & Mixes"})
        self.assertEqual(env["product.public.category"].search_count([("name", "like", "DEMO %")]), 0)

    def test_website_seed_is_idempotent(self):
        env = self.env
        env["pharma.website.demo.seed"].seed()
        snap = {"cats": env["product.public.category"].search_count([]),
                "pub": env["product.template"].search_count([("is_published", "=", True)]),
                "sites": env["website"].search_count([])}
        env["pharma.website.demo.seed"].seed()
        self.assertEqual({"cats": env["product.public.category"].search_count([]),
                          "pub": env["product.template"].search_count([("is_published", "=", True)]),
                          "sites": env["website"].search_count([])}, snap)
