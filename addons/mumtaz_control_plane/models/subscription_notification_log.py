from odoo import fields, models


class MumtazSubscriptionNotificationLog(models.Model):
    _name = "mumtaz.subscription.notification.log"
    _description = "Mumtaz Subscription Notification Log"
    _order = "sent_at desc, id desc"

    subscription_id = fields.Many2one("mumtaz.subscription", required=True, ondelete="cascade", index=True)
    tenant_id = fields.Many2one("mumtaz.tenant", ondelete="set null", index=True)
    event_code = fields.Selection(
        [
            ("trial_ending_soon", "Trial Ending Soon"),
            ("payment_overdue", "Payment Overdue"),
            ("entered_grace", "Entered Grace"),
            ("grace_ending_soon", "Grace Ending Soon"),
            ("suspended", "Suspended"),
            ("reactivated", "Reactivated"),
            ("renewal_requested", "Renewal Requested"),
        ],
        required=True,
        index=True,
    )
    dedupe_key = fields.Char(required=True, index=True)
    channel_chatter = fields.Boolean(default=True)
    channel_internal = fields.Boolean(default=True)
    channel_email = fields.Boolean(default=False)
    source = fields.Selection(
        [("manual", "Manual"), ("cron", "Scheduled"), ("lifecycle", "Lifecycle")],
        default="manual",
        required=True,
    )
    sent_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)

    _sql_constraints = [
        (
            "mumtaz_subscription_notification_log_unique",
            "unique(subscription_id, event_code, dedupe_key)",
            "Duplicate notification event detected for the same subscription and dedupe key.",
        ),
    ]
