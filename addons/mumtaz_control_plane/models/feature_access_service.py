from datetime import datetime

from odoo import api, models


class MumtazFeatureAccessService(models.AbstractModel):
    _name = "mumtaz.feature.access.service"
    _description = "Mumtaz Feature Access Service"

    @api.model
    def resolve_feature_access(self, tenant, feature, timestamp=None, include_quota=True):
        tenant_rec = self._coerce_tenant(tenant)
        feature_rec = self._coerce_feature(feature)
        at_time = self._coerce_timestamp(timestamp)

        payload = {
            "tenant_id": tenant_rec.id,
            "feature_id": feature_rec.id,
            "effective_enabled": False,
            "effective_limit": None,
            "source": "plan",
            "reason": "Feature is not available in the current plan.",
            "quota": None,
        }

        subscription = self._resolve_current_subscription(tenant_rec, at_time)
        if not subscription:
            payload.update(
                {
                    "source": "subscription",
                    "reason": "No active/current subscription found.",
                }
            )
            return payload

        plan_feature = self.env["mumtaz.plan.feature"].search(
            [
                ("plan_id", "=", subscription.plan_id.id),
                ("feature_id", "=", feature_rec.id),
            ],
            limit=1,
        )
        if plan_feature:
            payload["effective_enabled"] = bool(plan_feature.enabled)
            payload["effective_limit"] = (
                plan_feature.quota_limit if feature_rec.feature_type == "quota" else None
            )
            payload["reason"] = "Resolved from plan feature mapping."

        override = self._resolve_active_override(tenant_rec, feature_rec, at_time)
        if override:
            payload = self._apply_override(payload, override)

        if include_quota and feature_rec.feature_type == "quota":
            payload["quota"] = self._resolve_quota_status(
                tenant_rec, feature_rec, payload["effective_limit"], at_time
            )

        return payload

    @api.model
    def batch_resolve_for_tenant(self, tenant, timestamp=None, include_quota=True):
        tenant_rec = self._coerce_tenant(tenant)
        features = self.env["mumtaz.feature"].search([("active", "=", True)])
        return [
            self.resolve_feature_access(tenant_rec, f, timestamp=timestamp, include_quota=include_quota)
            for f in features
        ]

    def _coerce_tenant(self, tenant):
        if hasattr(tenant, "_name") and tenant._name == "mumtaz.tenant":
            return tenant
        return self.env["mumtaz.tenant"].browse(int(tenant))

    def _coerce_feature(self, feature):
        if hasattr(feature, "_name") and feature._name == "mumtaz.feature":
            return feature
        return self.env["mumtaz.feature"].browse(int(feature))

    def _coerce_timestamp(self, timestamp):
        if timestamp is None:
            return datetime.utcnow()
        if isinstance(timestamp, datetime):
            return timestamp
        return datetime.fromisoformat(str(timestamp))

    def _resolve_current_subscription(self, tenant, at_time):
        at_date = at_time.date()
        subscriptions = self.env["mumtaz.subscription"].search(
            [
                ("tenant_id", "=", tenant.id),
                ("is_current", "=", True),
                ("status", "in", ["trial", "active", "past_due", "grace"]),
            ],
            order="id desc",
        )
        for sub in subscriptions:
            if sub.start_date and sub.start_date > at_date:
                continue
            if sub.end_date and sub.end_date < at_date:
                continue
            return sub
        return False

    def _resolve_active_override(self, tenant, feature, at_time):
        overrides = self.env["mumtaz.tenant.feature"].search(
            [
                ("tenant_id", "=", tenant.id),
                ("feature_id", "=", feature.id),
            ],
            order="id desc",
        )
        for override in overrides:
            if override.effective_from and override.effective_from > at_time:
                continue
            if override.effective_to and override.effective_to < at_time:
                continue
            return override
        return False

    def _apply_override(self, payload, override):
        mode = override.override_mode
        if mode == "inherit":
            payload.update({"source": "plan", "reason": "Override set to inherit."})
        elif mode == "force_on":
            payload.update(
                {
                    "effective_enabled": True,
                    "source": "override",
                    "reason": "Feature force-enabled by tenant override.",
                }
            )
        elif mode == "force_off":
            payload.update(
                {
                    "effective_enabled": False,
                    "source": "override",
                    "reason": "Feature force-disabled by tenant override.",
                }
            )
        elif mode == "quota_override":
            payload.update(
                {
                    "effective_enabled": True,
                    "effective_limit": override.override_quota_limit,
                    "source": "override",
                    "reason": "Quota overridden at tenant level.",
                }
            )
        return payload

    def _resolve_quota_status(self, tenant, feature, limit_value, at_time):
        at_date = at_time.date()
        metric = self.env["mumtaz.usage.metric"].search(
            [
                ("tenant_id", "=", tenant.id),
                ("feature_id", "=", feature.id),
                ("period_start", "<=", at_date),
                ("period_end", ">=", at_date),
            ],
            order="period_end desc, id desc",
            limit=1,
        )

        used_value = metric.value_used if metric else 0.0
        if not limit_value:
            state = "unlimited"
        elif used_value > limit_value:
            state = "exceeded"
        elif used_value >= (0.8 * limit_value):
            state = "nearing_limit"
        else:
            state = "within_limit"

        return {
            "metric_id": metric.id if metric else False,
            "metric_code": metric.metric_code if metric else feature.metric_code_default,
            "value_used": used_value,
            "value_limit": limit_value,
            "utilization_pct": metric.utilization_pct if metric else 0.0,
            "status": state,
        }
