from odoo import fields, models


class MumtazSubscriptionLifecycleLog(models.Model):
    _name = "mumtaz.subscription.lifecycle.log"
    _description = "Mumtaz Subscription Lifecycle Log"
    _order = "processed_at desc, id desc"

    subscription_id = fields.Many2one(
        "mumtaz.subscription", required=True, ondelete="cascade", index=True
    )
    tenant_id = fields.Many2one("mumtaz.tenant", ondelete="set null", index=True)
    from_status = fields.Selection(
        [
            ("trial", "Trial"),
            ("active", "Active"),
            ("past_due", "Past Due"),
            ("grace", "Grace"),
            ("suspended", "Suspended"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        required=True,
    )
    to_status = fields.Selection(
        [
            ("trial", "Trial"),
            ("active", "Active"),
            ("past_due", "Past Due"),
            ("grace", "Grace"),
            ("suspended", "Suspended"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        required=True,
    )
    reason = fields.Text(required=True)
    policy_mode = fields.Selection(
        [("warn", "Warn Only"), ("enforce", "Enforce")],
        required=True,
        default="enforce",
    )
    tenant_impact_mode = fields.Selection(
        [("none", "None"), ("warn", "Warn Only"), ("enforce", "Enforce")],
        required=True,
        default="warn",
    )
    tenant_action = fields.Selection(
        [
            ("none", "None"),
            ("warn_suspend", "Warn Suspend Tenant"),
            ("suspend", "Suspend Tenant"),
            ("warn_reactivate", "Warn Reactivate Tenant"),
            ("reactivate", "Reactivate Tenant"),
        ],
        default="none",
        required=True,
    )
    applied = fields.Boolean(default=False, required=True)
    processed_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    source = fields.Selection(
        [("manual", "Manual"), ("cron", "Scheduled")],
        default="manual",
        required=True,
    )
