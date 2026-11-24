from odoo import _, fields, models
from odoo.exceptions import UserError

LEAD_GROUP = "c2p_project_tracker.group_c2p_delivery_lead"


class ProjectMilestone(models.Model):
    _inherit = "project.milestone"

    c2p_baseline_deadline = fields.Date(
        string="Baseline Date", copy=False,
        help="The date first committed. The Deadline is the current forecast.")
    c2p_plan_change_ids = fields.One2many(
        "c2p.plan.change", "milestone_id", string="Plan Changes")

    def write(self, vals):
        """A committed milestone date keeps its baseline when it moves, and the
        Consultants account owner is told."""
        if ("deadline" not in vals and "c2p_baseline_deadline" not in vals) \
                or self.env.su or self.env.context.get("c2p_plan_change"):
            return super().write(vals)
        milestones = self.filtered(
            lambda m: m.project_id.c2p_layer == "delivery")
        if not milestones:
            return super().write(vals)
        is_lead = self.env.user.has_group(LEAD_GROUP)
        if "c2p_baseline_deadline" in vals and milestones.filtered(
                "c2p_baseline_deadline"):
            raise UserError(_(
                "A baseline date is not edited once set. The forecast moves; "
                "the baseline is what it is measured against."))
        before = {m.id: m.deadline for m in milestones}
        res = super().write(vals)
        Change = self.env["c2p.plan.change"]
        for ms in milestones:
            old = before[ms.id]
            if not old or ms.deadline == old:
                continue
            if not is_lead:
                raise UserError(_(
                    "Milestone '%s' has a committed date. Propose a plan "
                    "change and the delivery owner will decide.", ms.name))
            baseline = ms.c2p_baseline_deadline or old
            if not ms.c2p_baseline_deadline:
                super(ProjectMilestone, ms).write(
                    {"c2p_baseline_deadline": baseline})
            change = Change._log_direct_edit(
                "date", str(old), str(ms.deadline or ""), milestone=ms,
                baseline=baseline)
            change._notify_account_owner(_(
                "Milestone %(ms)s moved from %(old)s to %(new)s (baseline "
                "%(base)s). %(why)s", ms=ms.name, old=old,
                new=ms.deadline or _("no date"), base=baseline,
                why=change.reason))
        return res
