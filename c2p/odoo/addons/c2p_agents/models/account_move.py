"""Agent 4: the invoice chaser."""

from odoo import api, fields, models

from .agent_tools import activity_type, already_flagged, dry_run_enabled, log_run

INVOICE_CHASER_LIMIT = 50

# See the note on the crm.lead summaries: this string is the duplicate marker.
CHASER_SUMMARY = "C2P Agent: overdue invoice"

# Customer documents that can fall overdue. Vendor bills are deliberately out of
# scope — chasing ourselves for our own payables is a different job with a
# different owner.
CHASEABLE_TYPES = ("out_invoice", "out_receipt")

# Payment states worth a phone call. `in_payment` is excluded: the money is
# already moving and the call would be wrong.
UNPAID_STATES = ("not_paid", "partial")


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _c2p_overdue_domain(self, today):
        return [
            ("move_type", "in", list(CHASEABLE_TYPES)),
            ("state", "=", "posted"),
            ("payment_state", "in", list(UNPAID_STATES)),
            ("invoice_date_due", "<", today),
        ]

    @api.model
    def _cron_chase_overdue_invoices(self, limit=INVOICE_CHASER_LIMIT, dry_run=None):
        """Raise a Call on the owner of each overdue posted customer invoice.

        Unlike the two CRM chasers, this does not require the invoice to be free
        of activities. An overdue invoice often has other activities on it
        already, and none of them mean somebody has chased the payment — so here
        the duplicate marker alone decides.
        """
        dry_run = dry_run_enabled(self.env, dry_run)
        call = activity_type(self.env, "mail.mail_activity_data_call")
        today = fields.Date.context_today(self)
        moves = self.search(
            self._c2p_overdue_domain(today), limit=limit, order="invoice_date_due asc"
        )
        flagged = already_flagged(
            self.env, "account.move", moves.ids, call.id, CHASER_SUMMARY
        )
        acted = 0
        for move in moves:
            if move.id in flagged:
                continue
            acted += 1
            if dry_run:
                continue
            move.activity_schedule(
                activity_type_id=call.id,
                summary=CHASER_SUMMARY,
                note="%s is %s days overdue. Outstanding: %s %s."
                % (
                    move.name or "This invoice",
                    (today - move.invoice_date_due).days,
                    move.currency_id.name or "",
                    move.amount_residual,
                ),
                user_id=(move.invoice_user_id or move.create_uid or self.env.user).id,
                date_deadline=today,
            )
        return log_run(self.env, "invoice_chaser", len(moves), acted, dry_run, limit)
