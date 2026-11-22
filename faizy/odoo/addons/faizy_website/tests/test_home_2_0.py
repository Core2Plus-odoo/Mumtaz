from odoo.tests.common import HttpCase, TransactionCase, tagged

# Claims nobody has approved. If one of these reappears on a public page the
# build must fail, not rely on someone noticing.
FORBIDDEN = (
    "families cared for", "cities on the ground", "tasks photographed",
    "following our story", "first three care activities", "first three activities",
    "Three free activities", "are on us", "Start free",
)


def run_menu_migration(env):
    """Run the 19.0.1.21.0 migration the way an upgrade would."""
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "migrations", "19.0.1.21.0", "post-menu-label.py")
    spec = importlib.util.spec_from_file_location("post_menu_label", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.migrate(env.cr, "19.0.1.20.0")


@tagged("post_install", "-at_install", "faizy")
class TestHome20(HttpCase):
    """The public pages carry the FAIZY 2.0 look and none of the unapproved claims."""

    def setUp(self):
        super().setUp()
        # A database upgraded from 19.0.1.20.0 still holds the old menu label.
        run_menu_migration(self.env)

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


@tagged("post_install", "-at_install", "faizy")
class TestStartMenuMigration(TransactionCase):
    """The upgrade renames a leftover "Start free" menu entry and respects other wording."""

    def _migrate(self):
        run_menu_migration(self.env)

    def test_old_label_is_renamed(self):
        menu = self.env.ref("faizy_website.menu_faizy_start")
        menu.name = "Start free"
        self._migrate()
        self.assertEqual(menu.name, "Get started")

    def test_marketing_wording_is_kept(self):
        menu = self.env.ref("faizy_website.menu_faizy_start")
        menu.name = "Join today"
        self._migrate()
        self.assertEqual(menu.name, "Join today")
