"""Agent 4: the invoice chaser, ported from cron 47.

Faithful to the production rules, including the three places my first pass had
guessed wrong: customer invoices only (not receipts), any existing activity
suppresses the chase, and it runs weekly rather than daily.
"""

from odoo import api, fields, models

from .agent_tools import activity_type, dry_run_enabled, log_run

INVOICE_CHASER_LIMIT = 40

# Production chases `out_invoice` only. Customer receipts are deliberately not
# in scope, and vendor bills never were — chasing ourselves for our own payables
# is a different job with a different owner.
CHASEABLE_TYPES = ("out_invoice",)

# `in_payment` is excluded: the money is already moving and the call would be
# wrong. `reversed` and `paid` need no chasing.
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
            # Production skips any invoice that already carries an activity —
            # deliberately, and it is also what makes this agent idempotent,
            # since its summary embeds the overdue day count and therefore
            # changes every single day. A summary marker could not dedupe it.
            ("activity_ids", "=", False),
        ]

    @api.model
    def _cron_chase_overdue_invoices(self, limit=INVOICE_CHASER_LIMIT, dry_run=None):
        """Raise a Call on the owner of each overdue posted customer invoice.

        One deliberate departure from production: the "has no activity" test is
        in the domain rather than applied in Python after the limit. Production
        takes 40 invoices and then discards those with activities, so a run can
        act on far fewer than 40 — sometimes none, while genuinely unchased
        invoices wait behind them. In the domain, the limit selects 40 invoices
        that actually need chasing.
        """
        dry_run = dry_run_enabled(self.env, dry_run)
        call = activity_type(self.env, "mail.mail_activity_data_call")
        today = fields.Date.context_today(self)
        moves = self.search(
            self._c2p_overdue_domain(today), limit=limit, order="invoice_date_due asc"
        )
        acted = 0
        ownerless = 0
        for move in moves:
            owner = move.invoice_user_id or move.create_uid
            if not owner:
                ownerless += 1
                continue
            overdue_days = (today - move.invoice_date_due).days
            acted += 1
            if dry_run:
                continue
            move.activity_schedule(
                activity_type_id=call.id,
                summary="Overdue %s days - %s" % (overdue_days, move.name),
                note="<p>%s is %s days overdue. Amount due: %s %s.</p>"
                % (
                    move.name,
                    overdue_days,
                    move.amount_residual,
                    move.currency_id.name or "",
                ),
                user_id=owner.id,
                date_deadline=today,
            )
        note = (
            "%s invoice(s) skipped for having no owner" % ownerless
            if ownerless
            else ""
        )
        return log_run(
            self.env, "invoice_chaser", len(moves), acted, dry_run, limit, note
        )
