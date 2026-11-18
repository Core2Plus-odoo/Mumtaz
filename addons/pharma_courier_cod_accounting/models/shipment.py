from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .remittance import MOVE_STATES
from .reversal import entry_is_open, reversal_state


class PharmaCourierShipment(models.Model):
    _name = "pharma.courier.shipment"
    _inherit = ["pharma.courier.shipment", "pharma.cod.entry.reversal"]
    _entry_field = "collection_move_id"

    collection_move_id = fields.Many2one(
        "account.move", string="Collection Entry", readonly=True, copy=False, ondelete="set null", index=True)
    collection_move_ref = fields.Char(string="Collection Entry No.", compute="_compute_collection_info")
    collection_move_state = fields.Selection(MOVE_STATES, string="Collection Entry Status",
                                             compute="_compute_collection_info")
    collection_reversal_state = fields.Selection(
        [("draft", "Reversal drafted"), ("posted", "Reversed")], string="Collection Entry Reversal",
        compute="_compute_collection_info")
    collection_move_open = fields.Boolean(
        compute="_compute_collection_info", help="The entry still stands: a draft, or posted and not reversed.")
    previous_move_ids = fields.Many2many(
        "account.move", "pharma_courier_shipment_prev_move_rel", "shipment_id", "move_id",
        string="Superseded Entries", readonly=True, copy=False,
        help="Collection entries that were cancelled or reversed before the current one was created.")

    @api.depends("collection_move_id", "collection_move_id.state", "collection_move_id.name",
                 "collection_move_id.reversal_move_ids.state")
    def _compute_collection_info(self):
        for s in self:
            move = s.collection_move_id.sudo()
            s.collection_move_ref = move.name if move else False
            s.collection_move_state = move.state if move else False
            s.collection_reversal_state = reversal_state(move) if move else False
            s.collection_move_open = entry_is_open(move) if move else False

    # ------------------------------------------------------------------ the entry
    def _collection_problem(self):
        """Why this shipment cannot have a collection entry yet, or False. One reason, in plain words."""
        self.ensure_one()
        if self.payment_mode != "cod":
            return _("is not a COD shipment")
        if self.state != "delivered":
            return _("is not delivered")
        if self.cod_collected <= 0:
            return _("has no COD collected")
        if not self.sale_order_id:
            return _("has no matching sale order, so there is no customer to credit")
        if self.collection_move_open:
            return _("already has collection entry %s", self.collection_move_id.sudo().name)
        return False

    def _collection_lines(self):
        """[(account, label, debit, credit, partner)] for this shipment, or a UserError naming what is missing."""
        self.ensure_one()
        courier = self.courier_id.sudo()
        missing = [lbl for f, lbl in (("acc_journal_id", _("Journal")),
                                      ("acc_clearing_account_id", _("COD clearing account"))) if not courier[f]]
        order = self.sale_order_id.sudo()
        partner = (order.partner_invoice_id or order.partner_id).commercial_partner_id
        receivable = partner.with_company(self.env.company).property_account_receivable_id
        if not receivable:
            raise UserError(_("Customer %s has no receivable account.", partner.display_name))
        if missing:
            raise UserError(_("Complete the Accounting tab of courier %(c)s first. Missing: %(m)s.",
                              c=courier.name, m=", ".join(missing)))
        amount = self.env.company.currency_id.round(self.cod_collected)
        tag = _("%(courier)s parcel %(trk)s, order %(so)s", courier=courier.name, trk=self.tracking_number,
                so=order.name)
        return [(courier.acc_clearing_account_id, _("COD collected by %s", tag), amount, 0.0, courier.partner_id),
                (receivable, _("COD paid by customer: %s", tag), 0.0, amount, partner)]

    def action_create_collection_entry(self):
        """Draft entry: the courier collected the customer's cash, so the courier holds it (debit clearing) and the
        customer no longer owes it (credit their receivable). Reconcile the credit with the invoice in Accounting. All or
        nothing: if any selected shipment cannot have one, none is created."""
        if not self.env.su and not self.env.user.has_group("pharma_core.group_pharma_finance"):
            raise UserError(_("Only a Finance Controller can create a collection entry."))
        problems = [f"{s.tracking_number} {why}" for s in self if (why := s._collection_problem())]
        if problems:
            raise UserError(_("No collection entry was created:\n%s", "\n".join(problems)))
        prepared = [(s, s._collection_lines()) for s in self]
        for s, lines in prepared:
            courier = s.courier_id.sudo()
            # Elevated rights on purpose, as for the settlement entry: a Finance Controller creates a DRAFT; an
            # accountant posts it. The user is unchanged, so the entry records who created it.
            move = self.env["account.move"].sudo().create({
                "move_type": "entry", "journal_id": courier.acc_journal_id.id,
                "date": s.date_delivered or fields.Date.context_today(s),
                "ref": _("COD collected %(c)s %(t)s", c=courier.code, t=s.tracking_number),
                "line_ids": [(0, 0, {"account_id": acc.id, "name": label, "debit": debit, "credit": credit,
                                     "partner_id": partner.id or False})
                             for acc, label, debit, credit, partner in lines]})
            s._retire_open_entry()
            s.collection_move_id = move
            s.message_post(body=_("Draft collection entry %s created. Post it from Accounting.", move.name or move.ref))
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Collection entries"), "type": "success", "sticky": False,
                           "message": _("%s draft collection entries created.", len(prepared))}}

    def action_open_collection_entry(self):
        self.ensure_one()
        if not self.collection_move_id:
            raise UserError(_("No collection entry has been created for %s.", self.display_name))
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": self.collection_move_id.id,
                "view_mode": "form"}
