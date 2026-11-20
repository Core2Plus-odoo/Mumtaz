from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .courier import ACCOUNT_FIELDS
from .reversal import entry_is_open, reversal_state

# remittance line deduction field -> courier account field
DEDUCTION_ACCOUNTS = {
    "deduction_freight": "acc_freight_account_id",
    "deduction_cod_fee": "acc_cod_fee_account_id",
    "deduction_wht_income_tax": "acc_wht_income_account_id",
    "deduction_wht_sales_tax": "acc_wht_sales_account_id",
    "deduction_other": "acc_other_account_id",
}
MOVE_STATES = [("draft", "Draft"), ("posted", "Posted"), ("cancel", "Cancelled")]


class PharmaCourierRemittance(models.Model):
    _name = "pharma.courier.remittance"
    _inherit = ["pharma.courier.remittance", "pharma.cod.entry.reversal"]
    _entry_field = "move_id"

    move_id = fields.Many2one("account.move", string="Journal Entry", readonly=True, copy=False, ondelete="set null",
                              index=True)
    move_ref = fields.Char(string="Entry", compute="_compute_move_info",
                           help="Read with elevated rights so Finance sees the entry's number and state without "
                                "needing Accounting access.")
    move_state = fields.Selection(MOVE_STATES, string="Entry Status", compute="_compute_move_info")
    move_reversal_state = fields.Selection(
        [("draft", "Reversal drafted"), ("posted", "Reversed")], string="Entry Reversal", compute="_compute_move_info")
    move_open = fields.Boolean(compute="_compute_move_info",
                               help="The entry still stands: a draft, or posted and not reversed.")
    previous_move_ids = fields.Many2many(
        "account.move", "pharma_courier_remittance_prev_move_rel", "remittance_id", "move_id",
        string="Superseded Entries", readonly=True, copy=False,
        help="Entries that were cancelled or reversed before the current one was created.")

    @api.depends("move_id", "move_id.state", "move_id.name", "move_id.reversal_move_ids.state")
    def _compute_move_info(self):
        for r in self:
            move = r.move_id.sudo()
            r.move_ref = move.name if move else False
            r.move_state = move.state if move else False
            r.move_reversal_state = reversal_state(move) if move else False
            r.move_open = entry_is_open(move) if move else False

    # ------------------------------------------------------------------ the entry
    def _entry_lines(self):
        """Return [(account, label, debit, credit)] for this remittance, balanced, or raise a UserError that names
        exactly what is missing. Pure computation: nothing is written."""
        self.ensure_one()
        courier = self.courier_id.sudo()
        currency = self.env.company.currency_id
        rnd = currency.round
        gross, bank = rnd(self.amount_gross), rnd(self.bank_amount)
        tag = _("%(courier)s slip %(slip)s", courier=courier.name, slip=self.slip_ref)
        lines = [(courier.acc_clearing_account_id, _("COD collected by %s", tag), 0.0, gross),
                 (courier.acc_bank_account_id, _("Received from %s", tag), bank, 0.0)]
        missing = [lbl for f, lbl in (("acc_journal_id", ACCOUNT_FIELDS["acc_journal_id"]),
                                      ("acc_clearing_account_id", ACCOUNT_FIELDS["acc_clearing_account_id"]),
                                      ("acc_bank_account_id", ACCOUNT_FIELDS["acc_bank_account_id"])) if not courier[f]]
        total_debit = bank
        for fname, afield in DEDUCTION_ACCOUNTS.items():
            amount = rnd(sum(self.line_ids.mapped(fname)))
            if not amount:
                continue
            if not courier[afield]:
                missing.append(ACCOUNT_FIELDS[afield])
                continue
            label = self.line_ids._fields[fname].string
            lines.append((courier[afield], f"{label}: {tag}", amount, 0.0))
            total_debit += amount
        diff = rnd(gross - total_debit)          # slip net minus what reached the bank
        if diff:
            if not courier.acc_difference_account_id:
                missing.append(ACCOUNT_FIELDS["acc_difference_account_id"])
            else:
                label = _("Difference between slip and bank: %s", tag)
                lines.append((courier.acc_difference_account_id, label, diff if diff > 0 else 0.0,
                              -diff if diff < 0 else 0.0))
        if missing:
            raise UserError(_("Complete the Accounting tab of courier %(c)s first. Missing: %(m)s.",
                              c=courier.name, m=", ".join(dict.fromkeys(missing))))
        return [ln for ln in lines if ln[2] or ln[3]]

    def action_create_entry(self):
        if not self.env.su and not self.env.user.has_group("pharma_core.group_pharma_finance"):
            raise UserError(_("Only a Finance Controller can create the journal entry for a remittance."))
        for r in self:
            if r.state != "posted" or not r.run_id:
                raise UserError(_("%s must be posted and reconciled against the bank before an entry is created.",
                                  r.display_name))
            if r.move_open:
                raise UserError(_("%(r)s already has journal entry %(m)s.", r=r.display_name, m=r.move_id.sudo().name))
            if r.bank_amount <= 0 or r.amount_gross <= 0:
                raise UserError(_("%s needs a bank amount and a remitted gross above zero.", r.display_name))
            r._check_flow_order()
            lines = r._entry_lines()
            courier = r.courier_id.sudo()
            partner = courier.partner_id.id or False
            # Created with elevated rights on purpose: the person pressing the button is a Finance Controller, not
            # necessarily an accountant. It is a DRAFT, so posting still needs an accountant. The user is unchanged,
            # so the entry records who created it.
            move = self.env["account.move"].sudo().create({
                "move_type": "entry", "pharma_cod_kind": "settlement", "journal_id": courier.acc_journal_id.id, "date": r.date,
                "ref": _("COD %(c)s %(s)s", c=courier.code, s=r.slip_ref),
                "line_ids": [(0, 0, {"account_id": acc.id, "name": label, "debit": debit, "credit": credit,
                                     "partner_id": partner}) for acc, label, debit, credit in lines]})
            r._retire_open_entry()
            r.move_id = move
            r.message_post(body=_("Draft journal entry %s created. Post it from Accounting.", move.name or move.ref))
        return True

    def action_open_entry(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No journal entry has been created for %s.", self.display_name))
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": self.move_id.id,
                "view_mode": "form"}
