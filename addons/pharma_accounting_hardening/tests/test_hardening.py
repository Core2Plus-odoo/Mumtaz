import json
import xml.etree.ElementTree as ET
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged
from odoo.tools import file_open

PASSWORD = "Hardening-test-only-1!"


@tagged("post_install", "-at_install", "pharma")
class TestPharmaAccountingHardening(HttpCase):
    """The accounting kit is third-party code. These tests pin the two controls added around it and prove the
    tax gate still fires with the kit installed (the kit overrides account.move.action_post)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        g = lambda x: cls.env.ref(x).id
        cls.accountant = Users.create({"name": "Hardening Accountant", "login": "hardening_accountant",
                                       "password": PASSWORD, "group_ids": [(6, 0, [g("base.group_user"), g("account.group_account_user")])]})
        cls.plain = Users.create({"name": "Hardening Plain Internal", "login": "hardening_plain",
                                  "password": PASSWORD, "group_ids": [(6, 0, [g("base.group_user")])]})
        cls.portal = Users.create({"name": "Hardening Portal", "login": "hardening_portal",
                                   "password": PASSWORD, "group_ids": [(6, 0, [g("base.group_portal")])]})

    def _post_export(self, login, model, name="x"):
        self.authenticate(login, PASSWORD)
        return self.url_open("/xlsx_report", data={"model": model, "options": json.dumps({}),
                                                   "output_format": "xlsx", "report_name": name})

    # ---- export route -----------------------------------------------------------------------------
    def test_export_refused_for_users_without_an_accounting_role(self):
        for login in ("hardening_plain", "hardening_portal"):
            res = self._post_export(login, "res.partner")
            self.assertEqual(res.status_code, 403, login)

    def test_export_refused_for_a_model_that_is_not_an_exporter(self):
        for model in ("res.users", "ir.config_parameter", "no.such.model"):
            res = self._post_export("hardening_accountant", model)
            self.assertEqual(res.status_code, 403, model)

    def test_export_reaches_the_kit_for_an_accountant(self):
        # Empty options make the kit's own code fail, which it reports in a 200 body. The point here is only that
        # the guard let an accountant through to a real exporter, so the answer is not 403.
        res = self._post_export("hardening_accountant", "res.partner")
        self.assertEqual(res.status_code, 200)

    # ---- vendor support form ----------------------------------------------------------------------
    def test_support_form_is_admin_only(self):
        Form = self.env["client.support"]
        for user in (self.plain, self.accountant):
            with self.assertRaises(AccessError):
                Form.with_user(user).check_access("create")
        Form.with_user(self.env.ref("base.user_admin")).check_access("create")     # administrators still can

    def test_support_endpoint_points_nowhere(self):
        endpoint = self.env["client.support"]._get_support_endpoint()
        self.assertNotIn("cybrosys", endpoint)
        self.assertTrue(endpoint.startswith("http://127.0.0.1:"), endpoint)

    def test_endpoint_is_enforced_on_every_upgrade(self):
        """The data file must not be noupdate, or a later upgrade would leave a manually restored vendor URL alone.
        Checked on the parsed structure, not on the text, because the file's own comment mentions the word."""
        with file_open("pharma_accounting_hardening/data/support_endpoint.xml", "rb") as f:
            root = ET.parse(f).getroot()
        for el in root.iter():
            self.assertNotEqual(el.get("noupdate"), "1", f"<{el.tag}> is noupdate")
        calls = root.findall(".//function[@name='set_param']")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].get("model"), "ir.config_parameter")

    # ---- tax gate with the kit installed ----------------------------------------------------------
    def _draft_invoice(self, sku):
        prod = self.env["product.product"].search([("default_code", "=", sku)], limit=1)
        self.assertTrue(prod, sku)
        self.assertTrue(self.env["account.journal"].search_count([("type", "=", "sale")]), "no sales journal")
        partner = self.env["res.partner"].create({"name": "Hardening customer"})
        return self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": partner.id, "invoice_date": date(2026, 11, 6),
            "invoice_line_ids": [(0, 0, {"product_id": prod.id, "quantity": 1, "price_unit": prod.list_price})]})

    def test_tax_gate_still_blocks_an_unclassified_product_with_the_kit_installed(self):
        inv = self._draft_invoice("DEMO-SKU-C")          # no approved tax classification
        with self.assertRaises(UserError):
            inv.action_post()                            # the kit overrides action_post; the gate lives in _post
        self.assertEqual(inv.state, "draft")

    def test_an_approved_product_still_posts_with_the_kit_installed(self):
        inv = self._draft_invoice("DEMO-SKU-A")
        inv.action_post()
        self.assertEqual(inv.state, "posted")

    # ---- vendor support button --------------------------------------------------------------------
    def test_vendor_support_button_is_removed_from_the_web_client(self):
        """The headset icon and the user-menu item are taken out of the JS registries by an asset of this module.
        Pinned on the manifest and the file, because the registries only exist in a browser."""
        from odoo.modules.module import get_manifest
        path = "pharma_accounting_hardening/static/src/js/remove_vendor_support_ui.js"
        self.assertIn(path, get_manifest("pharma_accounting_hardening")["assets"]["web.assets_backend"])
        with file_open(path, "r") as f:
            js = f.read()
        self.assertIn("cybrosys_support_client.ClientSupportSystray", js)
        self.assertIn('"cybrosys_support"', js)
        self.assertIn("cat.remove(key)", js)
