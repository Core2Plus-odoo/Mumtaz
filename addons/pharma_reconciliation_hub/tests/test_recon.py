from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "pharma")
class TestPharmaRecon(TransactionCase):
    """DEMO / fictional data only. Mirrors Blueprint s.12 and s.23."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        U = cls.env["res.users"].with_context(no_reset_password=True)
        base = cls.env.ref("base.group_user").id
        fin = cls.env.ref("pharma_core.group_pharma_finance").id
        cls.fin1 = U.create({"name": "Demo Fin 1", "login": "demo_fin1", "group_ids": [(6, 0, [base, fin])]})
        cls.fin2 = U.create({"name": "Demo Fin 2", "login": "demo_fin2", "group_ids": [(6, 0, [base, fin])]})
        cls.ops = U.create({"name": "Demo Ops", "login": "demo_ops",
                            "group_ids": [(6, 0, [base, cls.env.ref("pharma_core.group_pharma_user").id])]})

    def _run(self, typ="cod", ded=0.0, items=()):
        run = self.env["pharma.recon.run"].create({"name": "DEMO run", "run_type": typ,
                                                   "authorized_deductions": ded, "is_demo": True})
        for side, ref, batch, amt, d in items:
            self.env["pharma.recon.item"].create({"run_id": run.id, "side": side, "item_ref": ref,
                "batch_ref": batch, "amount": amt, "item_date": d})
        return run

    def _match(self, run):
        run.with_user(self.fin1).action_match()
        return run

    def test_blueprint_cod_example_is_exception_not_adjusted(self):
        # collected 100,000; authorized deductions 5,000; expected 95,000; actual 93,000
        run = self._run("cod", 5000, [
            ("source", "AWB1", "BATCH1", 60000, date(2026, 11, 3)),
            ("source", "AWB2", "BATCH1", 40000, date(2026, 11, 3)),
            ("bank", "BATCH1", "", 93000, date(2026, 11, 9))])
        self._match(run)
        self.assertEqual((run.expected_bank, run.bank_total, run.variance), (95000.0, 93000.0, -2000.0))
        self.assertTrue(run.exception_ids)
        self.assertTrue(all(e.state == "open" and not e.owner_id for e in run.exception_ids))
        self.assertEqual(run.state, "partial")

    def test_cod_exact_settlement_matches_cleanly(self):
        run = self._run("cod", 5000, [
            ("source", "AWB1", "BATCH1", 60000, date(2026, 11, 3)),
            ("source", "AWB2", "BATCH1", 40000, date(2026, 11, 3)),
            ("bank", "BATCH1", "", 95000, date(2026, 11, 9))])
        self._match(run)
        self.assertFalse(run.exception_ids)
        self.assertEqual(run.state, "matched")
        self.assertEqual(set(run.item_ids.mapped("method")) - {False}, {"one_to_many_batch"})

    def test_exact_reference(self):
        run = self._run("gateway", 0, [("source", "R1", "", 500, date(2026, 11, 1)),
                                        ("bank", "R1", "", 500, date(2026, 11, 2))])
        self._match(run)
        self.assertEqual(run.item_ids.mapped("method"), ["exact_ref", "exact_ref"])

    def test_amount_only_ambiguity_refused(self):
        run = self._run("bank", 0, [("source", "A", "", 500, date(2026, 11, 1)),
                                    ("source", "B", "", 500, date(2026, 11, 2)),
                                    ("bank", "", "", 500, date(2026, 11, 2))])
        self._match(run)
        self.assertFalse(run.item_ids.filtered(lambda i: i.state == "matched"))
        self.assertIn("Ambiguous", run.exception_ids.description)

    def test_unique_amount_date_flagged_low_confidence(self):
        run = self._run("bank", 0, [("source", "A", "", 777, date(2026, 11, 1)),
                                    ("bank", "", "", 777, date(2026, 11, 2))])
        self._match(run)
        self.assertIn("LOW_CONFIDENCE", run.item_ids.filtered(lambda i: i.side == "bank").method)

    def test_bad_bank_reference_amount_differs(self):
        run = self._run("bank", 0, [("source", "R1", "", 500, date(2026, 11, 1)),
                                    ("bank", "R1", "", 490, date(2026, 11, 2))])
        self._match(run)
        self.assertIn("differs", run.exception_ids.description)

    def test_unidentified_bank_item(self):
        run = self._run("bank", 0, [("bank", "ZZ", "", 3500, date(2026, 11, 8))])
        self._match(run)
        self.assertEqual(run.exception_ids.description, "Unidentified bank item")

    def test_only_finance_can_run_matching(self):
        run = self._run("bank", 0, [("bank", "ZZ", "", 1, date(2026, 11, 8))])
        with self.assertRaises(UserError):
            run.with_user(self.ops).action_match()

    # --- exception governance
    def _exception(self):
        run = self._run("bank", 0, [("bank", "ZZ", "", 100, date(2026, 11, 8))])
        self._match(run)
        return run.exception_ids

    def test_close_requires_owner_resolution_note(self):
        exc = self._exception()
        with self.assertRaises(UserError):
            exc.with_user(self.fin1).action_propose_close()          # no owner
        exc.with_user(self.fin1).action_assign_to_me()
        with self.assertRaises(UserError):
            exc.with_user(self.fin1).action_propose_close()          # no resolution/note

    def test_maker_checker_on_closure(self):
        exc = self._exception()
        exc.with_user(self.fin1).action_assign_to_me()
        exc.write({"resolution": "explained", "note": "DEMO: timing difference"})
        exc.with_user(self.fin1).action_propose_close()
        with self.assertRaises(UserError):
            exc.with_user(self.fin1).action_approve_close()          # same person
        exc.with_user(self.fin2).action_approve_close()
        self.assertEqual(exc.state, "closed")
        self.assertEqual(exc.approved_by, self.fin2)

    # --- Distribution Partner
    def test_stock_rollforward_and_variance(self):
        run = self._run("partner_stock", 0)
        line = self.env["pharma.partner.stock.line"].create({
            "run_id": run.id, "sku": "DEMO-SKU-A", "lot": "DEMO-LOT-01", "location": "DEMO-PARTNER-WH1",
            "opening": 100, "inward_accepted": 50, "adj_positive_approved": 2, "sold_or_issued": 80,
            "returned_to_pharma": 5, "expired_damaged_documented": 3, "adj_negative_approved": 1,
            "reported": 60})
        self.assertEqual((line.expected_closing, line.variance), (63, -3))
        line.action_raise_exceptions()
        line.action_raise_exceptions()                                # idempotent
        self.assertEqual(len(run.exception_ids), 1)
        self.assertFalse(run.exception_ids.owner_id)

    def test_scenario_gate_blocks_revenue_but_records_custody(self):
        r = self.env["pharma.partner.scenario"].custody_transfer("DEMO-SKU-A", "DEMO-LOT-01", 100)
        self.assertTrue(r["custody_move"])
        self.assertFalse(r["revenue_recognised"])
        self.assertFalse(r["tax_posted"])
        self.assertTrue(r["status"].startswith("BLOCKED_AWAITING_CLIENT"))

    def test_scenario_incomplete_signoff_still_blocked(self):
        self.env["pharma.partner.scenario"].create({"scenario": "A", "contract_ref": "DEMO-CONTRACT",
                                                "finance_signoff_id": self.fin1.id})
        r = self.env["pharma.partner.scenario"].custody_transfer("S", "L", 1)
        self.assertTrue(r["status"].startswith("BLOCKED"))

    def test_scenarios_b_and_c_never_a_sale(self):
        for sc in ("B", "C"):
            self.env["pharma.partner.scenario"].search([]).unlink()
            self.env["pharma.partner.scenario"].create({"scenario": sc, "contract_ref": "DEMO-CONTRACT",
                "finance_signoff_id": self.fin1.id, "tax_signoff_id": self.fin2.id})
            self.assertFalse(self.env["pharma.partner.scenario"].custody_transfer("S", "L", 1)["revenue_recognised"])

    def test_scenario_a_needs_title_transfer_evidence(self):
        self.env["pharma.partner.scenario"].create({"scenario": "A", "contract_ref": "DEMO-CONTRACT",
            "finance_signoff_id": self.fin1.id, "tax_signoff_id": self.fin2.id})
        self.assertEqual(self.env["pharma.partner.scenario"].custody_transfer("S", "L", 1)["revenue_recognised"],
                         "pending_title_transfer_evidence")

    # --- raw event archive (core)
    def test_raw_event_idempotent_conflict_immutable(self):
        E = self.env["pharma.raw.event"]
        rec, out = E.ingest("shopify", "W1", '{"a":1}', is_demo=True)
        self.assertEqual(out, "archived")
        self.assertEqual(E.ingest("shopify", "W1", '{"a":1}')[1], "duplicate_ignored")
        self.assertEqual(E.ingest("shopify", "W1", '{"a":2}')[1], "conflict")
        self.assertEqual(E.search_count([("event_id", "=", "W1")]), 1)
        self.assertEqual(rec.payload, '{"a":1}')                       # never overwritten
        with self.assertRaises(UserError):
            rec.write({"payload": "x"})
        with self.assertRaises(UserError):
            rec.unlink()
