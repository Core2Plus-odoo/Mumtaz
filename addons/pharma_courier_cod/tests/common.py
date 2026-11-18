from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "pharma")
class CourierCase(TransactionCase):
    """Shared fixtures. DEMO / fictional data only. Logins are prefixed so they never collide with the users the other
    pharma test suites create in their own setUp."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        U = cls.env["res.users"].with_context(no_reset_password=True)
        base = cls.env.ref("base.group_user").id
        g = lambda x: cls.env.ref("pharma_core." + x).id
        cls.fin = U.create({"name": "COD Finance", "login": "cod_fin", "group_ids": [(6, 0, [base, g("group_pharma_finance")])]})
        cls.ops = U.create({"name": "COD Ops", "login": "cod_ops", "group_ids": [(6, 0, [base, g("group_pharma_user")])]})
        cls.adm = U.create({"name": "COD Admin", "login": "cod_adm", "group_ids": [(6, 0, [base, g("group_pharma_admin")])]})
        cls.courier = cls.env["pharma.courier"].create(
            {"name": "Test Courier", "code": "TCOD", "remittance_cycle_days": 14, "is_demo": True})
        cls.courier2 = cls.env["pharma.courier"].create({"name": "Other Courier", "code": "OCOD", "is_demo": True})
        cls.partner = cls.env["res.partner"].create({"name": "COD Test Customer"})
        cls.today = fields.Date.context_today(cls.env["pharma.courier.shipment"])
        cls.Ship = cls.env["pharma.courier.shipment"]
        cls.Rem = cls.env["pharma.courier.remittance"]
        cls.Exc = cls.env["pharma.recon.exception"]

    # ---------------------------------------------------------------- builders
    def _order(self, ref):
        return self.env["sale.order"].create({"partner_id": self.partner.id, "client_order_ref": ref})

    def _ship(self, trk, declared=1000.0, collected=None, days_ago=3, state="delivered", mode="cod",
              with_order=True, courier=None, **kw):
        """A shipment, by default delivered `days_ago` days ago with a matching sale order so the 'no matching order'
        finding stays out of tests that are about something else."""
        if with_order:
            self._order(trk)
        vals = {"courier_id": (courier or self.courier).id, "tracking_number": trk, "state": state,
                "payment_mode": mode, "cod_declared": declared,
                "cod_collected": declared if collected is None else collected, "is_demo": True}
        if with_order:
            vals["order_ref"] = trk
        if days_ago is not None:
            vals["date_delivered"] = self.today - timedelta(days=days_ago)
        vals.update(kw)
        return self.Ship.create(vals)

    def _remit(self, slip, rows, bank=None, post=True, courier=None, **kw):
        """rows: (shipment, gross, {deduction field: amount})."""
        lines = [Command.create({"shipment_id": s.id, "amount_gross": g, **d}) for s, g, d in rows]
        rem = self.Rem.create({"courier_id": (courier or self.courier).id, "slip_ref": slip, "date": self.today,
                               "is_demo": True, "line_ids": lines, **kw})
        if bank is not None:
            rem.bank_amount = bank
        if post:
            rem.action_post()
        return rem

    def _exc(self, key):
        return self.Exc.search([("dedupe_key", "=", key)])
