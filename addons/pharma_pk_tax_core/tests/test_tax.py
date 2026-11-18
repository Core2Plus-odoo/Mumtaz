from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "pharma")
class TestPharmaTax(TransactionCase):
    """DEMO/fictional data only. Mirrors Blueprint s.23 UAT cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        g = lambda x: cls.env.ref("pharma_core." + x).id
        cls.maker = Users.create({"name": "Demo Maker", "login": "demo_maker",
                                  "group_ids": [(6, 0, [cls.env.ref("base.group_user").id, g("group_pharma_admin"), cls.env.ref("product.group_product_manager").id])]})
        cls.approver = Users.create({"name": "Demo Approver", "login": "demo_approver",
                                     "group_ids": [(6, 0, [cls.env.ref("base.group_user").id, g("group_pharma_tax_approver"), cls.env.ref("product.group_product_manager").id])]})
        cls.env["ir.config_parameter"].sudo().set_param("pharma.mode", "demo")
        cls.Rule = cls.env["pharma.tax.rule"]
        cls.rule = cls.Rule.with_user(cls.maker).create({
            "name": "DEMO-R1", "tax_type": "SALES_TAX_OUTPUT", "tax_class": "QA_TEST_CLASS_ONLY",
            "rate": 10, "date_from": date(2026, 1, 1), "legal_ref": "DEMO-REF",
            "evidence_ref": "DEMO-EVID", "is_demo": True})
        cls.pending = cls.env["product.product"].create({"name": "DEMO Pending SKU", "default_code": "DEMO-SKU-C"})
        cls.ok = cls.env["product.product"].create({"name": "DEMO Approved SKU",
                                                                          "default_code": "DEMO-SKU-A"})
        cls.ok.product_tmpl_id.with_user(cls.maker).write({
            "pharma_tax_class": "QA_TEST_CLASS_ONLY", "pharma_tax_evidence_ref": "DEMO-EVID"})

    def _approve_all(self):
        self.rule.with_user(self.approver).action_approve()
        self.ok.product_tmpl_id.with_user(self.approver).action_pharma_approve_tax_class()

    # --- classification and maker-checker
    def test_new_product_pending_nothing_assumed(self):
        self.assertEqual(self.pending.product_tmpl_id.pharma_tax_status, "pending_evidence")
        res = self.Rule.resolve(self.pending, date(2026, 11, 1), 1000)
        self.assertEqual(res["resolution"], "blocked")
        self.assertIsNone(res["amount"])

    def test_maker_cannot_approve_own_classification(self):
        with self.assertRaises(UserError):
            self.ok.product_tmpl_id.with_user(self.maker).action_pharma_approve_tax_class()

    def test_creator_cannot_approve_own_rule_even_if_approver_group(self):
        self.maker.write({"group_ids": [(4, self.env.ref("pharma_core.group_pharma_tax_approver").id)]})
        with self.assertRaises(UserError):
            self.rule.with_user(self.maker).action_approve()

    def test_rule_needs_evidence(self):
        r = self.Rule.with_user(self.maker).create({"name": "DEMO-R2", "tax_type": "SALES_TAX_OUTPUT",
            "tax_class": "Z", "rate": 1, "date_from": date(2026, 1, 1), "is_demo": True})
        with self.assertRaises(UserError):
            r.with_user(self.approver).action_approve()

    def test_changing_class_resets_approval(self):
        self._approve_all()
        t = self.ok.product_tmpl_id
        self.assertEqual(t.pharma_tax_status, "approved")
        t.with_user(self.maker).write({"pharma_tax_class": "OTHER"})
        self.assertEqual(t.pharma_tax_status, "pending_evidence")

    # --- engine
    def test_draft_rule_needs_approval(self):
        self.ok.product_tmpl_id.with_user(self.approver).action_pharma_approve_tax_class()
        res = self.Rule.resolve(self.ok, date(2026, 11, 1), 1000)
        self.assertEqual(res["resolution"], "needs_approval")

    def test_resolved_amount(self):
        self._approve_all()
        res = self.Rule.resolve(self.ok, date(2026, 11, 1), 1000)
        self.assertEqual((res["resolution"], res["amount"]), ("resolved", 100.0))

    def test_demo_rule_refused_in_production(self):
        self._approve_all()
        self.env["ir.config_parameter"].sudo().set_param("pharma.mode", "production")
        res = self.Rule.resolve(self.ok, date(2026, 11, 1), 1000)
        self.assertEqual(res["resolution"], "needs_approval")
        self.assertIn("DEMO-only", res["reason"])

    def test_effective_dating(self):
        self._approve_all()
        self.assertEqual(self.Rule.resolve(self.ok, date(2025, 12, 31), 100)["resolution"], "blocked")
        self.assertEqual(self.Rule.resolve(self.ok, date(2026, 1, 1), 100)["resolution"], "resolved")

    def test_overlap_is_ambiguous_blocked(self):
        self._approve_all()
        r2 = self.Rule.with_user(self.maker).create({"name": "DEMO-R3", "tax_type": "SALES_TAX_OUTPUT",
            "tax_class": "QA_TEST_CLASS_ONLY", "rate": 20, "date_from": date(2026, 1, 1), "legal_ref": "L",
            "evidence_ref": "E", "is_demo": True})
        r2.with_user(self.approver).action_approve()
        res = self.Rule.resolve(self.ok, date(2026, 11, 1), 100)
        self.assertEqual(res["resolution"], "blocked")
        self.assertIn("ambiguous", res["reason"])

    def test_approved_rule_immutable(self):
        self._approve_all()
        with self.assertRaises(UserError):
            self.rule.write({"rate": 99})
        self.rule.write({"date_to": date(2026, 12, 31)})   # end-dating is allowed

    # --- events
    def test_event_post_duplicate_and_reversal(self):
        self._approve_all()
        E = self.env["pharma.tax.event"]
        ev = E.post_event("DEMO-O-1", "shopify", "S1", "SALES_TAX_OUTPUT", self.ok, date(2026, 11, 1), 1000)
        self.assertEqual((ev.amount, ev.rule_code), (100.0, "DEMO-R1"))
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                E.post_event("DEMO-O-1", "shopify", "S1", "SALES_TAX_OUTPUT", self.ok, date(2026, 11, 1), 1000)
        ev.action_reverse()
        self.assertEqual(sum(E.search([("order_ref", "=", "DEMO-O-1")]).mapped("amount")), 0.0)
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                ev.action_reverse()

    def test_event_immutable(self):
        self._approve_all()
        ev = self.env["pharma.tax.event"].post_event("DEMO-O-2", "odoo_website", "S2", "SALES_TAX_OUTPUT",
                                                     self.ok, date(2026, 11, 1), 500)
        with self.assertRaises(UserError):
            ev.write({"amount": 1})
        with self.assertRaises(UserError):
            ev.unlink()

    def test_blocked_product_cannot_post_event(self):
        with self.assertRaises(UserError):
            self.env["pharma.tax.event"].post_event("DEMO-O-3", "shopify", "S3", "SALES_TAX_OUTPUT",
                                                    self.pending, date(2026, 11, 1), 100)

    # --- posting gate on real Odoo documents
    def _so(self, product):
        partner = self.env["res.partner"].create({"name": "DEMO Customer"})
        return self.env["sale.order"].create({"partner_id": partner.id, "order_line": [
            (0, 0, {"product_id": product.id, "product_uom_qty": 1, "price_unit": 1000})]})

    def test_sale_order_confirm_blocked_for_pending_sku(self):
        with self.assertRaises(UserError) as cm:
            self._so(self.pending).action_confirm()
        self.assertIn("DEMO Pending SKU", str(cm.exception))

    def test_sale_order_confirm_allowed_for_approved_sku(self):
        self._approve_all()
        so = self._so(self.ok)
        so.action_confirm()
        self.assertEqual(so.state, "sale")

    def test_customer_invoice_post_blocked_for_pending_sku(self):
        partner = self.env["res.partner"].create({"name": "DEMO Customer 2"})
        inv = self.env["account.move"].create({"move_type": "out_invoice", "partner_id": partner.id,
            "invoice_line_ids": [(0, 0, {"product_id": self.pending.id, "quantity": 1, "price_unit": 100})]})
        with self.assertRaises(UserError):
            inv.action_post()

    def test_gate_can_be_switched_off_by_policy(self):
        self.env["ir.config_parameter"].sudo().set_param("pharma.tax_gate", "off")
        so = self._so(self.pending)
        so.action_confirm()
        self.assertEqual(so.state, "sale")
