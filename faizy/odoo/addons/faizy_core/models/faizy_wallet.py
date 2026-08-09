from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FaizyWalletTransaction(models.Model):
    """Append-only wallet ledger for customer credit and worker payouts.

    The balance is summed from these rows and never stored. A stored balance and
    a ledger will eventually disagree, and at that point you cannot tell which
    one lied — so there is only ever one source of truth.

    Signs are enforced against the type: a "debit" cannot sneak in as a credit.
    """

    _name = "faizy.wallet.transaction"
    _description = "Faizy Wallet Transaction"
    _order = "create_date desc"

    name = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("faizy.wallet")
        or "/",
    )
    # Exactly one counterparty: a customer's wallet or a Faizy's payout account.
    partner_id = fields.Many2one("res.partner", string="Customer", index=True)
    worker_id = fields.Many2one("faizy.worker", string="Faizy", index=True)
    order_id = fields.Many2one("faizy.order", ondelete="set null", index=True)

    txn_type = fields.Selection(
        [
            ("topup", "Top-up"),
            ("debit", "Debit"),
            ("refund", "Refund"),
            ("payout", "Payout"),
            ("adjustment", "Adjustment"),
        ],
        required=True,
    )
    amount = fields.Monetary(
        required=True,
        currency_field="currency_id",
        help="Signed: credits positive, debits and payouts negative.",
    )
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id
    )
    reference = fields.Char()
    note = fields.Text()

    @api.constrains("partner_id", "worker_id")
    def _check_single_counterparty(self):
        for txn in self:
            if bool(txn.partner_id) == bool(txn.worker_id):
                raise ValidationError(
                    self.env._(
                        "A wallet transaction belongs to either a customer or a "
                        "Faizy — set exactly one."
                    )
                )

    @api.constrains("txn_type", "amount")
    def _check_sign_matches_type(self):
        for txn in self:
            if txn.txn_type in ("topup", "refund") and txn.amount <= 0:
                raise ValidationError(
                    self.env._("A %(kind)s must be positive.", kind=txn.txn_type)
                )
            if txn.txn_type in ("debit", "payout") and txn.amount >= 0:
                raise ValidationError(
                    self.env._("A %(kind)s must be negative.", kind=txn.txn_type)
                )
