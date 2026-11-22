from odoo.tests.common import HttpCase, tagged

# Claims nobody has approved. If one of these reappears on a public page the
# build must fail, not rely on someone noticing.
FORBIDDEN = (
    "families cared for", "cities on the ground", "tasks photographed",
    "following our story", "first three care activities", "first three activities",
    "Three free activities", "are on us",
)


@tagged("post_install", "-at_install", "faizy")
class TestHome20(HttpCase):
    """The public pages carry the FAIZY 2.0 look and none of the unapproved claims."""

    def test_home_new_hero_and_no_unapproved_claims(self):
        page = self.url_open("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("fz2-hero", page.text)
        self.assertIn("/faizy_website/static/src/img/agent-hero.jpg", page.text)
        self.assertIn("illustrative character", page.text)
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, page.text, "unapproved claim on /: %s" % phrase)

    def test_other_public_pages_have_no_unapproved_claims(self):
        for path in ("/pricing", "/start", "/join", "/privacy", "/ai-team"):
            page = self.url_open(path)
            self.assertEqual(page.status_code, 200, path)
            for phrase in FORBIDDEN:
                self.assertNotIn(phrase, page.text, "%s on %s" % (phrase, path))

    def test_hero_image_is_served(self):
        img = self.url_open("/faizy_website/static/src/img/agent-hero.jpg")
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img.headers.get("Content-Type"), "image/jpeg")
