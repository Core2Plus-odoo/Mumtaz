from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

RUN_TYPES = [("cod", "R03 COD vs courier vs bank"), ("gateway", "R04 Gateway vs payout vs bank"),
             ("bank", "R05 Bank vs ledger"), ("partner_stock", "R07 Distribution Partner stock"),
             ("other", "Other")]
RUN_STATES = [("imported", "Imported"), ("validated", "Validated"), ("matched", "Matched"),
              ("partial", "Partial"), ("pending", "Pending"), ("disputed", "Disputed"),
              ("approved", "Approved"), ("closed", "Closed")]


class PharmaReconRun(models.Model):
    _name = "pharma.recon.run"
    _description = "Reconciliation Run"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(required=True, tracking=True)
    run_type = fields.Selection(RUN_TYPES, required=True, default="cod")
    period = fields.Char(help="e.g. 2026-11")
    state = fields.Selection(RUN_STATES, default="imported", tracking=True)
    date_window_days = fields.Integer(default=3, help="Amount+date fallback window (low confidence only).")
    authorized_deductions = fields.Float(digits=(16, 2), help="Contractually authorized deductions (courier / gateway fees).")
    item_ids = fields.One2many("pharma.recon.item", "run_id")
    exception_ids = fields.One2many("pharma.recon.exception", "run_id")
    stock_line_ids = fields.One2many("pharma.partner.stock.line", "run_id")
    source_total = fields.Float(compute="_compute_totals", digits=(16, 2))
    bank_total = fields.Float(compute="_compute_totals", digits=(16, 2))
    expected_bank = fields.Float(compute="_compute_totals", digits=(16, 2))
    variance = fields.Float(compute="_compute_totals", digits=(16, 2))
    open_exceptions = fields.Integer(compute="_compute_totals")
    is_demo = fields.Boolean(string="DEMO")

    @api.depends("item_ids.amount", "item_ids.side", "authorized_deductions", "exception_ids.state")
    def _compute_totals(self):
        for r in self:
            src = sum(r.item_ids.filtered(lambda i: i.side == "source").mapped("amount"))
            bank = sum(r.item_ids.filtered(lambda i: i.side == "bank").mapped("amount"))
            r.source_total, r.bank_total = src, bank
            r.expected_bank = src - r.authorized_deductions
            r.variance = bank - r.expected_bank if bank else 0.0
            r.open_exceptions = len(r.exception_ids.filtered(lambda e: e.state != "closed"))

    def _raise_exc(self, desc, item=None, amount=0.0):
        self.env["pharma.recon.exception"].create({
            "run_id": self.id, "description": desc, "amount": amount,
            "bank_item_id": item.id if item else False, "is_demo": self.is_demo})

    def action_match(self):
        """Exact ref > one-to-many batch > unique amount+date (flagged LOW CONFIDENCE).
        Ambiguous / unmatched => exception. Variances are never adjusted."""
        if not self.env.user.has_group("pharma_core.group_pharma_finance"):
            raise UserError("Only a Finance Controller can run matching.")
        for run in self:
            Item = self.env["pharma.recon.item"]
            used = set()
            src_all = run.item_ids.filtered(lambda i: i.side == "source" and i.state == "pending")
            for b in run.item_ids.filtered(lambda i: i.side == "bank" and i.state == "pending"):
                exact = src_all.filtered(lambda s: s.id not in used and b.item_ref and s.item_ref == b.item_ref)
                if len(exact) == 1:
                    used.add(exact.id)
                    if abs(exact.amount - b.amount) < 0.005:
                        (exact | b).write({"state": "matched", "method": "exact_ref"})
                        exact.matched_bank_id = b
                    else:
                        (exact | b).write({"state": "exception"})
                        run._raise_exc(f"Reference matches but amount differs by {b.amount - exact.amount:,.2f}",
                                       b, b.amount - exact.amount)
                    continue
                if len(exact) > 1:
                    b.state = "exception"
                    run._raise_exc("Reference matches multiple source items", b)
                    continue
                batch = src_all.filtered(lambda s: s.id not in used and b.item_ref and s.batch_ref == b.item_ref)
                if batch:
                    used.update(batch.ids)
                    # One run = one settlement: the bank credit is the gross batch less the
                    # contractually authorized deductions (courier / gateway fees).
                    gross = sum(batch.mapped("amount"))
                    tot = gross - run.authorized_deductions
                    if abs(tot - b.amount) < 0.005:
                        (batch | b).write({"state": "matched", "method": "one_to_many_batch"})
                        batch.write({"matched_bank_id": b.id})
                    else:
                        (batch | b).write({"state": "exception"})
                        run._raise_exc(
                            f"Batch gross {gross:,.2f} less authorized deductions "
                            f"{run.authorized_deductions:,.2f} = expected {tot:,.2f} vs bank {b.amount:,.2f}: "
                            f"variance {b.amount - tot:,.2f}. Investigate; no auto-adjustment.", b, b.amount - tot)
                    continue
                win = timedelta(days=run.date_window_days)
                cands = src_all.filtered(lambda s: s.id not in used and abs(s.amount - b.amount) < 0.005
                                         and s.item_date and b.item_date and abs(s.item_date - b.item_date) <= win)
                if len(cands) == 1:
                    used.add(cands.id)
                    (cands | b).write({"state": "matched", "method": "amount_date_LOW_CONFIDENCE"})
                    cands.matched_bank_id = b
                elif len(cands) > 1:
                    b.state = "exception"
                    run._raise_exc("Ambiguous: multiple amount/date candidates; amount-only auto-match refused", b)
                else:
                    b.state = "exception"
                    run._raise_exc("Unidentified bank item", b, b.amount)
            if run.run_type in ("cod", "gateway") and run.item_ids.filtered(lambda i: i.side == "bank") \
                    and abs(run.variance) >= 0.005 and not run.exception_ids:
                run._raise_exc(
                    f"Settlement variance {run.variance:,.2f}: expected {run.expected_bank:,.2f}, "
                    f"actual {run.bank_total:,.2f}. Investigate; no auto-adjustment.", None, run.variance)
            pend = run.item_ids.filtered(lambda i: i.state == "pending")
            run.state = ("pending" if pend else "partial" if run.open_exceptions else "matched")
            if run.open_exceptions:
                run.state = "partial"
        return True


class PharmaReconItem(models.Model):
    _name = "pharma.recon.item"
    _description = "Reconciliation Item"
    _order = "item_date, id"

    run_id = fields.Many2one("pharma.recon.run", required=True, ondelete="cascade", index=True)
    side = fields.Selection([("source", "Source (courier/gateway/ledger)"), ("bank", "Bank")], required=True)
    item_ref = fields.Char(string="Reference")
    batch_ref = fields.Char(string="Batch Ref")
    amount = fields.Float(digits=(16, 2), required=True)
    item_date = fields.Date()
    source_label = fields.Char(string="Source")
    raw_event_id = fields.Many2one("pharma.raw.event", string="Source Payload")
    state = fields.Selection([("pending", "Pending"), ("matched", "Matched"), ("exception", "Exception")],
                             default="pending")
    method = fields.Char()
    matched_bank_id = fields.Many2one("pharma.recon.item")


class PharmaReconException(models.Model):
    _name = "pharma.recon.exception"
    _description = "Reconciliation Exception"
    _inherit = ["mail.thread"]
    _order = "id desc"

    run_id = fields.Many2one("pharma.recon.run", required=True, ondelete="cascade", index=True)
    bank_item_id = fields.Many2one("pharma.recon.item")
    description = fields.Char(required=True)
    amount = fields.Float(digits=(16, 2))
    owner_id = fields.Many2one("res.users", string="Owner", tracking=True)
    state = fields.Selection([("open", "Open"), ("investigating", "Investigating"),
                              ("pending_approval", "Pending approval"), ("closed", "Closed")],
                             default="open", tracking=True)
    resolution = fields.Selection([("explained", "Explained / timing"), ("matched_manual", "Matched manually"),
                                   ("write_off", "Write-off (approved)")])
    note = fields.Text(string="Resolution note")
    proposed_by = fields.Many2one("res.users", readonly=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    is_demo = fields.Boolean(string="DEMO")

    def action_assign_to_me(self):
        self.write({"owner_id": self.env.user.id, "state": "investigating"})

    def action_propose_close(self):
        for e in self:
            if not e.owner_id:
                raise UserError("Assign an owner before closing.")
            if not (e.resolution and e.note):
                raise UserError("A resolution and a note are required.")
            e.write({"state": "pending_approval", "proposed_by": self.env.user.id})

    def action_approve_close(self):
        if not self.env.user.has_group("pharma_core.group_pharma_finance"):
            raise UserError("Only a Finance Controller can approve closure.")
        for e in self:
            if e.state != "pending_approval":
                raise UserError("Only exceptions pending approval can be approved.")
            if e.proposed_by == self.env.user:
                raise UserError("Maker-checker: closure must be approved by someone other than the proposer.")
            e.write({"state": "closed", "approved_by": self.env.user.id})
