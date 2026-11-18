from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

SHIPMENT_STATES = [
    ("booked", "Booked"),
    ("in_transit", "In transit"),
    ("delivered", "Delivered"),
    ("returned", "Returned"),
    ("cancelled", "Cancelled"),
]
PAYMENT_MODES = [("cod", "Cash on delivery"), ("prepaid", "Prepaid")]
COD_STATES = [
    ("none", "Not COD / not expected"),
    ("pending", "Not yet delivered"),
    ("uncollected", "Delivered, nothing collected"),
    ("outstanding", "Collected, not remitted"),
    ("partial", "Partly remitted"),
    ("remitted", "Remitted"),
]
# Buckets are 0-7, 8-15, 16-30 and 31+ days: the source requirement wrote "8-15" and "15-30", which overlap at day 15.
AGEING_BUCKETS = [
    ("b_0_7", "0-7 days"),
    ("b_8_15", "8-15 days"),
    ("b_16_30", "16-30 days"),
    ("b_31_plus", "31+ days"),
]


def map_status(raw):
    """Map a courier's own status text to our state. Order matters: 'Undelivered' and 'Out for delivery' both contain
    'deliver' and must not be read as delivered."""
    s = (raw or "").strip().lower()
    if not s:
        return "booked"
    if "return" in s or "rto" == s:
        return "returned"
    if "cancel" in s:
        return "cancelled"
    if any(k in s for k in ("undeliver", "not deliver", "attempt", "fail", "out for", "transit", "dispatch",
                            "pick", "arrived", "hub", "re-schedul", "reschedul")):
        return "in_transit"
    if "deliver" in s:
        return "delivered"
    return "booked"


class PharmaCourierShipment(models.Model):
    """One parcel. The anchor of the COD ledger.

    Deliberately not a stock picking: it must exist when the courier reports a parcel we have no order for, and that
    gap is itself a finding. COD is followed in three steps: declared at booking, collected at the door, remitted by the
    courier. The two gaps between them have different causes, so they raise different exceptions: a customer who paid
    less is a loss to recover, a courier that accounted for less is a claim against the courier."""

    _name = "pharma.courier.shipment"
    _description = "Courier Shipment"
    _inherit = ["mail.thread"]
    _order = "date_booked desc, id desc"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    courier_id = fields.Many2one("pharma.courier", required=True, index=True, tracking=True)
    tracking_number = fields.Char(required=True, index=True, tracking=True)
    order_ref = fields.Char(string="Order Reference", index=True, tracking=True,
                            help="Our order number as the courier knows it. Matched to a sale order reference or number.")
    sale_order_id = fields.Many2one("sale.order", index=True, tracking=True)
    order_matched = fields.Boolean(compute="_compute_order_matched", store=True, index=True)
    consignee_name = fields.Char()
    destination_city = fields.Char()
    state = fields.Selection(SHIPMENT_STATES, default="booked", required=True, index=True, tracking=True)
    provider_status = fields.Char(string="Courier Status", help="The courier's own status text, before mapping.")
    payment_mode = fields.Selection(PAYMENT_MODES, default="cod", required=True, index=True)
    date_booked = fields.Date(index=True, tracking=True)
    date_delivered = fields.Date(index=True, tracking=True,
                                 help="The courier's clock for remitting COD starts here, not at booking.")
    cod_declared = fields.Float(string="COD Declared", digits=(16, 2), tracking=True)
    cod_collected = fields.Float(string="COD Collected", digits=(16, 2), tracking=True)
    line_ids = fields.One2many("pharma.courier.remittance.line", "shipment_id", string="Remittance Lines")
    cod_remitted = fields.Float(string="Remitted (gross)", digits=(16, 2), compute="_compute_remitted", store=True)
    cod_deductions = fields.Float(string="Deductions", digits=(16, 2), compute="_compute_remitted", store=True)
    cod_net_received = fields.Float(string="Net Received", digits=(16, 2), compute="_compute_remitted", store=True)
    cod_outstanding = fields.Float(string="Outstanding", digits=(16, 2), compute="_compute_cod", store=True)
    cod_collection_variance = fields.Float(
        string="Collection Variance", digits=(16, 2), compute="_compute_cod", store=True,
        help="Collected minus declared. Negative means the customer paid less than declared.")
    cod_remittance_variance = fields.Float(
        string="Remittance Variance", digits=(16, 2), compute="_compute_cod", store=True,
        help="Remitted gross minus collected. Negative means the courier accounted for less than it collected.")
    cod_state = fields.Selection(COD_STATES, compute="_compute_cod", store=True, index=True, string="COD Status")
    cod_days_outstanding = fields.Integer(compute="_compute_ageing", store=True, string="Days Outstanding")
    cod_ageing_bucket = fields.Selection(AGEING_BUCKETS, compute="_compute_ageing", store=True, index=True,
                                         string="Ageing")
    cod_is_overdue = fields.Boolean(compute="_compute_ageing", store=True, index=True, string="Overdue")
    raw_event_id = fields.Many2one("pharma.raw.event", readonly=True, string="Source Event",
                                   help="The archived courier row this record was last built from.")
    is_demo = fields.Boolean(string="DEMO")

    _courier_tracking_uniq = models.Constraint(
        "UNIQUE(courier_id, tracking_number)", "This courier already has a shipment with that tracking number.")

    # ------------------------------------------------------------------ computes
    @api.depends("courier_id.code", "tracking_number")
    def _compute_name(self):
        for s in self:
            s.name = f"{s.courier_id.code or '?'}/{s.tracking_number or '?'}"

    @api.depends("sale_order_id")
    def _compute_order_matched(self):
        for s in self:
            s.order_matched = bool(s.sale_order_id)

    @api.depends("line_ids.amount_gross", "line_ids.amount_deductions", "line_ids.amount_net", "line_ids.state")
    def _compute_remitted(self):
        for s in self:
            lines = s.line_ids.filtered(lambda l: l.state == "posted")
            s.cod_remitted = sum(lines.mapped("amount_gross"))
            s.cod_deductions = sum(lines.mapped("amount_deductions"))
            s.cod_net_received = sum(lines.mapped("amount_net"))

    @api.depends("payment_mode", "state", "cod_declared", "cod_collected", "cod_remitted",
                 "courier_id.variance_tolerance")
    def _compute_cod(self):
        for s in self:
            is_cod = s.payment_mode == "cod"
            delivered = s.state == "delivered"
            tol = s.courier_id.variance_tolerance or 0.0
            s.cod_collection_variance = (s.cod_collected - s.cod_declared) if (is_cod and delivered) else 0.0
            s.cod_remittance_variance = (s.cod_remitted - s.cod_collected) if is_cod else 0.0
            s.cod_outstanding = max(s.cod_collected - s.cod_remitted, 0.0) if (is_cod and delivered) else 0.0
            if not is_cod or s.state in ("returned", "cancelled"):
                s.cod_state = "none"
            elif not delivered:
                s.cod_state = "pending"
            elif s.cod_collected <= 0:
                s.cod_state = "uncollected"
            elif s.cod_remitted <= 0:
                s.cod_state = "outstanding"
            elif s.cod_remitted + tol < s.cod_collected:
                s.cod_state = "partial"
            else:
                s.cod_state = "remitted"

    @api.depends("cod_outstanding", "cod_state", "date_delivered", "courier_id.remittance_cycle_days")
    def _compute_ageing(self):
        today = fields.Date.context_today(self)
        for s in self:
            s._apply_ageing(today)

    def _apply_ageing(self, today):
        """Age outstanding COD from the delivery date. Dates, not timestamps: a courier reports a delivery day, and a
        day compared with a day cannot be a day out because of a time zone."""
        self.ensure_one()
        if not (self.cod_outstanding > 0 and self.date_delivered):
            self.cod_days_outstanding = 0
            self.cod_ageing_bucket = False
            self.cod_is_overdue = False
            return
        days = max((today - self.date_delivered).days, 0)
        self.cod_days_outstanding = days
        self.cod_is_overdue = days > (self.courier_id.remittance_cycle_days or 14)
        if days <= 7:
            self.cod_ageing_bucket = "b_0_7"
        elif days <= 15:
            self.cod_ageing_bucket = "b_8_15"
        elif days <= 30:
            self.cod_ageing_bucket = "b_16_30"
        else:
            self.cod_ageing_bucket = "b_31_plus"

    @api.constrains("cod_declared", "cod_collected", "date_booked", "date_delivered")
    def _check_values(self):
        for s in self:
            if s.cod_declared < 0 or s.cod_collected < 0:
                raise ValidationError(_("COD amounts cannot be negative (%s).", s.name))
            if s.date_booked and s.date_delivered and s.date_delivered < s.date_booked:
                raise ValidationError(_("%s is delivered before it was booked.", s.name))

    # ------------------------------------------------------------------ order link
    def _link_order(self):
        """Match the courier's order reference to a sale order by customer reference or number. Optional by design."""
        # Superuser search: whoever loads a courier file (Finance) needs no sales rights to have the match made.
        SO = self.env["sale.order"].sudo()
        for s in self.filtered(lambda s: s.order_ref and not s.sale_order_id):
            so = SO.search(["|", ("client_order_ref", "=", s.order_ref), ("name", "=", s.order_ref)], limit=1)
            if so:
                s.sale_order_id = so

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._link_order()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "order_ref" in vals:
            self._link_order()
        return res

    # ------------------------------------------------------------------ ageing refresh
    def action_refresh_ageing(self):
        """Recompute ageing for these shipments against today. Ageing depends on the date, not on any field, so it
        cannot refresh itself; the daily job and the list action call this."""
        for fname in ("cod_days_outstanding", "cod_ageing_bucket", "cod_is_overdue"):
            self.env.add_to_compute(self._fields[fname], self)
        self.env.flush_all()
        return True

    @api.model
    def action_refresh_all(self):
        """Refresh ageing for every delivered COD shipment and raise the exceptions that follow. Returns a
        notification so it can be bound to a list action."""
        if not self.env.su and not self.env.user.has_group("pharma_core.group_pharma_finance"):
            raise UserError(_("Only a Finance Controller can refresh COD ageing and raise exceptions."))
        recs = self.search([("payment_mode", "=", "cod"), ("state", "in", ("delivered", "returned"))])
        recs.action_refresh_ageing()
        raised = recs.action_check()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("COD refreshed"), "type": "success", "sticky": False,
                           "message": _("%(n)s shipments checked, %(r)s new exceptions raised.",
                                        n=len(recs), r=raised)}}

    @api.model
    def _cron_daily(self):
        self.action_refresh_all()

    # ------------------------------------------------------------------ exceptions
    def _exception_run(self, courier, kind, is_demo):
        """A standing monitoring run per courier and month, so findings that belong to no remittance still land in the
        hub's queue."""
        Run = self.env["pharma.recon.run"]
        period = fields.Date.context_today(self).strftime("%Y-%m")
        name = f"COD {kind} {courier.code} {period}"
        run = Run.search([("name", "=", name)], limit=1)
        return run or Run.create({"name": name, "run_type": "cod", "period": period, "is_demo": is_demo})

    def _raise(self, category, description, amount, run=None):
        """Raise one exception in the hub queue. Idempotent on (courier, tracking, category): a finding that exists,
        open or resolved, is never raised again."""
        self.ensure_one()
        Exc = self.env["pharma.recon.exception"]
        key = f"{self.courier_id.code}/{self.tracking_number}/{category}"
        if Exc.search_count([("dedupe_key", "=", key)]):
            return False
        run = run or self._exception_run(self.courier_id, "monitoring", self.is_demo)
        Exc.create({"run_id": run.id, "description": description, "amount": amount, "category": category,
                    "dedupe_key": key, "source_model": self._name, "source_id": self.id, "is_demo": self.is_demo})
        return True

    def action_check(self, run=None):
        """Raise the exceptions these shipments warrant. Returns how many were newly raised."""
        raised = 0
        for s in self:
            tol = s.courier_id.variance_tolerance or 0.0
            trk = s.tracking_number
            if s.payment_mode == "cod" and s.state == "delivered" and s.cod_collection_variance < -tol:
                raised += s._raise(
                    "collection",
                    _("Declared %(d).2f but collected %(c).2f on %(t)s: the customer paid %(g).2f less.",
                      d=s.cod_declared, c=s.cod_collected, t=trk, g=abs(s.cod_collection_variance)),
                    abs(s.cod_collection_variance), run)
            if s.payment_mode == "cod" and s.cod_remitted and s.cod_remittance_variance < -tol:
                raised += s._raise(
                    "remittance",
                    _("Collected %(c).2f on %(t)s but the courier accounted for %(r).2f, a shortfall of %(g).2f.",
                      c=s.cod_collected, t=trk, r=s.cod_remitted, g=abs(s.cod_remittance_variance)),
                    abs(s.cod_remittance_variance), run)
            if s.cod_is_overdue:
                raised += s._raise(
                    "overdue",
                    _("%(a).2f collected on %(t)s has been outstanding %(n)s days, beyond the %(cy)s-day cycle.",
                      a=s.cod_outstanding, t=trk, n=s.cod_days_outstanding, cy=s.courier_id.remittance_cycle_days),
                    s.cod_outstanding, run)
            if s.payment_mode == "cod" and s.state == "returned" and s.cod_collected > 0:
                raised += s._raise(
                    "returned_cod",
                    _("%(a).2f of COD was collected on %(t)s, which came back as a return.", a=s.cod_collected, t=trk),
                    s.cod_collected, run)
            if not s.sale_order_id and s.state != "cancelled":
                raised += s._raise(
                    "intake",
                    _("The courier reports %(t)s for order reference '%(o)s', but there is no matching sale order.",
                      t=trk, o=s.order_ref or "-"), 0.0, run)
        return raised
