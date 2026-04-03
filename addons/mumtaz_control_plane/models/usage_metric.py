from odoo import api, fields, models


class MumtazUsageMetric(models.Model):
    _name = "mumtaz.usage.metric"
    _description = "Mumtaz Usage Metric"
    _order = "period_start desc, id desc"

    tenant_id = fields.Many2one("mumtaz.tenant", required=True, ondelete="cascade", index=True)
    feature_id = fields.Many2one("mumtaz.feature", ondelete="set null", index=True)
    metric_code = fields.Char(required=True, index=True)
    period_start = fields.Date(required=True, index=True)
    period_end = fields.Date(required=True, index=True)
    value_used = fields.Float(default=0.0)
    value_limit = fields.Float()
    utilization_pct = fields.Float(compute="_compute_utilization_pct", store=True)
    source_system = fields.Selection(
        [
            ("api_gateway", "API Gateway"),
            ("erp", "ERP"),
            ("ai", "AI"),
            ("manual", "Manual"),
        ],
        default="manual",
        required=True,
    )
    last_sync_at = fields.Datetime()

    @api.depends("value_used", "value_limit")
    def _compute_utilization_pct(self):
        for rec in self:
            if rec.value_limit:
                rec.utilization_pct = (rec.value_used / rec.value_limit) * 100.0
            else:
                rec.utilization_pct = 0.0

    _sql_constraints = [
        (
            "mumtaz_usage_metric_unique",
            "unique(tenant_id, feature_id, metric_code, period_start, period_end)",
            "Usage metric row must be unique for tenant/feature/code/period.",
        ),
    ]
