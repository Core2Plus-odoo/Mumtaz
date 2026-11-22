import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

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

# Customer WhatsApp sending is switched off until the gateway project is
# approved (FAIZY HQ05 §2, ERP D-08). Anything other than "on" — including the
# parameter not existing at all — means off, so a fresh or neutralised
# database can never start messaging customers by accident.
SEND_MODE_PARAM = "faizy.whatsapp_send_mode"


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
            # Written while sending is off (faizy.whatsapp_send_mode). Never
            # picked up by the send cron, so these cannot go out later by
            # surprise when the gateway is switched on.
            ("held", "Not Sent (Sending Off)"),
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

    # ── Send mode ────────────────────────────────────────────────────────

    @api.model
    def _faizy_sending_enabled(self):
        """True only when a Manager has explicitly set the send mode to "on"."""
        mode = self.env["ir.config_parameter"].sudo().get_param(SEND_MODE_PARAM, "off")
        return (mode or "").strip().lower() == "on"

    @api.model_create_multi
    def create(self, vals_list):
        """Safety net for every caller that writes the queue directly.

        `queue_message` already refuses to create anything while sending is
        off; this catches the paths that call create() themselves (the ops
        alert, AI draft approval, future code). The row is kept as `held` so
        there is still a record of what would have been sent, but it can never
        reach the send cron.
        """
        if not self._faizy_sending_enabled():
            for vals in vals_list:
                if vals.get("state", "queued") == "queued":
                    vals["state"] = "held"
        return super().create(vals_list)

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
        recordset when there is no number to send to — or when customer
        WhatsApp sending is switched off, in which case nothing is created and
        the order (if any) gets an internal note instead."""
        if not self._faizy_sending_enabled():
            if order:
                order.sudo().message_post(
                    body=self.env._(
                        "Customer WhatsApp message not sent (%(type)s): "
                        "WhatsApp sending is switched off.",
                        type=message_type,
                    ),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
            return self.browse()
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

    # ── Sending ──────────────────────────────────────────────────────────

    def action_send(self):
        """Hand the message to the configured provider.

        The transport is intentionally a stub until Meta business verification
        clears and credentials exist — see faizy/docs/00-decisions.md. Rather
        than silently pretending success, an unconfigured provider leaves the
        message queued and records why.
        """
        if not self._faizy_sending_enabled():
            raise UserError(self.env._(
                "WhatsApp sending is switched off for this database. Nothing "
                "was sent. A Manager turns it on only after the WhatsApp "
                "gateway is approved."
            ))
        for message in self:
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
        if not self._faizy_sending_enabled():
            raise UserError(self.env._(
                "WhatsApp sending is switched off, so a retry would only queue "
                "the message for nothing. Nothing was changed."
            ))
        self.write({"state": "queued", "error_message": False})

    @api.model
    def _cron_send_queued(self, limit=50):
        """Drain the queue. Capped per run so a backlog cannot monopolise a worker.

        Does nothing at all while sending is off: the existing backlog stays
        exactly as it is (not sent, not deleted) until a Manager decides.
        """
        if not self._faizy_sending_enabled():
            return True
        queued = self.search(
            [("state", "=", "queued"), ("attempts", "<", 5)], limit=limit
        )
        queued.action_send()
        return True
