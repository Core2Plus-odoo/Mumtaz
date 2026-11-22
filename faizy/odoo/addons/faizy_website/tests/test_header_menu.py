from lxml import html

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.faizy_website.menu_setup import _find, fix_header_menu


@tagged("post_install", "-at_install", "faizy_website")
class TestHeaderMenu(HttpCase):
    """The About Us dropdown must hold its three pages, and the button comes last."""

    def setUp(self):
        super().setUp()
        self.website = self.env["website"].search([], limit=1)
        self.top = self.website.menu_id
        self.about = _find(self.env, self.website, "#", parent=self.top, name="About Us")

    def test_detached_entry_is_moved_under_the_websites_about_us(self):
        self.assertTrue(self.about, "the website has its own About Us group")
        generic_about = self.env.ref("faizy_website.menu_faizy_about")
        self.assertFalse(generic_about.website_id)
        entry = _find(self.env, self.website, "/ai-team")
        entry.parent_id = generic_about  # how Odoo leaves it after copying the menu to the website
        fix_header_menu(self.env)
        self.assertEqual(entry.parent_id, self.about)
        self.assertEqual(set(self.about.child_id.mapped("url")), {"/join", "/ai-team", "/privacy"})

    def test_entry_placed_elsewhere_by_marketing_is_left_alone(self):
        entry = _find(self.env, self.website, "/ai-team")
        entry.parent_id = self.top
        fix_header_menu(self.env)
        self.assertEqual(entry.parent_id, self.top)

    def test_blog_does_not_tie_with_the_button(self):
        start = _find(self.env, self.website, "/start", parent=self.top)
        blog = _find(self.env, self.website, "/blog", parent=self.top)
        if not blog:
            blog = self.env["website.menu"].create(
                {"name": "Blog", "url": "/blog", "parent_id": self.top.id, "website_id": self.website.id}
            )
        blog.sequence = start.sequence
        fix_header_menu(self.env)
        self.assertLess(blog.sequence, start.sequence)

    def test_header_shows_the_dropdown_pages(self):
        fix_header_menu(self.env)
        page = html.fromstring(self.url_open("/").content)
        for url in ("/join", "/ai-team", "/privacy"):
            self.assertTrue(page.xpath("//header//a[@href='%s']" % url), url)
