from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "pharma")
class TestPharmaDemoSeed(TransactionCase):
    """The seeder ran once at install (post_init_hook). These tests prove every demo scenario exists
    and that running the seeder again changes nothing."""

    def _counts(self):
        env = self.env
        return {m: env[m].sudo().search_count([]) for m in (
            "pharma.tax.rule", "pharma.tax.event", "pharma.raw.event", "pharma.recon.run", "pharma.recon.item",
            "pharma.recon.exception", "pharma.partner.stock.line", "pharma.partner.scenario", "sale.order",
            "account.move")} | {"users": env["res.users"].sudo().search_count([("login", "like", "pharma.%")])}

    def test_seed_is_idempotent(self):
        self.env["pharma.demo.seed"].seed()      # bring the DB to the seeded steady state first
        before = self._counts()
        self.env["pharma.demo.seed"].seed()
        self.assertEqual(self._counts(), before)

    def test_products_are_shop_ready(self):
        Prod = self.env["product.template"].sudo()
        names = {p.default_code: p.name for p in Prod.search([("default_code", "=like", "DEMO-SKU-%")])}
        self.assertEqual(names, {
            "DEMO-SKU-A": "Green Leaf Infusion (DEMO)", "DEMO-SKU-B": "Golden Chai Blend (DEMO)",
            "DEMO-SKU-C": "Rose Petal Tea (DEMO)", "DEMO-SKU-D": "Lavender Evening Infusion (DEMO)",
            "DEMO-SKU-E": "Warm Spice Mix (DEMO)"})
        for p in Prod.search([("default_code", "=like", "DEMO-SKU-%")]):
            self.assertTrue(p.image_1920, p.name)
            self.assertIn("No health claims", p.description_sale)
            self.assertIn("DEMO scenario", p.description or "")        # the control it demonstrates, internal only
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_param("pharma.demo.image_version"), "2")

    def test_mode_and_company(self):
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_param("pharma.mode"), "demo")
        self.assertEqual(self.env.company.name, "Pharma Demo Co")

    def test_demo_users_one_per_role(self):
        U = self.env["res.users"].sudo()
        for login, group in (("pharma.ops", "group_pharma_user"), ("pharma.maker", "group_pharma_admin"),
                             ("pharma.approver", "group_pharma_tax_approver"), ("pharma.finance", "group_pharma_finance")):
            u = U.search([("login", "=", login)])
            self.assertEqual(len(u), 1, login)
            self.assertTrue(U.with_user(u).env.user.has_group(f"pharma_core.{group}"), login)
        ops = U.search([("login", "=", "pharma.ops")])
        self.assertFalse(U.with_user(ops).env.user.has_group("pharma_core.group_pharma_finance"))

    def test_tax_rule_scenarios(self):
        Rule = self.env["pharma.tax.rule"].sudo()
        by = {r.name: r for r in Rule.search([("name", "like", "DEMO-RULE-")])}
        self.assertEqual(by["DEMO-RULE-3"].state, "draft")
        self.assertEqual(by["DEMO-RULE-7"].state, "superseded")
        self.assertTrue(all(by[n].state == "approved" for n in ("DEMO-RULE-0", "DEMO-RULE-1", "DEMO-RULE-2", "DEMO-RULE-5", "DEMO-RULE-6")))
        self.assertTrue(all(r.is_demo for r in by.values()))
        # effective dating: a 2025 date uses the 8% rule, 2026 uses 10%
        A = self.env["product.product"].search([("default_code", "=", "DEMO-SKU-A")], limit=1)
        self.assertEqual(Rule.resolve(A, date(2025, 6, 1), 1000)["amount"], 80.0)
        self.assertEqual(Rule.resolve(A, date(2026, 6, 1), 1000)["amount"], 100.0)
        # ambiguity: two approved rules overlap for DEMO_CLASS_Y
        D = self.env["product.product"].search([("default_code", "=", "DEMO-SKU-D")], limit=1)
        res = Rule.resolve(D, date(2026, 6, 1), 1000)
        self.assertEqual(res["resolution"], "blocked")
        self.assertIn("ambiguous", res["reason"])
        # pending classification blocks
        C = self.env["product.product"].search([("default_code", "=", "DEMO-SKU-C")], limit=1)
        self.assertEqual(Rule.resolve(C, date(2026, 6, 1), 1000)["resolution"], "blocked")

    def test_maker_checker_on_demo_rule(self):
        Rule = self.env["pharma.tax.rule"].sudo()
        maker = self.env["res.users"].sudo().search([("login", "=", "pharma.maker")])
        approver = self.env["res.users"].sudo().search([("login", "=", "pharma.approver")])
        r3 = Rule.search([("name", "=", "DEMO-RULE-3")])
        with self.assertRaises(UserError):
            r3.with_user(maker).action_approve()          # maker is not an approver
        r4 = Rule.search([("name", "=", "DEMO-RULE-4")])
        with self.assertRaises(UserError):
            r4.with_user(approver).action_approve()       # evidence missing
        r3.with_user(approver).action_approve()
        self.assertEqual(r3.state, "approved")

    def test_classification_proposed_awaits_approver(self):
        E = self.env["product.template"].sudo().search([("default_code", "=", "DEMO-SKU-E")], limit=1)
        self.assertEqual(E.pharma_tax_status, "pending_evidence")
        self.assertEqual(E.pharma_tax_proposed_by.login, "pharma.maker")
        approver = self.env["res.users"].sudo().search([("login", "=", "pharma.approver")])
        E.with_user(approver).action_pharma_approve_tax_class()
        self.assertEqual(E.pharma_tax_status, "approved")

    def test_events_include_a_reversal(self):
        Ev = self.env["pharma.tax.event"].sudo()
        rev = Ev.search([("order_ref", "=", "DEMO-O-1004"), ("kind", "=", "reversal")])
        self.assertEqual(len(rev), 1)
        self.assertEqual(rev.amount, -rev.reversal_of.amount)

    def test_raw_event_duplicate_and_conflict(self):
        Raw = self.env["pharma.raw.event"].sudo()
        self.assertEqual(Raw.search_count([("event_id", "=", "DEMO-O-1007")]), 1)
        self.assertEqual(Raw.search([("event_id", "=", "DEMO-O-1008")]).state, "conflict")

    def test_recon_runs_cover_every_outcome(self):
        Run = self.env["pharma.recon.run"].sudo()
        runs = {r.name: r for r in Run.search([("is_demo", "=", True)])}
        clean = runs["DEMO R03 COD batch DEMO-COD-BATCH-2 (DEMO Courier A) — clean"]
        self.assertEqual((clean.state, clean.open_exceptions), ("matched", 0))
        variance = runs["DEMO R03 COD batch DEMO-COD-BATCH-1 (DEMO Courier A)"]
        self.assertEqual(variance.state, "partial")
        self.assertEqual(variance.variance, -2000.0)   # 106,000 gross - 5,000 fees = 101,000 expected vs 99,000 received
        gw = runs["DEMO R04 gateway payout DEMO-PAYOUT-7 (DEMO Gateway)"]
        self.assertTrue(any("Unidentified" in e.description for e in gw.exception_ids))
        bank = runs["DEMO R05 Bank vs ledger Nov"]
        methods = set(bank.item_ids.mapped("method"))
        self.assertIn("exact_ref", methods)
        self.assertIn("amount_date_LOW_CONFIDENCE", methods)
        descs = " | ".join(bank.exception_ids.mapped("description"))
        self.assertIn("amount differs", descs)
        self.assertIn("Ambiguous", descs)

    def test_exceptions_in_every_state(self):
        Exc = self.env["pharma.recon.exception"].sudo()
        states = set(Exc.search([("is_demo", "=", True)]).mapped("state"))
        self.assertTrue({"open", "investigating", "pending_approval", "closed"} <= states, states)
        closed = Exc.search([("state", "=", "closed"), ("is_demo", "=", True)], limit=1)
        self.assertNotEqual(closed.proposed_by, closed.approved_by)
        pending = Exc.search([("state", "=", "pending_approval")], limit=1)
        with self.assertRaises(UserError):
            pending.with_user(pending.proposed_by).action_approve_close()   # maker-checker

    def test_partner_stock_and_scenario_gate(self):
        St = self.env["pharma.partner.stock.line"].sudo()
        self.assertTrue(St.search_count([("variance", "!=", 0)]) >= 2)
        self.assertTrue(St.search_count([("variance", "=", 0)]) >= 1)
        Sc = self.env["pharma.partner.scenario"].sudo()
        self.assertFalse(Sc.search([], limit=1).complete)
        res = Sc.custody_transfer("DEMO-SKU-A", "DEMO-LOT-01", 10)
        self.assertTrue(res["custody_move"])
        self.assertFalse(res["revenue_recognised"])
        self.assertIn("BLOCKED", res["status"])

    def test_sales_gate_on_demo_documents(self):
        SO = self.env["sale.order"].sudo()
        self.assertEqual(SO.search([("client_order_ref", "=", "DEMO-SO-OK")]).state, "sale")
        blocked = SO.search([("client_order_ref", "=", "DEMO-SO-BLOCKED")])
        self.assertEqual(blocked.state, "draft")
        with self.assertRaises(UserError):
            blocked.action_confirm()
        Move = self.env["account.move"].sudo()
        ok = Move.search([("ref", "=", "DEMO-INV-OK")])
        if ok:   # invoices exist whenever the DB has a sale journal
            self.assertEqual(ok.state, "posted")
            inv = Move.search([("ref", "=", "DEMO-INV-BLOCKED")])
            self.assertEqual(inv.state, "draft")
            with self.assertRaises(UserError):
                inv.action_post()
