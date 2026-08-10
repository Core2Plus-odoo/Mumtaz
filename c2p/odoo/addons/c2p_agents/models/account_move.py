"""Agent 4: the invoice chaser."""

from odoo import api, fields, models

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
    _name = "account.move"
    _inherit = ["account.move", "c2p.agent.mixin"]

    @api.model
    def _c2p_overdue_domain(self, today):
        return [
            ("move_type", "in", list(CHASEABLE_TYPES)),
            ("state", "=", "posted"),
            ("payment_state", "in", list(UNPAID_STATES)),
            ("invoice_date_due", "<", today),
        ]

    @api.model
    def _cron_chase_overdue_invoices(self, limit=None, dry_run=None):
        """Raise a Call on the owner of each overdue posted customer invoice.

        Unlike the two CRM chasers, this does not require the invoice to be free
        of activities. An overdue invoice frequently has other activities on it
        already, and none of them mean somebody has chased the payment — the
        duplicate marker alone decides that.
        """
        limit = limit or self._c2p_param_int("invoice_chaser_limit", 50)
        dry_run = self._c2p_dry_run(dry_run)
        scanned = acted = 0
        try:
            activity_type = self._c2p_activity_type("mail.mail_activity_data_call")
            today = fields.Date.context_today(self)
            moves = self.search(
                self._c2p_overdue_domain(today),
                limit=limit,
                order="invoice_date_due asc",
            )
            scanned = len(moves)
            flagged = self._c2p_already_flagged(
                "account.move", moves.ids, activity_type, CHASER_SUMMARY
            )
            for move in moves:
                if move.id in flagged:
                    continue
                acted += 1
                if dry_run:
                    continue
                move._c2p_schedule_activity(
                    activity_type,
                    CHASER_SUMMARY,
                    _chaser_note(move, today),
                    move.invoice_user_id or move.create_uid or self.env.user,
                    today,
                )
        except Exception:
            self._c2p_log_failure("invoice_chaser", scanned, acted, dry_run, limit)
            raise
        return self._c2p_finish("invoice_chaser", scanned, acted, dry_run, limit)


def _chaser_note(move, today):
    overdue_days = (today - move.invoice_date_due).days
    return (
        "%s is %s days overdue. Outstanding: %s %s. Raised automatically by the "
        "C2P invoice chaser."
        % (
            move.name or "This invoice",
            overdue_days,
            move.currency_id.name or "",
            move.amount_residual,
        )
    )
