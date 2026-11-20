"""The COD process flow. One path for every parcel:

    Booked -> In transit -> Delivered -> Collected -> Remitted -> Reconciled -> Closed
                               (returned and cancelled leave the path)

and for every remittance: Draft -> Posted -> Reconciled. Each record says what its next step is and who owns it, so
nobody needs to know which button to press: they open their queue. The stage and next step are COMPUTED from the real
records, never typed, so they cannot disagree with the data. Exceptions are a parallel track with their own queue (the
hub's Exception Queue); a parcel only counts its open findings here.

Other modules add steps by extending the two hooks, `_flow_compute` and `_flow_owner_map`, and adding selection values."""
from odoo import _, api, fields, models

FLOW_STAGES = [
    ("booked", "Booked"),
    ("in_transit", "In transit"),
    ("delivered", "Delivered"),
    ("collected", "Collected"),
    ("remitted", "Remitted"),
    ("reconciled", "Reconciled"),
    ("closed", "Closed"),
    ("returned", "Returned"),
    ("cancelled", "Cancelled"),
]
FLOW_OWNERS = [
    ("none", "Nobody"),
    ("ops", "Operations"),
    ("finance", "Finance Controller"),
    ("accountant", "Accountant"),
]
SHIPMENT_NEXT = [
    ("none", "Nothing further"),
    ("track", "Awaiting delivery"),
    ("confirm_collection", "Confirm what the courier collected"),
    ("await_remittance", "Awaiting the courier's remittance"),
    ("chase_remittance", "Chase the overdue remittance"),
    ("reconcile", "Reconcile the remittance against the bank"),
    ("settle_returned", "Settle the COD held on a returned parcel"),
]
REMITTANCE_NEXT = [
    ("none", "Nothing further"),
    ("post_slip", "Post the slip"),
    ("reconcile", "Reconcile against the bank"),
    ("resolve", "Resolve the open findings"),
]


class PharmaCourierShipmentFlow(models.Model):
    _inherit = "pharma.courier.shipment"

    flow_stage = fields.Selection(FLOW_STAGES, string="Stage", compute="_compute_flow", store=True, index=True)
    flow_next = fields.Selection(SHIPMENT_NEXT, string="Next Step", compute="_compute_flow", store=True, index=True)
    flow_owner = fields.Selection(FLOW_OWNERS, string="Next Step Owner", compute="_compute_flow", store=True, index=True)
    flow_next_text = fields.Char(string="What to do next", compute="_compute_flow_text")
    open_findings = fields.Integer(string="Open Findings", compute="_compute_open_findings",
                                   help="Open exceptions raised for this parcel. They are worked in the Exception Queue.")

    # ------------------------------------------------------------------ the rules
    def _flow_owner_map(self):
        return {"track": "ops", "confirm_collection": "finance", "await_remittance": "finance",
                "chase_remittance": "finance", "reconcile": "finance", "settle_returned": "finance"}

    def _flow_compute(self):
        """(stage, next step) from the real records. Extended by other modules; always returns a pair."""
        self.ensure_one()
        if self.state == "cancelled":
            return "cancelled", "none"
        if self.state == "returned":
            holds = self.payment_mode == "cod" and self.cod_collected > 0 and self.cod_remitted < self.cod_collected
            return "returned", "settle_returned" if holds else "none"
        if self.state == "booked":
            return "booked", "track"
        if self.state == "in_transit":
            return "in_transit", "track"
        if self.payment_mode != "cod":
            return "closed", "none"
        if self.cod_collected <= 0:
            return "delivered", "confirm_collection"
        posted = self.line_ids.filtered(lambda l: l.state == "posted")
        waiting = "chase_remittance" if self.cod_is_overdue else "await_remittance"
        if not posted or self.cod_remitted <= 0:
            return "collected", waiting
        if any(not l.remittance_id.run_id for l in posted):
            return "remitted", "reconcile"
        if self.cod_outstanding > (self.courier_id.variance_tolerance or 0.0):
            return "remitted", waiting           # remitted in part: the rest is still owed
        return "closed", "none"

    @api.depends("state", "payment_mode", "cod_collected", "cod_remitted", "cod_outstanding", "cod_is_overdue",
                 "line_ids.state", "line_ids.remittance_id.run_id", "courier_id.variance_tolerance")
    def _compute_flow(self):
        for s in self:
            stage, nxt = s._flow_compute()
            s.flow_stage, s.flow_next = stage, nxt
            s.flow_owner = s._flow_owner_map().get(nxt, "none")

    @api.depends("flow_next", "flow_owner")
    def _compute_flow_text(self):
        labels = dict(self._fields["flow_next"]._description_selection(self.env))
        owners = dict(self._fields["flow_owner"]._description_selection(self.env))
        for s in self:
            if s.flow_next == "none":
                s.flow_next_text = _("Nothing further")
            else:
                s.flow_next_text = _("%(step)s (%(owner)s)", step=labels.get(s.flow_next, s.flow_next),
                                     owner=owners.get(s.flow_owner, s.flow_owner))

    def _compute_open_findings(self):
        data = {src: n for src, n in self.env["pharma.recon.exception"].sudo()._read_group(
            [("source_model", "=", self._name), ("source_id", "in", self.ids), ("state", "!=", "closed")],
            ["source_id"], ["__count"])}
        for s in self:
            s.open_findings = data.get(s.id, 0)


class PharmaCourierRemittanceFlow(models.Model):
    _inherit = "pharma.courier.remittance"

    flow_next = fields.Selection(REMITTANCE_NEXT, string="Next Step", compute="_compute_flow")
    flow_owner = fields.Selection(FLOW_OWNERS, string="Next Step Owner", compute="_compute_flow")
    flow_next_text = fields.Char(string="What to do next", compute="_compute_flow")

    def _flow_owner_map(self):
        return {"post_slip": "finance", "reconcile": "finance", "resolve": "finance"}

    def _flow_next_key(self):
        self.ensure_one()
        if self.state == "cancel":
            return "none"
        if self.state == "draft":
            return "post_slip"
        if not self.run_id:
            return "reconcile"
        return "resolve" if self.open_exceptions else "none"

    @api.depends("state", "run_id", "run_id.open_exceptions")
    def _compute_flow(self):
        labels = dict(self._fields["flow_next"]._description_selection(self.env))
        owners = dict(self._fields["flow_owner"]._description_selection(self.env))
        for r in self:
            key = r._flow_next_key()
            owner = r._flow_owner_map().get(key, "none")
            r.flow_next, r.flow_owner = key, owner
            r.flow_next_text = (_("Nothing further") if key == "none" else
                                _("%(step)s (%(owner)s)", step=labels.get(key, key), owner=owners.get(owner, owner)))
