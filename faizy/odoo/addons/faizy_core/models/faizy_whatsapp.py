import logging
from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Business-initiated transitions with no prior customer reply to ride inside —
# Meta (and Twilio, once Content Templates exist there) will not deliver these
# as free text outside a 24h session, so they default to a template named
# after the message type. Each name must be registered and approved before
# `faizy_whatsapp_provider` is turned on; see faizy/docs/00-decisions.md §2.
# `otp` is excluded: Meta prices and structures authentication templates
# differently (a code + button), not the single-body-variable shape here.
# `generic` is excluded: its text is ad hoc per call, not reusable as a
# template at all.
TEMPLATE_DEFAULT_TYPES = {
    "booking_confirmation", "faizy_assigned", "worker_assignment",
    "status_update", "receipt",
}

# Customer messages leave between these hours, Karachi time. A confirmation that
# lands at 3 a.m. is a worse experience than one that lands at 10, and the
# public AI-team page already promises "10am to 9pm". Overridable with
# `faizy.send_hours_start`, `faizy.send_hours_end` and `faizy.send_timezone`
# (ir.config_parameter); the defaults are the approved window.
SEND_HOURS_START = 10.0
SEND_HOURS_END = 21.0
SEND_TIMEZONE = "Asia/Karachi"


class FaizyWhatsappMessage(models.Model):
    """Outbound WhatsApp queue.

    Every message becomes a record before it becomes an API call. That ordering
    is the point: a failed send is a visible, retryable row rather than a
    notification nobody noticed was missing. It also gives ops one place to
    answer "was the customer actually told?".

    Provider-agnostic — Meta Cloud API and Twilio both drain this same queue.
    The transport itself is configured per company; until it is, messages simply
    accumulate as `queued`, which is a safe default.
    """

    _name = "faizy.whatsapp.message"
    _description = "Faizy WhatsApp Message"
    _order = "create_date desc"

    partner_id = fields.Many2one("res.partner", string="Customer", index=True)
    worker_id = fields.Many2one("faizy.worker", string="Faizy", index=True)
    phone = fields.Char(required=True, index=True)

    message_type = fields.Selection(
        [
            ("otp", "OTP"),
            ("booking_confirmation", "Booking Confirmation"),
            ("faizy_assigned", "Faizy Assigned"),
            ("worker_assignment", "Worker Assignment"),
            ("status_update", "Status Update"),
            ("receipt", "Receipt"),
            ("generic", "Generic"),
        ],
        required=True,
        index=True,
    )
    # WhatsApp only allows free-form text inside a 24h customer service window.
    # Anything outbound and unprompted must be an approved template.
    template_name = fields.Char()
    body = fields.Text(required=True)
    lang = fields.Selection([("en", "English"), ("ur", "Urdu")], default="en")

    order_id = fields.Many2one("faizy.order", ondelete="set null", index=True)

    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("failed", "Failed"),
        ],
        default="queued",
        required=True,
        index=True,
        # No `tracking` here: this model has no mail.thread, so Odoo logged
        # "unknown parameter 'tracking'" at load and silently ignored it. The
        # fix is to drop it rather than add the mixin — a send queue turns over
        # constantly, and giving every row a chatter would cost a message table
        # write per state change for an audit trail nobody reads. `sent_date`,
        # `error_message` and `retry_count` already record what matters.
    )
    provider = fields.Char(readonly=True)
    provider_message_id = fields.Char(readonly=True)
    error_message = fields.Text(readonly=True)
    attempts = fields.Integer(default=0, readonly=True)
    date_sent = fields.Datetime(readonly=True)

    # ── Composition ──────────────────────────────────────────────────────

    @api.model
    def _render_body(self, message_type, order=None, partner=None, worker=None):
        """Default copy for each transition.

        Short and factual — these arrive on a phone, often while the recipient is
        doing something else. When real WhatsApp templates are approved, these
        become the fallback text and `template_name` carries the approved one.
        """
        if message_type == "booking_confirmation" and order:
            return self.env._(
                "Faizy: your request %(ref)s (%(title)s) is confirmed. "
                "We'll let you know as soon as a Faizy is assigned.",
                ref=order.name,
                title=order.title,
            )
        if message_type == "faizy_assigned" and order:
            return self.env._(
                "Faizy: %(worker)s has been assigned to %(ref)s and will be in "
                "touch shortly.",
                worker=order.worker_id.name or "",
                ref=order.name,
            )
        if message_type == "worker_assignment" and order:
            return self.env._(
                "New job %(ref)s: %(title)s in %(city)s. Open the Faizy portal "
                "to accept.",
                ref=order.name,
                title=order.title,
                city=order.city or "",
            )
        if message_type == "status_update" and order:
            return self.env._(
                "Faizy: %(ref)s is now %(state)s.",
                ref=order.name,
                state=dict(order._fields["state"].selection).get(order.state, order.state),
            )
        if message_type == "receipt" and order:
            return self.env._(
                "Faizy: %(ref)s is complete. Total %(total)s %(currency)s. "
                "Thank you for trusting us with your family.",
                ref=order.name,
                total=f"{order.amount_total:.2f}",
                currency=order.currency_id.name,
            )
        return self.env._("Faizy update.")

    @api.model
    def contact_number(self):
        """The number customers and family members are told to write to.

        Read from res.company.phone, never hardcoded. FAIZY_SPEC.md §12 carries
        +971 58 128 2057 in the FMB welcome template, but Muhammad's call is the
        Pakistani number — and the family members receiving that message are in
        Pakistan, so a local number is the right one for them anyway.

        One source, because this string ends up in the FMB welcome, the ops
        alerts and the site, and three copies of a phone number become two
        numbers the moment one changes.
        """
        return (self.env.company.phone or "").strip()

    @api.model
    def queue_message(
        self,
        partner=None,
        worker=None,
        message_type="generic",
        order=None,
        body=None,
        template_name=None,
    ):
        """Put one message on the queue. Returns the record, or an empty
        recordset when there is no number to send to."""
        phone = None
        lang = "en"
        if partner:
            # `phone` alone: Odoo 19 dropped res.partner.mobile, so the old
            # `partner.mobile or partner.phone` raised AttributeError and took
            # down every transition that notifies a customer.
            phone = partner.phone
            lang = "ur" if (partner.lang or "").startswith("ur") else "en"
        elif worker:
            phone = worker.phone
            # Ground staff in Pakistan — Urdu is the sensible default.
            lang = "ur"

        if not phone:
            return self.browse()

        return self.create(
            {
                "partner_id": partner.id if partner else False,
                "worker_id": worker.id if worker else False,
                "phone": phone,
                "message_type": message_type,
                "template_name": template_name
                or (message_type if message_type in TEMPLATE_DEFAULT_TYPES else False),
                "order_id": order.id if order else False,
                "lang": lang,
                "body": body
                or self._render_body(
                    message_type, order=order, partner=partner, worker=worker
                ),
            }
        )

    # ── Send window ──────────────────────────────────────────────────────

    @api.model
    def _within_send_hours(self, dt=None):
        """True when `dt` (naive UTC, default now) is inside the customer send window."""
        get = self.env["ir.config_parameter"].sudo().get_param

        def number(key, default):
            try:
                return float(get(key, default))
            except (TypeError, ValueError):
                return default

        try:
            tz = ZoneInfo(get("faizy.send_timezone", SEND_TIMEZONE))
        except (ZoneInfoNotFoundError, ValueError):
            tz = ZoneInfo(SEND_TIMEZONE)
        start = number("faizy.send_hours_start", SEND_HOURS_START)
        end = number("faizy.send_hours_end", SEND_HOURS_END)
        local = (dt or fields.Datetime.now()).replace(tzinfo=timezone.utc).astimezone(tz)
        return start <= local.hour + local.minute / 60.0 < end

    def _is_send_window_gated(self):
        """Customer-facing messages wait for the window.

        Not gated: a login code (`otp`), because the person asked for it a
        second ago and a code that arrives next morning is useless, and
        messages to ground staff (`worker_id`), who work their own hours.
        """
        self.ensure_one()
        return bool(self.partner_id and not self.worker_id and self.message_type != "otp")

    def _hold_until_window(self):
        """Leave the rows queued and say why, without counting an attempt."""
        note = self.env._("Held until the customer send window opens (Karachi time).")
        for message in self.filtered(lambda m: m.error_message != note):
            message.error_message = note

    # ── Sending ──────────────────────────────────────────────────────────

    def action_send(self):
        """Hand the message to the configured provider.

        The transport is intentionally a stub until Meta business verification
        clears and credentials exist — see faizy/docs/00-decisions.md. Rather
        than silently pretending success, an unconfigured provider leaves the
        message queued and records why.
        """
        messages = self
        if not self._within_send_hours():
            held = self.filtered(lambda m: m._is_send_window_gated())
            held._hold_until_window()
            messages = self - held
        for message in messages:
            provider = message._get_provider()
            if not provider:
                message.write(
                    {
                        "attempts": message.attempts + 1,
                        "error_message": self.env._(
                            "No WhatsApp provider configured. Set the credentials "
                            "in Settings before messages can be delivered."
                        ),
                    }
                )
                continue
            try:
                result = provider._send_whatsapp(message)
                message.write(
                    {
                        "state": "sent",
                        "provider": provider._name,
                        "provider_message_id": result.get("message_id"),
                        "date_sent": fields.Datetime.now(),
                        "attempts": message.attempts + 1,
                        "error_message": False,
                    }
                )
            except Exception as err:  # noqa: BLE001 - one bad send must not stop the batch
                _logger.warning("Faizy WhatsApp send failed: %s", err)
                message.write(
                    {
                        "state": "failed",
                        "attempts": message.attempts + 1,
                        "error_message": str(err),
                    }
                )

    def _get_provider(self):
        """Resolve the transport: the company, once it holds working credentials
        for the provider it names — see faizy_whatsapp_transport.py. False
        until Settings → Faizy → WhatsApp is actually filled in."""
        self.ensure_one()
        company = self.env.company
        return company if company._faizy_whatsapp_configured() else False

    def action_retry(self):
        self.write({"state": "queued", "error_message": False})

    @api.model
    def _cron_send_queued(self, limit=50):
        """Drain the queue. Capped per run so a backlog cannot monopolise a worker."""
        domain = [("state", "=", "queued"), ("attempts", "<", 5)]
        if not self._within_send_hours():
            # Outside the window only messages that may go out are picked, so
            # held customer rows neither use up the batch nor get rewritten
            # every 15 minutes all night.
            domain += [
                "|", "|",
                ("message_type", "=", "otp"),
                ("partner_id", "=", False),
                ("worker_id", "!=", False),
            ]
        queued = self.search(domain, limit=limit)
        queued.action_send()
        return True
