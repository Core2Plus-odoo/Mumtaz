"""Accounting steps of the COD process flow, added to the base flow of pharma_courier_cod.

Order, when this module is installed and the mode is strict (the default): a slip cannot be settled until every parcel on
it has a POSTED collection entry, because settling cash the books never recorded as collected leaves the clearing
account wrong. Finance can override with a written reason, which is logged; or the owner can switch the mode to
advisory (system parameter `pharma.cod_flow_mode` = advisory), when the gap is only noted. Nothing is ever posted by
this module: posting stays with the accountant."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

ACCOUNTING_STEPS = [
    ("collect_entry", "Create the collection entry"),
    ("post_collection", "Post the collection entry"),
    ("settle_entry", "Create the settlement entry"),
    ("post_settlement", "Post the settlement entry"),
    ("post_reversal", "Post the reversal entry"),
]
ACCOUNTING_OWNERS = {"collect_entry": "finance", "settle_entry": "finance", "post_collection": "accountant",
                     "post_settlement": "accountant", "post_reversal": "accountant"}
FLOW_MODE_PARAM = "pharma.cod_flow_mode"


def _ondelete():
    return {key: "set null" for key, _label in ACCOUNTING_STEPS}


class PharmaCourierRemittanceFlow(models.Model):
    _inherit = "pharma.courier.remittance"

    flow_next = fields.Selection(
        selection_add=[("settle_entry", "Create the settlement entry"), ("post_settlement", "Post the settlement entry"),
                       ("post_reversal", "Post the reversal entry")],
        ondelete={"settle_entry": "set null", "post_settlement": "set null", "post_reversal": "set null"})
    flow_override_reason = fields.Text(
        string="Order Override Reason", copy=False, tracking=True,
        help="Only needed when a parcel on this slip has no posted collection entry yet and the process is strict. "
             "Why settling anyway is right. It is logged on the slip.")

    def _flow_owner_map(self):
        owners = super()._flow_owner_map()
        owners.update(ACCOUNTING_OWNERS)
        return owners

    def _flow_entry_next(self):
        """The accounting step this reconciled slip still owes, or None when its entry stands."""
        self.ensure_one()
        if self.move_reversal_state == "draft":
            return "post_reversal"
        if not self.move_open:
            return "settle_entry"
        if self.move_state == "draft":
            return "post_settlement"
        return None

    def _flow_next_key(self):
        key = super()._flow_next_key()
        if self.state == "posted" and self.run_id:
            return self._flow_entry_next() or key
        return key

    @api.depends("move_id.state", "move_id.reversal_move_ids.state")
    def _compute_flow(self):
        return super()._compute_flow()

    # ------------------------------------------------------------------ the order check
    def _flow_mode(self):
        mode = self.env["ir.config_parameter"].sudo().get_param(FLOW_MODE_PARAM, "strict")
        return "advisory" if mode == "advisory" else "strict"

    def _check_flow_order(self):
        """Settlement needs a posted collection entry for every parcel on the slip."""
        self.ensure_one()
        unbooked = self.line_ids.shipment_id.filtered(
            lambda s: not (s.collection_move_state == "posted" and not s.collection_reversal_state))
        if not unbooked:
            return
        names = ", ".join(unbooked.mapped("tracking_number"))
        if self._flow_mode() == "advisory":
            self.message_post(body=_("Advisory: no posted collection entry yet for %s.", names))
            return
        reason = (self.flow_override_reason or "").strip()
        if not reason:
            raise UserError(_(
                "The settlement entry for %(slip)s cannot be created yet. These parcels have no POSTED collection "
                "entry: %(names)s.\nCreate and post their collection entries first, or, if settling now is right, "
                "write the reason in 'Order Override Reason' on this slip.", slip=self.display_name, names=names))
        self.message_post(body=_("Order check overridden by %(user)s. Reason: %(reason)s. Parcels without a posted "
                                 "collection entry: %(names)s.", user=self.env.user.name, reason=reason, names=names))


class PharmaCourierShipmentFlow(models.Model):
    _inherit = "pharma.courier.shipment"

    flow_next = fields.Selection(selection_add=ACCOUNTING_STEPS, ondelete=_ondelete())

    def _flow_owner_map(self):
        owners = super()._flow_owner_map()
        owners.update(ACCOUNTING_OWNERS)
        return owners

    def _flow_compute(self):
        stage, nxt = super()._flow_compute()
        if not (self.payment_mode == "cod" and self.state == "delivered" and self.cod_collected > 0):
            return stage, nxt
        if self.collection_reversal_state == "draft":
            return stage, "post_reversal"
        if not self.collection_move_open:
            return stage, "collect_entry"
        if self.collection_move_state == "draft":
            return stage, "post_collection"
        if stage == "closed":
            # nothing left on the courier side; the books may still owe the settlement
            for rem in self.line_ids.filtered(lambda l: l.state == "posted").remittance_id:
                step = rem._flow_entry_next() if rem.run_id else None
                if step:
                    return "reconciled", step
        return stage, nxt

    @api.depends("collection_move_id.state", "collection_move_id.reversal_move_ids.state",
                 "line_ids.remittance_id.move_id.state", "line_ids.remittance_id.move_id.reversal_move_ids.state")
    def _compute_flow(self):
        return super()._compute_flow()
