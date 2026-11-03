import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class FaizyOrderAlert(models.Model):
    """Tell ops when a customer files a request, so someone actually assigns it.

    Nothing else does this. A customer-created order lands as `pending` and
    sits there until a human in Operations happens to look at the board —
    there was previously no push in either direction. This fires on every
    `create()`, regardless of caller, which is what an `_inherit`d create
    override is for: the portal form, the JSON API `_create_care_request`
    uses, the backend "New" button and the sample-data loader all go through
    the same `faizy.order.create()`, so one override covers all of them.

    The alert failing must never block the order itself existing — a customer
    whose booking silently vanished because a notification broke is a worse
    outcome than a notification that quietly fails and gets fixed later. Both
    channels are attempted and logged independently for that reason.
    """

    _inherit = "faizy.order"

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            # Sample data creates dozens of orders at once for demo purposes;
            # alerting on those would page a human about fake bookings every
            # time the demo set is regenerated. Every other model in this
            # addon excludes is_sample the same way.
            if order.is_sample:
                continue
            try:
                self._alert_ops_new_order(order)
            except Exception:
                _logger.exception(
                    "Faizy ops alert failed for order %s", order.id
                )
        return orders

    def _alert_ops_new_order(self, order):
        self.ensure_one()
        svc = order.service_id.name or "Unknown service"
        cust = order.partner_id.name or "Unknown customer"
        fam = order.family_member_id.name or "The household"
        city = order.city or "Unknown city"
        ref = order.name or "New order"

        wa_body = (
            "New Faizy order — needs assignment\n\n"
            f"Ref: {ref}\n"
            f"Service: {svc}\n"
            f"For: {fam}\n"
            f"Customer: {cust}\n"
            f"City: {city}\n\n"
            "Assign at: myfaizy.com/odoo/faizy-orders"
        )
        # sudo(): this runs inside an order create() triggered by a portal
        # customer's own session as often as by staff, and a portal user has
        # no write access to faizy.whatsapp.message or mail.mail. The alert
        # is a system side-effect of the create, not a permission the caller
        # needs of their own.
        #
        # message_type must be one of faizy.whatsapp.message's own selection
        # values (otp / booking_confirmation / faizy_assigned /
        # worker_assignment / status_update / receipt / generic) — "generic"
        # here because none of the specific ones describe an ops-facing
        # assignment alert, and the ORM raises ValueError on anything outside
        # that list rather than silently accepting a new one.
        self.env["faizy.whatsapp.message"].sudo().create({
            "phone": "+923343043970",
            "message_type": "generic",
            "template_name": "ops_new_order",
            "body": wa_body,
            "order_id": order.id,
            "state": "queued",
        })

        self.env["mail.mail"].sudo().create({
            "subject": f"New order needs assignment — {ref}",
            "body_html": (
                "<p><b>New Faizy Care Order</b></p>"
                f"<p>Service: {svc}<br/>For: {fam}<br/>"
                f"Customer: {cust}<br/>City: {city}</p>"
                '<p><a href="https://myfaizy.com/odoo/faizy-orders">Assign now</a></p>'
            ),
            "email_to": "hello@myfaizy.com",
            "auto_delete": True,
        }).send()

        order.message_post(
            body="Ops alerted — WhatsApp queued, email sent.",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        _logger.info("Faizy ops alert sent for order %s (%s)", ref, city)
