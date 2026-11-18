from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

REMITTANCE_STATES = [("draft", "Draft"), ("posted", "Posted"), ("cancel", "Cancelled")]
DEDUCTIONS = ("deduction_freight", "deduction_cod_fee", "deduction_wht_income_tax", "deduction_wht_sales_tax",
              "deduction_other")


class PharmaCourierRemittance(models.Model):
    """One payout batch from a courier. What reaches the bank is net of the courier's own deductions, so a batch is
    never simply the sum of what was collected: reconciling it means explaining every deduction.

    Reconciliation is the hub's. This model builds a hub run from its lines, so the batch is matched to the bank credit
    by slip reference, a difference is never forced to zero, and every variance becomes an exception with an owner and
    maker-checker closure."""

    _name = "pharma.courier.remittance"
    _description = "Courier COD Remittance"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(default="/", readonly=True, copy=False)
    courier_id = fields.Many2one("pharma.courier", required=True, index=True, tracking=True)
    slip_ref = fields.Char(string="Slip / Bank Reference", required=True, index=True, tracking=True,
                           help="The courier's batch or transfer reference. It is the key that ties this batch to the "
                                "bank credit.")
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    state = fields.Selection(REMITTANCE_STATES, default="draft", required=True, index=True, tracking=True, copy=False)
    line_ids = fields.One2many("pharma.courier.remittance.line", "remittance_id", string="Lines")
    line_count = fields.Integer(compute="_compute_amounts", store=True)
    amount_gross = fields.Float(string="Gross COD", digits=(16, 2), compute="_compute_amounts", store=True)
    amount_deductions = fields.Float(string="Deductions", digits=(16, 2), compute="_compute_amounts", store=True)
    amount_net = fields.Float(string="Net per Lines", digits=(16, 2), compute="_compute_amounts", store=True)
    bank_amount = fields.Float(string="Received at Bank", digits=(16, 2), tracking=True,
                               help="What actually arrived in the bank for this batch.")
    amount_bank_variance = fields.Float(string="Bank Variance", digits=(16, 2), compute="_compute_amounts", store=True,
                                        help="Received at the bank minus the net the lines add up to.")
    check_deductions = fields.Boolean(
        string="Check Against Authorized", tracking=True,
        help="Tick when Finance holds an authorized deduction amount for this batch (for example from the courier "
             "agreement). The reported deductions are then compared with it.")
    deductions_authorized = fields.Float(string="Authorized Deductions", digits=(16, 2), tracking=True)
    deductions_excess = fields.Float(string="Deductions Above Authorized", digits=(16, 2),
                                     compute="_compute_amounts", store=True)
    run_id = fields.Many2one("pharma.recon.run", readonly=True, copy=False, string="Reconciliation Run")
    run_state = fields.Selection(related="run_id.state", string="Run Status")
    open_exceptions = fields.Integer(related="run_id.open_exceptions", string="Open Exceptions")
    statement_id = fields.Many2one("pharma.courier.statement", readonly=True, copy=False)
    is_demo = fields.Boolean(string="DEMO")

    _slip_uniq = models.Constraint("UNIQUE(courier_id, slip_ref)", "This courier already has a remittance with that slip reference.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("pharma.courier.remittance") or "/"
        return super().create(vals_list)

    @api.depends("line_ids.amount_gross", "line_ids.amount_deductions", "line_ids.amount_net", "bank_amount",
                 "check_deductions", "deductions_authorized")
    def _compute_amounts(self):
        for r in self:
            r.line_count = len(r.line_ids)
            r.amount_gross = sum(r.line_ids.mapped("amount_gross"))
            r.amount_deductions = sum(r.line_ids.mapped("amount_deductions"))
            r.amount_net = sum(r.line_ids.mapped("amount_net"))
            r.amount_bank_variance = (r.bank_amount - r.amount_net) if r.bank_amount else 0.0
            r.deductions_excess = (r.amount_deductions - r.deductions_authorized) if r.check_deductions else 0.0

    @api.constrains("deductions_authorized", "bank_amount")
    def _check_amounts(self):
        for r in self:
            if r.deductions_authorized < 0 or r.bank_amount < 0:
                raise ValidationError(_("Amounts on %s cannot be negative.", r.display_name))

    def write(self, vals):
        locked = {"courier_id", "slip_ref", "date"} & set(vals)
        if locked and any(r.state != "draft" for r in self):
            raise UserError(_("A posted or cancelled remittance cannot change its courier, slip reference or date."))
        if self.filtered("run_id") and {"bank_amount", "check_deductions", "deductions_authorized"} & set(vals):
            raise UserError(_("This remittance is already reconciled. Raise an adjustment through its exceptions instead."))
        return super().write(vals)

    def unlink(self):
        if any(r.state != "draft" for r in self):
            raise UserError(_("Only draft remittances can be deleted. Cancel a posted one instead."))
        return super().unlink()

    # ------------------------------------------------------------------ workflow
    def action_post(self):
        for r in self:
            if r.state != "draft":
                raise UserError(_("%s is not a draft.", r.display_name))
            if not r.line_ids:
                raise UserError(_("%s has no lines to post.", r.display_name))
        self.write({"state": "posted"})
        self.line_ids.shipment_id.action_refresh_ageing()
        return True

    def action_cancel(self):
        for r in self:
            if r.run_id:
                raise UserError(_("%s is already reconciled in %s. Raise an adjustment through its exceptions instead.",
                                  r.display_name, r.run_id.display_name))
        self.write({"state": "cancel"})
        self.line_ids.shipment_id.action_refresh_ageing()
        return True

    def action_draft(self):
        if any(r.state != "cancel" for r in self):
            raise UserError(_("Only a cancelled remittance can go back to draft."))
        self.write({"state": "draft"})
        return True

    def action_reconcile(self):
        """Build a hub run from this batch and match it. One run per batch, once: a difference is never reset, it is
        resolved through its exceptions."""
        if not self.env.user.has_group("pharma_core.group_pharma_finance"):
            raise UserError(_("Only a Finance Controller can reconcile a remittance."))
        Run, Item = self.env["pharma.recon.run"], self.env["pharma.recon.item"]
        for r in self:
            if r.state != "posted":
                raise UserError(_("Post %s before reconciling it.", r.display_name))
            if r.run_id:
                raise UserError(_("%s is already reconciled in %s.", r.display_name, r.run_id.display_name))
            if not r.bank_amount:
                raise UserError(_("Enter the amount received at the bank for %s first.", r.display_name))
            authorized = r.deductions_authorized if r.check_deductions else r.amount_deductions
            run = Run.create({
                "name": f"COD {r.courier_id.code} {r.slip_ref}", "run_type": "cod", "period": r.date.strftime("%Y-%m"),
                "authorized_deductions": authorized, "is_demo": r.is_demo})
            for line in r.line_ids:
                Item.create({
                    "run_id": run.id, "side": "source", "item_ref": line.shipment_id.tracking_number,
                    "batch_ref": r.slip_ref, "amount": line.amount_gross, "item_date": r.date,
                    "source_label": f"{r.courier_id.name} remittance {r.slip_ref}",
                    "raw_event_id": line.raw_event_id.id or False})
            Item.create({
                "run_id": run.id, "side": "bank", "item_ref": r.slip_ref, "amount": r.bank_amount,
                "item_date": r.date, "source_label": "Bank"})
            run.action_match()
            r.line_ids.shipment_id.action_check(run)
            r._check_deductions(run)
            # The hub marks a run 'partial' while exceptions are open. Findings added after its matching must not leave
            # a run that says 'matched' with an open exception on it.
            if run.open_exceptions and run.state == "matched":
                run.state = "partial"
            r.run_id = run
        return True

    def _check_deductions(self, run):
        """Deductions above the authorized amount are a finding, never absorbed."""
        Exc = self.env["pharma.recon.exception"]
        for r in self.filtered("check_deductions"):
            tol = r.courier_id.variance_tolerance or 0.0
            if r.deductions_excess <= tol:
                continue
            key = f"{r.courier_id.code}/{r.slip_ref}/deduction"
            if Exc.search_count([("dedupe_key", "=", key)]):
                continue
            Exc.create({
                "run_id": run.id, "category": "deduction", "dedupe_key": key, "amount": r.deductions_excess,
                "source_model": r._name, "source_id": r.id, "is_demo": r.is_demo,
                "description": _("%(slip)s reports deductions of %(rep).2f against an authorized %(auth).2f: "
                                 "%(ex).2f above what was agreed.", slip=r.slip_ref, rep=r.amount_deductions,
                                 auth=r.deductions_authorized, ex=r.deductions_excess)})

    def action_view_run(self):
        self.ensure_one()
        if not self.run_id:
            raise UserError(_("%s has not been reconciled yet.", self.display_name))
        return {"type": "ir.actions.act_window", "res_model": "pharma.recon.run", "res_id": self.run_id.id,
                "view_mode": "form"}


class PharmaCourierRemittanceLine(models.Model):
    """The share of a payout batch that belongs to one shipment, with its deductions itemised.

    The itemising is the point. The two withholding taxes a courier deducts are credits against the business's own tax
    liability: recoverable receivables, not costs. Folding them into one net figure would lose the credit."""

    _name = "pharma.courier.remittance.line"
    _description = "Courier COD Remittance Line"
    _order = "remittance_id, id"

    remittance_id = fields.Many2one("pharma.courier.remittance", required=True, ondelete="cascade", index=True)
    shipment_id = fields.Many2one("pharma.courier.shipment", required=True, ondelete="restrict", index=True)
    courier_id = fields.Many2one(related="remittance_id.courier_id", store=True, index=True)
    state = fields.Selection(related="remittance_id.state", store=True, index=True)
    date = fields.Date(related="remittance_id.date", store=True, index=True)
    amount_gross = fields.Float(string="COD Remitted (gross)", digits=(16, 2), required=True)
    deduction_freight = fields.Float(string="Freight Deducted", digits=(16, 2))
    deduction_cod_fee = fields.Float(string="COD Fee Deducted", digits=(16, 2))
    deduction_wht_income_tax = fields.Float(
        string="Withholding Income Tax", digits=(16, 2),
        help="Withheld by the courier against the business's income tax. Recoverable: a receivable, not a cost.")
    deduction_wht_sales_tax = fields.Float(
        string="Withholding Sales Tax", digits=(16, 2),
        help="Withheld by the courier against the business's sales tax. Recoverable.")
    deduction_other = fields.Float(string="Other Deductions", digits=(16, 2))
    amount_deductions = fields.Float(string="Total Deductions", digits=(16, 2), compute="_compute_amounts", store=True)
    amount_net = fields.Float(string="Net", digits=(16, 2), compute="_compute_amounts", store=True)
    raw_event_id = fields.Many2one("pharma.raw.event", readonly=True)
    note = fields.Char()

    _remittance_shipment_uniq = models.Constraint(
        "UNIQUE(remittance_id, shipment_id)", "A shipment can appear only once in a remittance.")

    @api.depends("amount_gross", *DEDUCTIONS)
    def _compute_amounts(self):
        for l in self:
            l.amount_deductions = sum(l[f] for f in DEDUCTIONS)
            l.amount_net = l.amount_gross - l.amount_deductions

    @api.constrains("amount_gross", *DEDUCTIONS)
    def _check_amounts(self):
        for l in self:
            if l.amount_gross < 0 or any(l[f] < 0 for f in DEDUCTIONS):
                raise ValidationError(_("Amounts cannot be negative (%s).", l.shipment_id.display_name))
            if l.amount_deductions > l.amount_gross + 0.005:
                raise ValidationError(_("Deductions exceed the gross amount for %s.", l.shipment_id.display_name))

    @api.constrains("shipment_id", "remittance_id")
    def _check_courier(self):
        for l in self:
            if l.shipment_id.courier_id != l.remittance_id.courier_id:
                raise ValidationError(_("%s belongs to another courier than this remittance.", l.shipment_id.display_name))

    def _check_parent_draft(self):
        if any(l.remittance_id.state != "draft" for l in self):
            raise UserError(_("Lines can only change while the remittance is a draft."))

    @api.model_create_multi
    def create(self, vals_list):
        remittances = self.env["pharma.courier.remittance"].browse([v["remittance_id"] for v in vals_list if v.get("remittance_id")])
        if any(r.state != "draft" for r in remittances):
            raise UserError(_("Lines can only be added while the remittance is a draft."))
        return super().create(vals_list)

    def write(self, vals):
        if set(vals) - {"raw_event_id", "note"}:
            self._check_parent_draft()
        return super().write(vals)

    def unlink(self):
        self._check_parent_draft()
        return super().unlink()
