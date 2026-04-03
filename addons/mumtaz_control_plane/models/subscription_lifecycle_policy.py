from datetime import timedelta

from odoo import api, fields, models


class MumtazSubscriptionLifecyclePolicy(models.AbstractModel):
    _name = "mumtaz.subscription.lifecycle.policy"
    _description = "Mumtaz Subscription Lifecycle Policy"

    @api.model
    def _get_param_int(self, key, default):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        if value in (None, ""):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @api.model
    def _get_param_bool(self, key, default):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        if value in (None, ""):
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    @api.model
    def _get_param_choice(self, key, default, allowed):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        if not value:
            return default
        value = str(value).strip().lower()
        return value if value in allowed else default

    @api.model
    def get_policy(self):
        return {
            "past_due_to_grace_days": self._get_param_int(
                "mumtaz_control_plane.lifecycle.past_due_to_grace_days", 3
            ),
            "grace_period_days": self._get_param_int(
                "mumtaz_control_plane.lifecycle.grace_period_days", 7
            ),
            "subscription_enforcement_mode": self._get_param_choice(
                "mumtaz_control_plane.lifecycle.subscription_enforcement_mode",
                "enforce",
                ["enforce", "warn"],
            ),
            "tenant_impact_mode": self._get_param_choice(
                "mumtaz_control_plane.lifecycle.tenant_impact_mode",
                "warn",
                ["none", "warn", "enforce"],
            ),
            "allow_auto_reactivation": self._get_param_bool(
                "mumtaz_control_plane.lifecycle.allow_auto_reactivation", True
            ),
        }

    @api.model
    def evaluate_transition(self, subscription, as_of_date):
        as_of = fields.Date.to_date(as_of_date) or fields.Date.context_today(self)
        status = subscription.status

        if status == "cancelled" and subscription.end_date and as_of > subscription.end_date:
            return {
                "to_status": "expired",
                "reason": "Cancelled subscription passed its end date.",
                "set_is_current": False,
            }

        if status in ("active", "trial") and subscription.end_date and as_of > subscription.end_date:
            return {
                "to_status": "expired",
                "reason": "Subscription reached end date.",
                "set_is_current": False,
            }

        if status == "trial" and subscription.trial_end and as_of > subscription.trial_end:
            if subscription.payment_status in ("paid", "waived"):
                return {
                    "to_status": "active",
                    "reason": "Trial ended and payment status allows activation.",
                    "clear_grace_until": True,
                }
            return {
                "to_status": "past_due",
                "reason": "Trial ended without cleared payment state.",
            }

        policy = self.get_policy()
        if policy["allow_auto_reactivation"] and status in ("past_due", "grace", "suspended"):
            if subscription.payment_status in ("paid", "waived"):
                return {
                    "to_status": "active",
                    "reason": "Payment recovered; auto-reactivation policy enabled.",
                    "clear_grace_until": True,
                }

        if status == "active" and subscription.payment_status == "overdue":
            return {
                "to_status": "past_due",
                "reason": "Active subscription moved to past due because payment is overdue.",
            }

        reference_date = subscription.renewal_date or subscription.end_date or subscription.trial_end

        if status == "past_due":
            if reference_date:
                days_overdue = (as_of - reference_date).days
            else:
                days_overdue = policy["past_due_to_grace_days"]

            if days_overdue >= policy["past_due_to_grace_days"]:
                return {
                    "to_status": "grace",
                    "reason": "Past due exceeded configured threshold; moved to grace.",
                    "set_grace_until": as_of + timedelta(days=policy["grace_period_days"]),
                }

        if status == "grace":
            if subscription.grace_until and as_of > subscription.grace_until:
                return {
                    "to_status": "suspended",
                    "reason": "Grace period elapsed; suspension threshold reached.",
                }

        return None
