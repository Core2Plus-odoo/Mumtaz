"""Idempotent seeder for the courier COD DEMO scenarios. Fictional, DEMO-flagged. Natural keys (courier code, tracking
number, order reference, slip reference) decide whether a record exists, so `seed()` runs at install and again on every
upgrade without creating anything twice. Real business methods are used throughout (validate, build, post, reconcile),
run as the demo Finance Controller, so the data went through the same code and the same access rules a user would."""
import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, Command, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

FREIGHT, COD_FEE, WHT_SALES = 200.0, 50.0, 30.0           # typical per-parcel deductions on a slip
# courier accounting field -> (account code, name, account type). Fictional accounts created only if absent.
DEMO_ACCOUNTS = {
    "acc_clearing_account_id": ("199910", "DEMO Courier COD clearing", "asset_current"),
    "acc_bank_account_id": ("199911", "DEMO Courier receipts", "asset_current"),
    "acc_wht_income_account_id": ("199912", "DEMO Withholding income tax receivable", "asset_current"),
    "acc_wht_sales_account_id": ("199913", "DEMO Withholding sales tax receivable", "asset_current"),
    "acc_freight_account_id": ("599910", "DEMO Courier freight", "expense"),
    "acc_cod_fee_account_id": ("599911", "DEMO Courier COD fee", "expense"),
    "acc_other_account_id": ("599912", "DEMO Courier other deductions", "expense"),
    "acc_difference_account_id": ("599913", "DEMO Courier remittance difference", "expense"),
}


class PharmaCourierDemoSeed(models.AbstractModel):
    _name = "pharma.courier.demo.seed"
    _description = "Courier COD DEMO data seeder (fictional, idempotent)"

    # ------------------------------------------------------------------ entry
    @api.model
    def seed(self):
        env = api.Environment(self.env.cr, SUPERUSER_ID, {"no_reset_password": True, "mail_create_nolog": True,
                                                          "tracking_disable": True})
        s = env["pharma.courier.demo.seed"]
        finance = env["res.users"].search([("login", "=", "pharma.finance")], limit=1)
        product = env["product.product"].search([("default_code", "=", "DEMO-SKU-A")], limit=1)
        if not finance or not product:
            _logger.warning("pharma_courier_cod_demo: demo users or SKU missing (is pharma_demo_data installed?); skipped")
            return
        s = s.with_context(seed_today=fields.Date.context_today(env["pharma.courier"]))
        a, b = s._seed_couriers()
        s._seed_delivery_report_a(a, finance, product)
        s._seed_clean_batch(a, finance)
        s._seed_variance_batch(a, finance, product)
        s._seed_unauthorized_deductions(b, finance, product)
        s._seed_ageing_and_edge_cases(a, b, finance, product)
        s._seed_error_statement(b, finance)
        s._seed_sample_file_orders(a, product)
        s._seed_accounting(a, b, finance)
        env["pharma.courier.shipment"].action_refresh_all()

    # ------------------------------------------------------------------ helpers
    def _day(self, n):
        return self.env.context["seed_today"] - timedelta(days=n)

    def _seed_couriers(self):
        Courier = self.env["pharma.courier"]

        def courier(code, name, cycle, tolerance):
            return Courier.search([("code", "=", code)], limit=1) or Courier.create({
                "name": name, "code": code, "remittance_cycle_days": cycle, "variance_tolerance": tolerance,
                "is_demo": True})
        return courier("DEMOA", "Courier A (DEMO)", 14, 1.0), courier("DEMOB", "Courier B (DEMO)", 7, 0.0)

    def _sale_order(self, product, ref, amount):
        """A confirmed sale order the shipment can be matched to. Approved SKU, so the tax gate passes it."""
        SO = self.env["sale.order"]
        so = SO.search([("client_order_ref", "=", ref)], limit=1)
        if so:
            return so
        partner = self.env["res.partner"].search([("name", "=", "DEMO Customer (fictional)")], limit=1) or \
            self.env["res.partner"].create({"name": "DEMO Customer (fictional)", "email": "demo.customer@example.invalid",
                                            "street": "DEMO street 1", "city": "DEMO City"})
        so = SO.create({"partner_id": partner.id, "client_order_ref": ref, "origin": "DEMO " + ref,
                        "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1,
                                                       "price_unit": amount})]})
        so.action_confirm()
        return so

    def _ship(self, courier, product, trk, declared, collected=None, days_ago=None, state="delivered", mode="cod",
              with_order=True, order_ref=None, city="DEMO City", **kw):
        """A shipment created directly (the ones not created through an upload). Existing ones are left alone."""
        Ship = self.env["pharma.courier.shipment"]
        found = Ship.search([("courier_id", "=", courier.id), ("tracking_number", "=", trk)], limit=1)
        if found:
            return found
        ref = order_ref or f"DEMO-ORD-{trk[5:]}"
        if with_order:
            self._sale_order(product, ref, declared)
        vals = {"courier_id": courier.id, "tracking_number": trk, "order_ref": ref, "state": state,
                "payment_mode": mode, "cod_declared": declared, "destination_city": city, "is_demo": True,
                "consignee_name": "DEMO Consignee", "date_booked": self._day((days_ago or 1) + 3),
                "cod_collected": declared if collected is None else collected}
        if days_ago is not None and state in ("delivered", "returned"):
            vals["date_delivered"] = self._day(days_ago)
        vals.update(kw)
        return Ship.create(vals)

    def _statement(self, courier, kind, marker_domain, rows, finance, **vals):
        """Create, validate and (when clean) build one statement as the Finance Controller. `marker_domain` finds an
        earlier copy of it so a second run adds nothing."""
        Stmt = self.env["pharma.courier.statement"]
        if Stmt.search([("courier_id", "=", courier.id), ("statement_type", "=", kind)] + marker_domain, limit=1):
            return Stmt
        st = Stmt.create({"courier_id": courier.id, "statement_type": kind, "is_demo": True, **vals,
                          "line_ids": [Command.create(r) for r in rows]})
        st.action_validate()
        if st.state == "validated":
            st.with_user(finance).action_build()
        return st

    # ------------------------------------------------------------------ scenarios
    def _seed_delivery_report_a(self, a, finance, product):
        """A built upload: eight parcels created from one courier delivery report, three of which stay awaiting
        remittance for the live remittance-slip demonstration."""
        rows = [(1, 2500, 24), (2, 4200, 24), (3, 1800, 24), (4, 3000, 12, 2700), (5, 5000, 12),
                (201, 2600, 4), (202, 3400, 4), (203, 1500, 4)]
        lines = []
        for r in rows:
            n, declared, ago = r[0], r[1], r[2]
            collected = r[3] if len(r) > 3 else declared
            ref = f"DEMO-ORD-A-{n:04d}"
            self._sale_order(product, ref, declared)
            lines.append({"reference": f"DEMO-A-{n:04d}", "order_ref": ref, "consignee_name": "DEMO Consignee",
                          "destination_city": ("Lahore", "Karachi", "Islamabad")[n % 3], "provider_status": "Delivered",
                          "date_booked": self._day(ago + 3), "date_delivered": self._day(ago),
                          "cod_declared": declared, "cod_collected": collected})
        self._statement(a, "shipments", [("line_ids.reference", "=", "DEMO-A-0001")], lines, finance)

    def _slip(self, courier, finance, slip, rows, bank_less=0.0, **vals):
        """rows: (tracking, gross, {deduction field: amount}). Builds the slip as a statement, posts and reconciles it."""
        net = sum(g - sum(d.values()) for _t, g, d in rows)
        lines = [{"reference": t, "amount_gross": g, **d} for t, g, d in rows]
        st = self._statement(courier, "cod_remittance", [("slip_ref", "=", slip)], lines, finance, slip_ref=slip,
                             remittance_date=self._day(3), bank_amount=net - bank_less, **vals)
        rem = st.remittance_id
        if rem and rem.state == "draft":
            rem.action_post()
            rem.with_user(finance).action_reconcile()

    def _seed_clean_batch(self, a, finance):
        """Everything lines up: collected = declared = remitted gross, bank = net of the itemised deductions."""
        d = {"deduction_freight": FREIGHT, "deduction_cod_fee": COD_FEE, "deduction_wht_sales_tax": WHT_SALES}
        self._slip(a, finance, "DEMO-SL-A-1001", [("DEMO-A-0001", 2500, d), ("DEMO-A-0002", 4200, d),
                                                  ("DEMO-A-0003", 1800, d)])

    def _seed_variance_batch(self, a, finance, product):
        """One batch, three findings: a customer who paid less than declared (DEMO-A-0004), a courier that remitted
        less than it collected (DEMO-A-0005) and a bank deposit short of the slip total."""
        d = {"deduction_freight": FREIGHT}
        self._slip(a, finance, "DEMO-SL-A-1002", [("DEMO-A-0004", 2700, d), ("DEMO-A-0005", 4600, d)], bank_less=400.0)

    def _seed_unauthorized_deductions(self, b, finance, product):
        """Courier B reports 800 of deductions against an authorized 500."""
        Rem = self.env["pharma.courier.remittance"]
        if Rem.search([("courier_id", "=", b.id), ("slip_ref", "=", "DEMO-SL-B-1001")], limit=1):
            return
        one = self._ship(b, product, "DEMO-B-0001", 3500, days_ago=10)
        two = self._ship(b, product, "DEMO-B-0002", 2200, days_ago=10)
        extra = {"deduction_freight": 250.0}
        rem = Rem.create({
            "courier_id": b.id, "slip_ref": "DEMO-SL-B-1001", "date": self._day(3), "is_demo": True,
            "check_deductions": True, "deductions_authorized": 500.0,
            "line_ids": [Command.create({"shipment_id": one.id, "amount_gross": 3500, **extra,
                                         "deduction_other": 300.0}),
                         Command.create({"shipment_id": two.id, "amount_gross": 2200, **extra})]})
        rem.bank_amount = rem.amount_net
        rem.action_post()
        rem.with_user(finance).action_reconcile()

    def _seed_ageing_and_edge_cases(self, a, b, finance, product):
        """One delivered-not-remitted parcel per ageing bucket, plus the single-parcel exceptions."""
        self._ship(a, product, "DEMO-A-0101", 2100, days_ago=5)         # 0-7 days
        self._ship(a, product, "DEMO-A-0102", 3300, days_ago=10)        # 8-15 days, inside Courier A's 14-day cycle
        self._ship(a, product, "DEMO-A-0103", 4100, days_ago=20)        # 16-30 days, overdue
        self._ship(a, product, "DEMO-A-0104", 6200, days_ago=45)        # 31+ days, overdue
        self._ship(b, product, "DEMO-B-0102", 1700, days_ago=9)         # Courier B's cycle is 7 days: overdue at 9
        # collected, then the parcel came back: the customer's money is with the courier
        self._ship(b, product, "DEMO-B-0201", 1900, days_ago=6, state="returned")
        # the courier reports an order the shop has no record of
        self._ship(a, product, "DEMO-A-0301", 2800, days_ago=8, with_order=False, order_ref="DEMO-UNKNOWN-0301")
        self._ship(a, product, "DEMO-A-0302", 2300, state="in_transit", collected=0.0)
        self._ship(b, product, "DEMO-B-0301", 0.0, days_ago=2, mode="prepaid", collected=0.0)

    def _seed_error_statement(self, b, finance):
        """An upload with three bad rows. Validation names each one and building stays blocked until they are fixed."""
        rows = [
            {"reference": "", "order_ref": "DEMO-ERR-ROW", "provider_status": "Delivered", "date_delivered": self._day(1)},
            {"reference": "DEMO-B-0901", "provider_status": "Delivered", "cod_declared": 1200.0},
            {"reference": "DEMO-B-0902", "provider_status": "Booked", "cod_declared": -50.0},
        ]
        self._statement(b, "shipments", [("line_ids.order_ref", "=", "DEMO-ERR-ROW")], rows, finance)

    def _seed_sample_file_orders(self, a, product):
        """Confirmed orders for the sample delivery report (static/samples), so its rows match an order on upload.
        DEMO-A-0406 is left without one on purpose: the upload then shows an intake finding."""
        for n, amount in ((401, 2400), (402, 1950), (403, 3100), (404, 2750), (405, 1600)):
            self._sale_order(product, f"DEMO-ORD-A-{n:04d}", amount)

    def _seed_accounting(self, a, b, finance):
        """Point both demo couriers at fictional accounts, then create ONE draft entry (the clean batch). The two other
        reconciled slips are left for the presenter to press Create journal entry on."""
        env = self.env
        journal = env["account.journal"].search([("type", "=", "general"), ("company_id", "=", env.company.id)], limit=1)
        if not journal:
            _logger.warning("pharma_courier_cod_demo: no general journal, accounting scenario skipped")
            return
        Account = env["account.account"]
        accounts = {}
        for fname, (code, name, typ) in DEMO_ACCOUNTS.items():
            accounts[fname] = Account.search([("code", "=", code)], limit=1) or \
                Account.create({"code": code, "name": name, "account_type": typ})
        for courier in (a, b):
            if not courier.acc_journal_id:
                courier.write({"acc_journal_id": journal.id, **{f: acc.id for f, acc in accounts.items()}})
        rem = env["pharma.courier.remittance"].search(
            [("courier_id", "=", a.id), ("slip_ref", "=", "DEMO-SL-A-1001")], limit=1)
        if rem and rem.run_id and not rem.move_id:
            rem.with_user(finance).action_create_entry()
        # the collection side of the same clean batch: the courier collected these three, so it holds the cash.
        # Together with the settlement entry above the clearing account nets to zero for this batch.
        for trk in ("DEMO-A-0001", "DEMO-A-0002", "DEMO-A-0003"):
            ship = env["pharma.courier.shipment"].search(
                [("courier_id", "=", a.id), ("tracking_number", "=", trk)], limit=1)
            if ship and not ship.collection_move_id:
                try:
                    ship.with_user(finance).action_create_collection_entry()
                except UserError as exc:
                    _logger.warning("pharma_courier_cod_demo: no collection entry for %s (%s)", trk, exc)
