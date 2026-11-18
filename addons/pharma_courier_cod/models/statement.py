import json

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from .remittance import DEDUCTIONS
from .shipment import map_status

STATEMENT_TYPES = [
    ("shipments", "Shipment / delivery report"),
    ("cod_remittance", "COD remittance slip"),
]
STATEMENT_STATES = [("draft", "Draft"), ("validated", "Validated"), ("built", "Built"), ("cancel", "Cancelled")]
LINE_STATES = [("pending", "Not validated"), ("valid", "Valid"), ("error", "Error"), ("built", "Built")]


class PharmaCourierStatement(models.Model):
    """One courier file, on its way to becoming documents.

    The upload itself is Odoo's own import screen: it reads CSV or XLSX, maps the courier's column names onto the staging
    fields below, and remembers the mapping for next time. Nothing here re-implements any of that.

    What Odoo cannot know is whether a row makes sense here: whether the tracking number exists, whether the courier is
    remitting more than it ever collected, whether a slip was already booked. That is checked row by row on staging
    lines before anything is built, because importing straight onto real documents would let a bad row land in the
    ledger. Every row that is built is first archived, unchanged, in the immutable raw-event log."""

    _name = "pharma.courier.statement"
    _description = "Courier Statement Upload"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(default="/", readonly=True, copy=False)
    courier_id = fields.Many2one("pharma.courier", required=True, index=True, tracking=True)
    statement_type = fields.Selection(STATEMENT_TYPES, required=True, default="cod_remittance", tracking=True)
    state = fields.Selection(STATEMENT_STATES, default="draft", required=True, index=True, tracking=True, copy=False)
    slip_ref = fields.Char(string="Slip / Bank Reference", help="Remittance slips only: the courier's batch reference.")
    remittance_date = fields.Date(help="Remittance slips only: the date on the slip.")
    bank_amount = fields.Float(string="Received at Bank", digits=(16, 2),
                               help="Remittance slips only: what arrived in the bank. Can be filled in later on the remittance.")
    line_ids = fields.One2many("pharma.courier.statement.line", "statement_id", string="Rows")
    line_count = fields.Integer(compute="_compute_counts")
    error_count = fields.Integer(compute="_compute_counts")
    remittance_id = fields.Many2one("pharma.courier.remittance", readonly=True, copy=False)
    shipments_created = fields.Integer(readonly=True, copy=False)
    shipments_updated = fields.Integer(readonly=True, copy=False)
    is_demo = fields.Boolean(string="DEMO")

    @api.depends("line_ids.state")
    def _compute_counts(self):
        for st in self:
            st.line_count = len(st.line_ids)
            st.error_count = len(st.line_ids.filtered(lambda l: l.state == "error"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("pharma.courier.statement") or "/"
        return super().create(vals_list)

    def unlink(self):
        if any(st.state not in ("draft", "cancel") for st in self):
            raise UserError(_("Only a draft or cancelled statement can be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------ upload
    def action_upload_file(self):
        """Open Odoo's own import screen on this statement's rows, with the statement already filled in."""
        self.ensure_one()
        if self.state not in ("draft", "validated"):
            raise UserError(_("%s is %s. Upload the file into a new statement.", self.display_name, self.state))
        return {"type": "ir.actions.client", "tag": "import",
                "params": {"active_model": "pharma.courier.statement.line",
                           "context": {"default_statement_id": self.id}}}

    def action_view_rows(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Rows"), "res_model": "pharma.courier.statement.line",
                "view_mode": "list,form", "domain": [("statement_id", "=", self.id)],
                "context": {"default_statement_id": self.id}}

    # ------------------------------------------------------------------ validate
    def _header_error(self):
        self.ensure_one()
        if self.statement_type == "cod_remittance":
            if not self.slip_ref:
                return _("Enter the slip or bank reference before validating.")
            if not self.remittance_date:
                return _("Enter the date on the slip before validating.")
            existing = self.env["pharma.courier.remittance"].search(
                [("courier_id", "=", self.courier_id.id), ("slip_ref", "=", self.slip_ref)], limit=1)
            if existing:
                return _("%(c)s already has remittance %(r)s with slip reference %(s)s.",
                         c=self.courier_id.name, r=existing.name, s=self.slip_ref)
        return None

    def action_validate(self):
        for st in self:
            if st.state not in ("draft", "validated"):
                raise UserError(_("%s is %s and cannot be validated.", st.display_name, st.state))
            error = st._header_error()
            if error:
                raise UserError(error)
            st.line_ids.action_validate()
            st.state = "validated" if (st.line_count and not st.error_count) else "draft"
        return True

    # ------------------------------------------------------------------ build
    def _archive(self, line):
        """Archive one row exactly as received. Event ids are scoped to the statement, so a courier re-sending a changed
        status in a later file is a new event, never a conflict, while processing one statement twice is a no-op."""
        self.ensure_one()
        payload = json.dumps({
            "statement": self.name, "courier": self.courier_id.code, "type": self.statement_type,
            "reference": line.reference, "order_ref": line.order_ref, "status": line.provider_status,
            "date_booked": str(line.date_booked or ""), "date_delivered": str(line.date_delivered or ""),
            "cod_declared": line.cod_declared, "cod_collected": line.cod_collected, "gross": line.amount_gross,
            **{f: line[f] for f in DEDUCTIONS}}, sort_keys=True)
        rec, _outcome = self.env["pharma.raw.event"].ingest(
            "courier", f"{self.courier_id.code}:{self.name}:{line.reference}", payload, is_demo=self.is_demo)
        return rec

    def action_build(self):
        if not self.env.user.has_group("pharma_core.group_pharma_finance"):
            raise UserError(_("Only a Finance Controller can build a statement."))
        for st in self:
            if st.state != "validated":
                raise UserError(_("Validate %s, with no errors, before building it.", st.display_name))
            if st.statement_type == "shipments":
                st._build_shipments()
            else:
                st._build_remittance()
            st.line_ids.filtered(lambda l: l.state == "valid").write({"state": "built"})
            st.state = "built"
        return True

    def _build_shipments(self):
        self.ensure_one()
        Shipment = self.env["pharma.courier.shipment"]
        created = updated = 0
        built = Shipment
        for line in self.line_ids.filtered(lambda l: l.state == "valid"):
            event = self._archive(line)
            # Never blank what the file leaves empty: a later, thinner report must not erase earlier facts.
            vals = {k: v for k, v in {
                "order_ref": line.order_ref, "consignee_name": line.consignee_name,
                "destination_city": line.destination_city, "provider_status": line.provider_status,
                "date_booked": line.date_booked, "date_delivered": line.date_delivered,
                "cod_declared": line.cod_declared, "cod_collected": line.cod_collected}.items() if v}
            if line.provider_status:
                vals["state"] = map_status(line.provider_status)
            vals["raw_event_id"] = event.id
            shipment = Shipment.search(
                [("courier_id", "=", self.courier_id.id), ("tracking_number", "=", line.reference)], limit=1)
            if shipment:
                shipment.write(vals)
                updated += 1
            else:
                shipment = Shipment.create(dict(
                    vals, courier_id=self.courier_id.id, tracking_number=line.reference,
                    payment_mode="cod" if line.cod_declared else "prepaid", is_demo=self.is_demo))
                created += 1
            line.shipment_id = shipment
            built |= shipment
        self.write({"shipments_created": created, "shipments_updated": updated})
        built.action_check()

    def _build_remittance(self):
        self.ensure_one()
        lines = []
        for line in self.line_ids.filtered(lambda l: l.state == "valid"):
            event = self._archive(line)
            line.raw_event_id = event
            lines.append(Command.create({
                "shipment_id": line.shipment_id.id, "amount_gross": line.amount_gross, "raw_event_id": event.id,
                **{f: line[f] for f in DEDUCTIONS}}))
        self.remittance_id = self.env["pharma.courier.remittance"].create({
            "courier_id": self.courier_id.id, "slip_ref": self.slip_ref, "date": self.remittance_date,
            "bank_amount": self.bank_amount, "statement_id": self.id, "is_demo": self.is_demo, "line_ids": lines})

    def action_view_result(self):
        self.ensure_one()
        if self.remittance_id:
            return {"type": "ir.actions.act_window", "res_model": "pharma.courier.remittance",
                    "res_id": self.remittance_id.id, "view_mode": "form"}
        if self.state == "built":
            return {"type": "ir.actions.act_window", "name": _("Shipments"), "res_model": "pharma.courier.shipment",
                    "view_mode": "list,form", "domain": [("id", "in", self.line_ids.shipment_id.ids)]}
        raise UserError(_("%s has not been built yet.", self.display_name))

    def action_cancel(self):
        if any(st.state == "built" for st in self):
            raise UserError(_("A built statement cannot be cancelled. Cancel the remittance it produced instead."))
        self.write({"state": "cancel"})
        return True


class PharmaCourierStatementLine(models.Model):
    """One row of the courier's file, before it is anything.

    One flat model for both statement types: a delivery report and a remittance slip are both a tracking number plus
    some amounts. The fields are named for what they mean to us, and the labels are the column headings a courier file is
    easiest to map from; whoever uploads maps them once and Odoo remembers."""

    _name = "pharma.courier.statement.line"
    _description = "Courier Statement Row"
    _order = "statement_id, id"
    _rec_name = "reference"

    statement_id = fields.Many2one("pharma.courier.statement", required=True, ondelete="cascade", index=True)
    courier_id = fields.Many2one(related="statement_id.courier_id", store=True, index=True)
    statement_type = fields.Selection(related="statement_id.statement_type", store=True)
    reference = fields.Char(string="Tracking Number", index=True)
    order_ref = fields.Char(string="Order Reference")
    consignee_name = fields.Char(string="Consignee")
    destination_city = fields.Char(string="Destination City")
    provider_status = fields.Char(string="Status")
    date_booked = fields.Date(string="Booked Date")
    date_delivered = fields.Date(string="Delivered Date")
    cod_declared = fields.Float(string="COD Declared", digits=(16, 2))
    cod_collected = fields.Float(string="COD Collected", digits=(16, 2))
    amount_gross = fields.Float(string="COD Remitted (Gross)", digits=(16, 2))
    deduction_freight = fields.Float(string="Freight Deducted", digits=(16, 2))
    deduction_cod_fee = fields.Float(string="COD Fee Deducted", digits=(16, 2))
    deduction_wht_income_tax = fields.Float(string="Withholding Income Tax", digits=(16, 2))
    deduction_wht_sales_tax = fields.Float(string="Withholding Sales Tax", digits=(16, 2))
    deduction_other = fields.Float(string="Other Deductions", digits=(16, 2))
    amount_deductions = fields.Float(compute="_compute_amounts", store=True, digits=(16, 2))
    amount_net = fields.Float(compute="_compute_amounts", store=True, digits=(16, 2))
    shipment_id = fields.Many2one("pharma.courier.shipment", readonly=True, index=True)
    raw_event_id = fields.Many2one("pharma.raw.event", readonly=True)
    state = fields.Selection(LINE_STATES, default="pending", required=True, index=True)
    error_message = fields.Char(readonly=True, copy=False)

    @api.depends("amount_gross", *DEDUCTIONS)
    def _compute_amounts(self):
        for l in self:
            l.amount_deductions = sum(l[f] for f in DEDUCTIONS)
            l.amount_net = l.amount_gross - l.amount_deductions

    def _find_shipment(self):
        self.ensure_one()
        return self.env["pharma.courier.shipment"].search(
            [("courier_id", "=", self.courier_id.id), ("tracking_number", "=", (self.reference or "").strip())], limit=1)

    def _validation_error(self):
        """The first thing wrong with this row, or None."""
        self.ensure_one()
        if not (self.reference or "").strip():
            return _("No tracking number.")
        amounts = [self.cod_declared, self.cod_collected, self.amount_gross, *[self[f] for f in DEDUCTIONS]]
        if any(a < 0 for a in amounts):
            return _("A negative amount.")
        if self.statement_type == "shipments":
            if self.date_booked and self.date_delivered and self.date_delivered < self.date_booked:
                return _("Delivered %(d)s, before it was booked on %(b)s.", d=self.date_delivered, b=self.date_booked)
            if map_status(self.provider_status) == "delivered" and not self.date_delivered:
                return _("Marked delivered but there is no delivery date, which the COD ageing needs.")
            return None
        # remittance slip
        if not self.amount_gross:
            return _("No remitted amount.")
        if self.amount_deductions > self.amount_gross + 0.005:
            return _("Deductions of %(d).2f exceed the %(g).2f remitted.", d=self.amount_deductions, g=self.amount_gross)
        shipment = self._find_shipment()
        if not shipment:
            return _("No shipment with tracking number %(t)s for %(c)s. Upload the delivery report first.",
                     t=self.reference, c=self.courier_id.name)
        self.shipment_id = shipment
        if shipment.payment_mode != "cod":
            return _("%s is not a COD shipment.", shipment.display_name)
        if shipment.state != "delivered":
            return _("%(s)s is %(st)s, not delivered, so there is no COD to remit.",
                     s=shipment.display_name, st=shipment.state)
        tol = self.courier_id.variance_tolerance or 0.0
        if shipment.cod_remitted + self.amount_gross > shipment.cod_collected + tol:
            return _("Remits %(r).2f but only %(c).2f was collected and %(a).2f is already accounted for.",
                     r=self.amount_gross, c=shipment.cod_collected, a=shipment.cod_remitted)
        return None

    def action_validate(self):
        seen = set()
        for line in self:
            if line.state == "built":
                continue
            error = line._validation_error()
            key = (line.reference or "").strip()
            if not error and key:
                if key in seen:
                    error = _("Duplicated within this statement.")
                seen.add(key)
            line.write({"state": "error" if error else "valid", "error_message": error or False})
        return True
