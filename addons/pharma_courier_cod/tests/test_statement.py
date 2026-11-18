import json
from datetime import timedelta

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import CourierCase

# The column headings of the sample files shipped with the demo. Odoo's import screen maps a file column to a field by
# its label, so these must stay the labels of the staging fields or uploads stop auto-mapping.
SAMPLE_HEADERS = ["Tracking Number", "Order Reference", "Consignee", "Destination City", "Status", "Booked Date",
                  "Delivered Date", "COD Declared", "COD Collected", "COD Remitted (Gross)", "Freight Deducted",
                  "COD Fee Deducted", "Withholding Income Tax", "Withholding Sales Tax", "Other Deductions"]


@tagged("post_install", "-at_install", "pharma")
class TestCourierStatement(CourierCase):

    def _stmt(self, rows, kind="shipments", **kw):
        vals = {"courier_id": self.courier.id, "statement_type": kind, "is_demo": True,
                "line_ids": [Command.create(r) for r in rows]}
        vals.update(kw)
        return self.env["pharma.courier.statement"].create(vals)

    def _rem_stmt(self, rows, slip="SL-1", bank=0.0, **kw):
        return self._stmt(rows, kind="cod_remittance", slip_ref=slip, remittance_date=self.today, bank_amount=bank, **kw)

    def _day(self, n):
        return self.today - timedelta(days=n)

    def _errors(self, st):
        st.action_validate()
        return st, st.line_ids.mapped("error_message")

    # ------------------------------------------------------------------ validation: delivery reports
    def test_a_good_delivery_report_validates(self):
        st = self._stmt([{"reference": "D1", "provider_status": "Delivered", "date_delivered": self._day(1),
                          "cod_declared": 1000, "cod_collected": 1000}])
        st.action_validate()
        self.assertEqual((st.state, st.error_count, st.line_ids.state), ("validated", 0, "valid"))

    def test_bad_delivery_rows_are_caught_with_a_reason(self):
        cases = [
            ({"reference": ""}, "No tracking number"),
            ({"reference": "X1", "cod_declared": -5}, "negative"),
            ({"reference": "X2", "date_booked": self._day(1), "date_delivered": self._day(3)}, "before it was booked"),
            ({"reference": "X3", "provider_status": "Delivered"}, "no delivery date"),
        ]
        for row, expected in cases:
            st, errors = self._errors(self._stmt([row]))
            self.assertEqual((st.state, st.error_count), ("draft", 1), expected)
            self.assertIn(expected, errors[0])

    def test_a_tracking_number_twice_in_one_file_is_an_error(self):
        st = self._stmt([{"reference": "DUP1", "provider_status": "Booked"}, {"reference": "DUP1", "provider_status": "Booked"}])
        st.action_validate()
        self.assertEqual(st.line_ids.mapped("state"), ["valid", "error"])
        self.assertIn("Duplicated", st.line_ids[1].error_message)

    def test_validating_never_touches_the_ledger(self):
        before = (self.Ship.search_count([]), self.Rem.search_count([]))
        self._stmt([{"reference": "N1", "provider_status": "Booked"}]).action_validate()
        self.assertEqual((self.Ship.search_count([]), self.Rem.search_count([])), before)

    # ------------------------------------------------------------------ validation: remittance slips
    def test_the_slip_header_is_checked(self):
        with self.assertRaises(UserError):
            self._stmt([], kind="cod_remittance").action_validate()                                   # no slip
        with self.assertRaises(UserError):
            self._stmt([], kind="cod_remittance", slip_ref="S").action_validate()                      # no date
        self._remit("TAKEN", [(self._ship("H1"), 1000, {})], post=False)
        with self.assertRaises(UserError) as cm:
            self._rem_stmt([], slip="TAKEN").action_validate()
        self.assertIn("already has remittance", str(cm.exception))

    def test_bad_remittance_rows_are_caught_with_a_reason(self):
        self._ship("P1", mode="prepaid")
        self._ship("T1", state="in_transit", days_ago=None)
        self._ship("O1", declared=1000)
        done = self._ship("C1", declared=1000)
        self._remit("PRIOR", [(done, 600, {})])
        cases = [
            ({"reference": "NOPE", "amount_gross": 100}, "Upload the delivery report first"),
            ({"reference": "P1", "amount_gross": 100}, "not a COD shipment"),
            ({"reference": "T1", "amount_gross": 100}, "not delivered"),
            ({"reference": "O1", "amount_gross": 1200}, "Remits 1200.00"),
            ({"reference": "C1", "amount_gross": 600}, "already accounted for"),
            ({"reference": "O1", "amount_gross": 0}, "No remitted amount"),
            ({"reference": "O1", "amount_gross": 100, "deduction_freight": 150}, "exceed"),
        ]
        for i, (row, expected) in enumerate(cases):
            st, errors = self._errors(self._rem_stmt([row], slip=f"BAD-{i}"))
            self.assertEqual(st.state, "draft", expected)
            self.assertIn(expected, errors[0])

    def test_a_good_remittance_row_is_matched_to_its_shipment(self):
        s = self._ship("G1")
        st = self._rem_stmt([{"reference": "G1", "amount_gross": 1000, "deduction_freight": 100}], slip="GOOD", bank=900)
        st.action_validate()
        self.assertEqual((st.state, st.line_ids.shipment_id), ("validated", s))

    def test_a_row_can_be_fixed_and_validated_again(self):
        st = self._rem_stmt([{"reference": "LATE1", "amount_gross": 100}], slip="FIX")
        st.action_validate()
        self.assertEqual(st.state, "draft")
        self._ship("LATE1", declared=100)
        st.action_validate()
        self.assertEqual((st.state, st.error_count), ("validated", 0))

    # ------------------------------------------------------------------ build: delivery reports
    def _delivery_report(self):
        self._order("ORD-A")
        return self._stmt([
            {"reference": "SA", "order_ref": "ORD-A", "provider_status": "Delivered", "consignee_name": "Ali",
             "destination_city": "Lahore", "date_booked": self._day(5), "date_delivered": self._day(2),
             "cod_declared": 1000, "cod_collected": 1000},
            {"reference": "SB", "provider_status": "Undelivered", "date_booked": self._day(3), "cod_declared": 500},
            {"reference": "SC", "provider_status": "Returned to Shipper", "cod_declared": 700, "cod_collected": 700},
            {"reference": "SD", "provider_status": "Delivered", "date_delivered": self._day(1)},
        ])

    def test_build_needs_validation_and_a_finance_controller(self):
        st = self._delivery_report()
        with self.assertRaises(UserError):
            st.with_user(self.fin).action_build()                       # not validated yet
        st.action_validate()
        with self.assertRaises(UserError):
            st.with_user(self.ops).action_build()                       # not a Finance Controller
        with self.assertRaises(AccessError):
            self.env["pharma.courier.statement"].with_user(self.ops).create({"courier_id": self.courier.id})

    def test_a_delivery_report_builds_shipments(self):
        st = self._delivery_report()
        st.action_validate()
        st.with_user(self.fin).action_build()
        self.assertEqual((st.state, st.shipments_created, st.shipments_updated), ("built", 4, 0))
        self.assertEqual(set(st.line_ids.mapped("state")), {"built"})
        by = {s.tracking_number: s for s in st.line_ids.shipment_id}
        self.assertEqual((by["SA"].state, by["SA"].consignee_name, by["SA"].destination_city),
                         ("delivered", "Ali", "Lahore"))
        self.assertTrue(by["SA"].order_matched)
        self.assertEqual(by["SB"].state, "in_transit")
        self.assertEqual(by["SC"].state, "returned")
        self.assertEqual((by["SD"].state, by["SD"].payment_mode), ("delivered", "prepaid"))       # nothing declared
        self.assertEqual(by["SA"].cod_state, "outstanding")
        self.assertTrue(self._exc("TCOD/SC/returned_cod"))                                         # findings follow the build
        self.assertTrue(self._exc("TCOD/SB/intake"))
        self.assertFalse(self._exc("TCOD/SA/intake"))

    def test_every_built_row_is_archived_unchanged_in_the_raw_event_log(self):
        st = self._delivery_report()
        st.action_validate()
        st.with_user(self.fin).action_build()
        ev = self.env["pharma.raw.event"].search([("event_id", "=", f"TCOD:{st.name}:SA")])
        self.assertEqual((ev.source, ev.is_demo, ev.state), ("courier", True, "archived"))
        payload = json.loads(ev.payload)
        self.assertEqual((payload["reference"], payload["status"], payload["cod_collected"]), ("SA", "Delivered", 1000.0))
        self.assertEqual(st.line_ids.filtered(lambda l: l.reference == "SA").shipment_id.raw_event_id, ev)

    def test_a_later_thinner_report_updates_without_erasing(self):
        first = self._delivery_report()
        first.action_validate()
        first.with_user(self.fin).action_build()
        second = self._stmt([{"reference": "SA", "provider_status": "Delivered", "date_delivered": self._day(2),
                              "cod_collected": 900}])
        second.action_validate()
        second.with_user(self.fin).action_build()
        a = self.Ship.search([("tracking_number", "=", "SA")])
        self.assertEqual((second.shipments_created, second.shipments_updated), (0, 1))
        self.assertEqual((a.cod_collected, a.cod_declared, a.consignee_name), (900.0, 1000.0, "Ali"))
        self.assertEqual(self.Ship.search_count([("tracking_number", "=", "SA")]), 1)
        ev = self.env["pharma.raw.event"].search([("event_id", "=", f"TCOD:{second.name}:SA")])
        self.assertEqual(ev.state, "archived")                      # a changed row in a new file is a new event, not a conflict

    def test_a_built_statement_cannot_be_built_or_cancelled_again(self):
        st = self._delivery_report()
        st.action_validate()
        st.with_user(self.fin).action_build()
        with self.assertRaises(UserError):
            st.with_user(self.fin).action_build()
        with self.assertRaises(UserError):
            st.action_cancel()
        with self.assertRaises(UserError):
            st.unlink()
        with self.assertRaises(UserError):
            st.action_upload_file()

    # ------------------------------------------------------------------ build: remittance slips
    def test_a_remittance_slip_builds_a_draft_remittance(self):
        k1, k2 = self._ship("K1", declared=1000), self._ship("K2", declared=2000)
        st = self._rem_stmt([
            {"reference": "K1", "amount_gross": 1000, "deduction_freight": 100, "deduction_wht_income_tax": 20},
            {"reference": "K2", "amount_gross": 2000, "deduction_cod_fee": 200, "deduction_wht_sales_tax": 30}],
            slip="SL-9", bank=2650)
        st.action_validate()
        st.with_user(self.fin).action_build()
        rem = st.remittance_id
        self.assertEqual((st.state, rem.state, rem.slip_ref, rem.date, rem.bank_amount, rem.statement_id),
                         ("built", "draft", "SL-9", self.today, 2650.0, st))
        self.assertEqual((rem.amount_gross, rem.amount_deductions, rem.amount_net, rem.amount_bank_variance),
                         (3000.0, 350.0, 2650.0, 0.0))
        l1 = rem.line_ids.filtered(lambda l: l.shipment_id == k1)
        self.assertEqual((l1.deduction_freight, l1.deduction_wht_income_tax, l1.amount_net), (100.0, 20.0, 880.0))
        self.assertTrue(all(rem.line_ids.mapped("raw_event_id")))
        self.assertEqual(k1.cod_remitted, 0.0)                      # a draft counts for nothing until posted
        rem.action_post()
        self.assertEqual((k1.cod_remitted, k2.cod_state), (1000.0, "remitted"))

    def test_from_the_courier_file_to_a_reconciled_run(self):
        for ref in ("E1", "E2"):
            self._order(ref)
        report = self._stmt([
            {"reference": "E1", "order_ref": "E1", "provider_status": "Delivered", "date_delivered": self._day(4),
             "cod_declared": 1000, "cod_collected": 1000},
            {"reference": "E2", "order_ref": "E2", "provider_status": "Delivered", "date_delivered": self._day(4),
             "cod_declared": 2000, "cod_collected": 2000}])
        report.action_validate()
        report.with_user(self.fin).action_build()
        slip = self._rem_stmt([{"reference": "E1", "amount_gross": 1000, "deduction_freight": 100},
                               {"reference": "E2", "amount_gross": 2000, "deduction_freight": 200}], slip="SL-E2E", bank=2700)
        slip.action_validate()
        self.assertEqual(slip.state, "validated")
        slip.with_user(self.fin).action_build()
        rem = slip.remittance_id
        rem.action_post()
        rem.with_user(self.fin).action_reconcile()
        self.assertEqual((rem.run_state, rem.open_exceptions), ("matched", 0))
        self.assertEqual(set(rem.line_ids.shipment_id.mapped("cod_state")), {"remitted"})

    # ------------------------------------------------------------------ the upload screen and housekeeping
    def test_upload_opens_odoos_own_import_screen_with_the_statement_filled_in(self):
        st = self._stmt([])
        action = st.action_upload_file()
        self.assertEqual((action["type"], action["tag"]), ("ir.actions.client", "import"))
        self.assertEqual(action["params"]["active_model"], "pharma.courier.statement.line")
        self.assertEqual(action["params"]["context"]["default_statement_id"], st.id)

    def test_staging_field_labels_match_the_sample_file_headings(self):
        labels = {f["string"] for f in self.env["pharma.courier.statement.line"].fields_get().values()}
        self.assertFalse(set(SAMPLE_HEADERS) - labels, set(SAMPLE_HEADERS) - labels)

    def test_draft_and_cancelled_statements_can_go(self):
        st = self._stmt([{"reference": "Z1"}])
        st.action_cancel()
        self.assertEqual(st.state, "cancel")
        st.unlink()
        self.assertFalse(self.env["pharma.courier.statement.line"].search([("reference", "=", "Z1")]))
        self._stmt([{"reference": "Z2"}]).unlink()

    def test_statement_names_come_from_a_sequence(self):
        a, b = self._stmt([]), self._stmt([])
        self.assertTrue(a.name.startswith("PCS/") and b.name.startswith("PCS/"))
        self.assertNotEqual(a.name, b.name)
