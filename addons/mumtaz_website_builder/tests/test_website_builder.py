"""The Mumtaz homepage module at its boundaries: what installs, what renders,
what the editor offers, what the form writes, and that the stylesheet bundle
survives our CSS (a Google Fonts URL with ';' once truncated the whole
frontend bundle)."""
import json
import re

from odoo.tests import HttpCase, tagged

from odoo.addons.http_routing.tests.common import MockRequest

URL = '/mumtaz-native-preview'
SNIPPETS = ['s_mumtaz_hero', 's_mumtaz_paths', 's_mumtaz_platform', 's_mumtaz_editions',
            's_mumtaz_ai', 's_mumtaz_partners', 's_mumtaz_contact']


@tagged('post_install', '-at_install')
class TestMumtazWebsiteBuilder(HttpCase):

    def test_install_adds_an_unpublished_page_and_nothing_else(self):
        page = self.env.ref('mumtaz_website_builder.page_mumtaz_preview')
        self.assertFalse(page.is_published)
        self.assertEqual(page.url, URL)
        website = self.env['website'].get_current_website()
        self.assertNotEqual(website.homepage_url or '/', URL)
        self.assertFalse(self.env['website.menu'].search([('url', '=', URL)]))
        r = self.url_open(URL)
        self.assertEqual(r.status_code, 404, 'an unpublished page must stay invisible to visitors')

    def test_admin_sees_seven_editable_sections_with_the_site_scope(self):
        self.authenticate('admin', 'admin')
        r = self.url_open(URL)
        self.assertEqual(r.status_code, 200)
        html = r.text
        for key in SNIPPETS:
            self.assertIn('data-snippet="%s"' % key, html)
        self.assertIn('id="wrap" class="oe_structure o_mumtaz_site"', html)
        self.assertIn('Run the business.', html)
        self.assertIn('action="/website/form/"', html)
        for name in ('contact_name', 'email_from', 'partner_name', 'phone', 'Interested solution', 'Privacy consent'):
            self.assertIn('name="%s"' % name, html)

    def test_page_wrap_is_literal_markup_so_the_builder_can_brand_it(self):
        # A QWeb directive inside #wrap stops Odoo from branding the wrap as one editable
        # structure; the editor then greys out every block group ("cannot be dropped").
        from lxml import etree
        view = self.env.ref('mumtaz_website_builder.page_mumtaz_preview').view_id
        root = etree.fromstring(view.arch_db.encode())
        wrap = root.xpath("//*[@id='wrap']")[0]
        dynamic = [el.tag for el in wrap.iter()
                   if (isinstance(el.tag, str) and el.tag == 't') or any(k.startswith('t-') for k in el.attrib)]
        self.assertFalse(dynamic, dynamic)

    def test_blocks_are_registered_in_the_builder_library(self):
        snippets = self.env['ir.ui.view'].sudo().search([('key', '=', 'mumtaz_website_builder.mumtaz_snippets')])
        self.assertTrue(snippets and snippets.active)
        arch = snippets.arch_db
        self.assertIn('snippet-group="mumtaz"', arch)
        website = self.env['website'].get_current_website()
        for key in SNIPPETS:
            self.assertIn('t-snippet="mumtaz_website_builder.%s"' % key, arch)
            with MockRequest(self.env, website=website):
                rendered = str(self.env['ir.qweb']._render('mumtaz_website_builder.%s' % key))
            self.assertIn('data-snippet="%s"' % key, rendered)
            self.assertIn('o_mumtaz_site', rendered)

    def test_frontend_stylesheet_bundle_is_intact(self):
        self.authenticate('admin', 'admin')
        html = self.url_open(URL).text
        m = re.search(r'(/web/assets/[^"]*web\.assets_frontend(?:\.min)?\.css)', html)
        self.assertTrue(m, 'frontend css bundle link not found')
        css = self.url_open(m.group(1)).text
        self.assertNotIn("css2?family", css, 'a css2 Google Fonts import is split by the bundler at its first ;')
        self.assertIn('.o_mumtaz_site .mumtaz_button', css, 'our scoped rules must be in the bundle')
        # the bundle still ends with Odoo's own rules: nothing after our import was swallowed
        self.assertIn('.o_footer', css)

    def _post(self, **extra):
        data = {'contact_name': 'Hind Al Mansoori', 'email_from': 'hind@example.test', 'partner_name': 'Dar Al Noor Jewellers',
                'phone': '+971 50 000 9100', 'Interested solution': 'Industry solution',
                'description': 'Three boutiques, one warehouse.', 'Privacy consent': 'Yes',
                'name': 'Mumtaz Digital — Website demo request'}
        data.update(extra)
        for k in [k for k, v in data.items() if v is None]:
            del data[k]
        return self.url_open('/website/form/crm.lead', data=data)

    def test_form_creates_a_tagged_lead_with_consent_recorded(self):
        before = self.env['crm.lead'].search([], order='id desc', limit=1).id or 0
        r = self._post()
        self.assertEqual(r.status_code, 200)
        out = json.loads(r.text)
        self.assertIn('id', out, out)
        lead = self.env['crm.lead'].browse(out['id'])
        self.assertGreater(lead.id, before)
        self.assertEqual(lead.contact_name, 'Hind Al Mansoori')
        self.assertEqual(lead.email_from, 'hind@example.test')
        self.assertEqual(lead.partner_name, 'Dar Al Noor Jewellers')
        self.assertIn('9100', lead.phone)
        self.assertIn(self.env.ref('mumtaz_website_builder.tag_industry'), lead.tag_ids)
        self.assertIn('Three boutiques', lead.description)
        self.assertIn('Privacy consent', lead.description)
        self.assertIn('Interested solution : Industry solution', lead.description)
        self.assertIn('Yes', lead.description)
        self.assertEqual(lead.name, 'Mumtaz Digital — Website demo request')

    def test_server_refuses_incomplete_or_robotic_posts(self):
        count = self.env['crm.lead'].search_count([])
        for bad in ({'contact_name': None, 'email_from': None}, {'email_from': 'nope'}, {'Privacy consent': None},
                    {'Interested solution': None}, {'Interested solution': 'Something else'}, {'partner_name': None}, {'phone': '12'}, {'website_url_hp': 'http://spam.example'}):
            out = json.loads(self._post(**bad).text)
            self.assertNotIn('id', out, bad)
            self.assertTrue(out.get('error'), bad)
        self.assertEqual(self.env['crm.lead'].search_count([]), count)
        # the same checks do not touch other website forms on the database
        r = self.url_open('/website/form/crm.lead', data={'name': 'Another form', 'contact_name': 'x'})
        self.assertIn('id', json.loads(r.text))
