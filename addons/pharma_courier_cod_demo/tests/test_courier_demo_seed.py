import csv
import os

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path

SAMPLES = "pharma_courier_cod_demo/static/samples"


@tagged("post_install", "-at_install", "pharma")
class TestCourierDemoSeed(TransactionCase):
    """The seeder ran once at install (post_init_hook). These tests prove each COD scenario exists and that running the
    seeder again changes nothing."""

    def _counts(self):
        env = self.env
        return {m: env[m].sudo().search_count([]) for m in (
            "pharma.courier", "pharma.courier.shipment", "pharma.courier.remittance", "pharma.courier.remittance.line",
            "pharma.courier.statement", "pharma.courier.statement.line", "pharma.recon.run", "pharma.recon.exception",
            "pharma.raw.event", "sale.order")}

    def _ship(self, trk):
        return self.env["pharma.courier.shipment"].sudo().search([("tracking_number", "=", trk)])

    def _exc(self, key):
        return self.env["pharma.recon.exception"].sudo().search([("dedupe_key", "=", key)])

    def test_seed_is_idempotent(self):
        self.env["pharma.courier.demo.seed"].seed()
        before = self._counts()
        self.env["pharma.courier.demo.seed"].seed()
        self.assertEqual(self._counts(), before)

    def test_couriers_are_generic_and_flagged_demo(self):
        couriers = self.env["pharma.courier"].sudo().search([("code", "like", "DEMO%")])
        self.assertEqual(sorted(couriers.mapped("name")), ["Courier A (DEMO)", "Courier B (DEMO)"])
        self.assertTrue(all(couriers.mapped("is_demo")))

    def test_the_clean_batch_matches_with_no_findings(self):
        run = self.env["pharma.recon.run"].sudo().search([("name", "=", "COD DEMOA DEMO-SL-A-1001")])
        self.assertEqual((run.state, run.open_exceptions), ("matched", 0))
        self.assertEqual(set(self._ship("DEMO-A-0001").mapped("cod_state")), {"remitted"})

    def test_the_variance_batch_raises_all_three_findings(self):
        self.assertTrue(self._exc("DEMOA/DEMO-A-0004/collection"))           # customer paid less than declared
        self.assertTrue(self._exc("DEMOA/DEMO-A-0005/remittance"))           # courier remitted less than collected
        run = self.env["pharma.recon.run"].sudo().search([("name", "=", "COD DEMOA DEMO-SL-A-1002")])
        self.assertEqual(run.state, "partial")
        self.assertTrue(run.open_exceptions)                                 # incl. the bank deposit being 400 short

    def test_deductions_above_the_authorized_amount_are_a_finding(self):
        rem = self.env["pharma.courier.remittance"].sudo().search([("slip_ref", "=", "DEMO-SL-B-1001")])
        self.assertEqual((rem.amount_deductions, rem.deductions_authorized, rem.deductions_excess), (800.0, 500.0, 300.0))
        exc = self.env["pharma.recon.exception"].sudo().search([("run_id", "=", rem.run_id.id), ("category", "=", "deduction")])
        self.assertEqual(len(exc), 1)

    def test_parcels_are_spread_across_the_ageing_buckets(self):
        """Ageing moves with the calendar, so the test does not assume today is the day of seeding: it checks the
        seeded delivery dates are 5/10/20/45 days apart from today-at-seeding, then that ageing agrees with them."""
        ships = {t: self._ship(t) for t in ("DEMO-A-0101", "DEMO-A-0102", "DEMO-A-0103", "DEMO-A-0104")}
        base = ships["DEMO-A-0101"].date_delivered
        offsets = [(base - s.date_delivered).days for s in ships.values()]
        self.assertEqual(offsets, [0, 5, 15, 40])
        today = fields.Date.context_today(self.env["pharma.courier.shipment"])
        ships_all = self.env["pharma.courier.shipment"].sudo().concat(*ships.values())
        ships_all.action_refresh_ageing()
        for s in ships_all:
            days = (today - s.date_delivered).days
            self.assertEqual(s.cod_days_outstanding, days, s.tracking_number)
            self.assertEqual(s.cod_is_overdue, days > s.courier_id.remittance_cycle_days, s.tracking_number)
        buckets = {s.cod_ageing_bucket for s in ships_all}
        self.assertGreaterEqual(len(buckets), 2)
        self.assertTrue(self._exc("DEMOA/DEMO-A-0104/overdue"))
        self.assertTrue(self._exc("DEMOB/DEMO-B-0102/overdue"))              # 9 days old, Courier B's cycle is 7

    def test_single_parcel_findings(self):
        self.assertTrue(self._exc("DEMOB/DEMO-B-0201/returned_cod"))
        self.assertTrue(self._exc("DEMOA/DEMO-A-0301/intake"))
        self.assertFalse(self._ship("DEMO-A-0301").sale_order_id)
        self.assertEqual(self._ship("DEMO-A-0302").state, "in_transit")
        self.assertEqual(self._ship("DEMO-B-0301").payment_mode, "prepaid")

    def test_the_built_upload_and_the_one_with_errors(self):
        Stmt = self.env["pharma.courier.statement"].sudo()
        built = Stmt.search([("statement_type", "=", "shipments"), ("line_ids.reference", "=", "DEMO-A-0001")])
        self.assertEqual((built.state, built.shipments_created), ("built", 8))
        bad = Stmt.search([("line_ids.order_ref", "=", "DEMO-ERR-ROW")])
        self.assertEqual((bad.state, bad.error_count), ("draft", 3))
        self.assertFalse(self._ship("DEMO-B-0901"))                          # nothing from a failed upload reaches the ledger

    def test_sample_files_match_the_demo(self):
        """The sample CSVs are what the presenter uploads live. Headings must be field labels so the import screen
        maps them on its own, and the slip must reference parcels that are waiting for remittance."""
        labels = {f["string"] for f in self.env["pharma.courier.statement.line"].fields_get().values()}
        for name in ("courier_a_delivery_report.csv", "courier_a_remittance_slip.csv"):
            with open(file_path(os.path.join(SAMPLES, name)), newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertTrue(rows, name)
            self.assertFalse(set(rows[0]) - labels, (name, set(rows[0]) - labels))
        with open(file_path(os.path.join(SAMPLES, "courier_a_remittance_slip.csv")), newline="") as fh:
            for row in csv.DictReader(fh):
                ship = self._ship(row["Tracking Number"])
                self.assertEqual((ship.state, ship.cod_state), ("delivered", "outstanding"), row)
        with open(file_path(os.path.join(SAMPLES, "courier_a_delivery_report.csv")), newline="") as fh:
            for row in csv.DictReader(fh):
                self.assertFalse(self._ship(row["Tracking Number"]), row)    # new parcels, so the upload creates them
