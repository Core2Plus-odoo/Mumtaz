import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from .stripe_client import StripeError

_logger = logging.getLogger(__name__)

_CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}


class MumtazSubscription(models.Model):
    _inherit = "mumtaz.subscription"

    last_charge_attempt = fields.Datetime(readonly=True, copy=False)
    last_charge_error = fields.Char(readonly=True, copy=False)

    # ── Cron entry point ──────────────────────────────────────────────────
    @api.model
    def cron_charge_due_subscriptions(self):
        """Charge every current subscription whose renewal is due and whose
        payment is still outstanding. Runs before the lifecycle cron so that
        successful charges reactivate and failures flow into grace→suspend."""
        settings = self.env["mumtaz.stripe.settings"].sudo().get_singleton()
        if not settings.auto_charge_enabled:
            return
        if not self.env["mumtaz.stripe.client"]._is_configured():
            _logger.info("Stripe not configured; skipping auto-charge run.")
            return
        today = fields.Date.today()
        due = self.search([
            ("is_current", "=", True),
            ("status", "in", ["active", "trial", "past_due", "grace"]),
            ("renewal_date", "<=", today),
            ("payment_status", "in", ["pending", "overdue"]),
        ])
        for sub in due:
            # Each charge is isolated so one failure never blocks the batch.
            try:
                sub._stripe_charge()
                self.env.cr.commit()
            except Exception as exc:  # noqa: BLE001 - cron must be resilient
                self.env.cr.rollback()
                _logger.exception("Auto-charge failed for subscription %s: %s",
                                  sub.id, exc)

    # ── Charge a single subscription ──────────────────────────────────────
    def _stripe_charge(self):
        self.ensure_one()
        tenant = self.tenant_id
        if not tenant.stripe_customer_id or not tenant.stripe_payment_method_id:
            self.last_charge_error = "No card on file"
            return False

        amount = self.outstanding_amount or self.plan_id.list_price
        if amount <= 0:
            return False
        decimals = self.currency_id.decimal_places or 2
        amount_minor = int(round(amount * (10 ** decimals)))

        client = self.env["mumtaz.stripe.client"]
        self.last_charge_attempt = fields.Datetime.now()
        # Idempotency key ties a charge to (subscription, renewal date) so a
        # re-run on the same due date never double-charges.
        idem = f"sub-{self.id}-{self.renewal_date}"
        try:
            intent = client.create_payment_intent(
                amount_minor=amount_minor,
                currency=self.currency_id.name,
                customer_id=tenant.stripe_customer_id,
                payment_method_id=tenant.stripe_payment_method_id,
                metadata={"subscription_id": str(self.id),
                          "tenant_id": str(tenant.id)},
                idempotency_key=idem,
            )
        except StripeError as exc:
            self._stripe_mark_failed(exc.user_message)
            return False

        if intent.get("status") == "succeeded":
            self._stripe_mark_paid(intent.get("id"), amount)
            return True
        # requires_action / requires_payment_method etc. — treat as failed.
        self._stripe_mark_failed("Payment not completed (%s)" % intent.get("status"))
        return False

    # ── Outcome handlers — drive the existing lifecycle engine ────────────
    def _stripe_mark_paid(self, intent_id, amount):
        self.ensure_one()
        self.write({
            "payment_status": "paid",
            "outstanding_amount": 0.0,
            "external_billing_ref": intent_id or self.external_billing_ref,
            "last_charge_error": False,
            "renewal_date": self._stripe_next_renewal_date(),
        })
        self.env["mumtaz.subscription.billing.record"].sudo().create({
            "subscription_id": self.id,
            "record_type": "renewal",
            "payment_status": "paid",
            "amount_due": amount,
            "currency_id": self.currency_id.id,
            "paid_date": fields.Date.today(),
            "external_reference": intent_id,
            "commercial_notes": "Auto-charged via Stripe.",
        })
        self.message_post(body="Stripe charge succeeded (%s). Subscription renewed." % intent_id)
        # Let the lifecycle engine reactivate immediately if it was past_due/grace.
        self.process_lifecycle(source="cron")

    def _stripe_mark_failed(self, reason):
        self.ensure_one()
        self.write({
            "payment_status": "overdue",
            "last_charge_error": (reason or "Charge failed")[:200],
        })
        self.message_post(body="Stripe charge failed: %s" % (reason or "unknown"))
        # Lifecycle engine will move active→past_due→grace→suspended over time.
        self.process_lifecycle(source="cron")

    def _stripe_next_renewal_date(self):
        self.ensure_one()
        base = self.renewal_date or fields.Date.today()
        months = _CYCLE_MONTHS.get(self.billing_cycle, 1)
        return base + relativedelta(months=months)
