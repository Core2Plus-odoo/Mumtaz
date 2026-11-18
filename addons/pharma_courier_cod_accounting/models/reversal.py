from odoo import _, fields, models
from odoo.exceptions import UserError

REVERSIBLE_MODELS = ("pharma.courier.remittance", "pharma.courier.shipment")


def entry_is_open(move):
    """True while a COD entry still stands: a draft, or a posted entry that has no POSTED reversal.

    A cancelled entry, or a posted one whose reversal is posted, is void: the shipment or remittance may then get a
    corrected entry. A posted entry with only a DRAFT reversal still stands, so nothing is created twice meanwhile."""
    move = move.sudo()
    if not move or move.state == "cancel":
        return False
    return not (move.state == "posted" and any(r.state == "posted" for r in move.reversal_move_ids))


def reversal_state(move):
    """'posted' when a posted reversal exists, 'draft' when only a draft one does, else False."""
    live = move.sudo().reversal_move_ids.filtered(lambda m: m.state != "cancel")
    if not live:
        return False
    return "posted" if any(m.state == "posted" for m in live) else "draft"


class PharmaCodEntryReversal(models.AbstractModel):
    """Shared by the remittance (settlement entry) and the shipment (collection entry). Standard Odoo already
    reverses a journal entry; what it cannot do is tell the COD record that its entry was withdrawn. This adds the
    controlled request (Finance asks, with a reason), a DRAFT reversal that an accountant posts, and the release of
    the record so a corrected entry can be created. The module still never posts anything."""
    _name = "pharma.cod.entry.reversal"
    _description = "COD entry reversal (shared behaviour)"
    _entry_field = None

    def _reverse_entry(self, reason, date):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("pharma_core.group_pharma_finance"):
            raise UserError(_("Only a Finance Controller can ask for an entry to be reversed."))
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("A reason is required to reverse an entry."))
        move = self[self._entry_field].sudo()
        if not move:
            raise UserError(_("%s has no entry to reverse.", self.display_name))
        if move.state == "draft":
            raise UserError(_("%s is still a draft: cancel it in Accounting instead of reversing it.",
                              move.name or move.ref))
        if move.state == "cancel":
            raise UserError(_("%s is cancelled: there is nothing to reverse.", move.name or move.ref))
        if move.reversal_move_ids.filtered(lambda m: m.state != "cancel"):
            raise UserError(_("%s already has a reversal entry.", move.name))
        # Standard Odoo reversal, kept as a DRAFT (cancel=False also leaves every reconciliation untouched).
        # Elevated rights on purpose, as for the entries themselves: a Finance Controller asks, an accountant posts.
        reversal = move._reverse_moves([{
            "ref": _("Reversal of %(m)s: %(r)s", m=move.name, r=reason),
            "date": date or fields.Date.context_today(self)}], cancel=False)
        self.message_post(body=_("Draft reversal entry %(rev)s created for %(m)s. Reason: %(r)s. "
                                 "Post it from Accounting.", rev=reversal.name or reversal.ref, m=move.name, r=reason))
        return reversal

    def action_open_reverse_wizard(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "pharma.courier.entry.reverse", "view_mode": "form",
                "target": "new", "context": {"default_res_model": self._name, "default_res_id": self.id}}

    def _retire_open_entry(self):
        """Called just before a corrected entry replaces a void one: keep the void one on record."""
        move = self.sudo()[self._entry_field]
        if move:
            # sudo: a Finance Controller has no Accounting rights, same reason the entries themselves are sudo'd
            self.sudo().previous_move_ids = [(4, move.id)]


class PharmaCourierEntryReverse(models.TransientModel):
    _name = "pharma.courier.entry.reverse"
    _description = "Reverse a COD journal entry"

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    reason = fields.Text(required=True, help="Why the posted entry is being withdrawn. Kept on the reversal entry "
                                             "and in the record's history.")
    date = fields.Date(string="Reversal Date", required=True, default=fields.Date.context_today)

    def action_confirm(self):
        self.ensure_one()
        if self.res_model not in REVERSIBLE_MODELS:
            raise UserError(_("This entry cannot be reversed from here."))
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            raise UserError(_("The record no longer exists."))
        record._reverse_entry(self.reason, self.date)
        return {"type": "ir.actions.act_window_close"}
