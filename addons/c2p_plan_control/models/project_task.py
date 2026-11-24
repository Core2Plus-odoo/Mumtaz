from odoo import _, fields, models
from odoo.exceptions import UserError

LEAD_GROUP = "c2p_project_tracker.group_c2p_delivery_lead"


class ProjectTask(models.Model):
    _inherit = "project.task"

    c2p_acceptance_criteria = fields.Text(
        string="Acceptance Criteria",
        help="How this work will be judged done. Set by the delivery owner.")
    c2p_plan_change_ids = fields.One2many(
        "c2p.plan.change", "task_id", string="Plan Changes")

    def _c2p_deadline_day(self):
        self.ensure_one()
        return self.date_deadline and self.date_deadline.date()

    def write(self, vals):
        """Committed dates, assignees, milestones and acceptance criteria on a
        Solutions delivery task move only with the delivery owner's hand.

        Setting a value that was empty is ordinary planning and is left alone.
        Changing one that was already committed is a plan change: a contributor
        is told to propose it, and a delivery owner's direct edit is logged.
        """
        guarded = {"date_deadline", "user_ids", "milestone_id",
                   "c2p_acceptance_criteria"} & set(vals)
        if (not guarded or self.env.su
                or self.env.context.get("c2p_plan_change")):
            return super().write(vals)
        tasks = self.filtered(lambda t: t.project_id.c2p_layer == "delivery")
        if not tasks:
            return super().write(vals)

        before = {t.id: {
            "date_deadline": t._c2p_deadline_day(),
            "user_ids": t.user_ids,
            "milestone_id": t.milestone_id,
            "c2p_acceptance_criteria": t.c2p_acceptance_criteria or "",
        } for t in tasks}
        is_lead = self.env.user.has_group(LEAD_GROUP)
        res = super().write(vals)

        Change = self.env["c2p.plan.change"]
        for task in tasks:
            old = before[task.id]
            moved = []
            if old["date_deadline"] and task._c2p_deadline_day() != old["date_deadline"]:
                moved.append(("date", str(old["date_deadline"]),
                              str(task._c2p_deadline_day() or ""),
                              old["date_deadline"]))
            if old["user_ids"] and task.user_ids != old["user_ids"]:
                moved.append(("reassign",
                              ", ".join(old["user_ids"].mapped("name")),
                              ", ".join(task.user_ids.mapped("name")), None))
            if old["milestone_id"] and task.milestone_id != old["milestone_id"]:
                moved.append(("task", old["milestone_id"].name,
                              task.milestone_id.name or "", None))
            if old["c2p_acceptance_criteria"] and \
                    (task.c2p_acceptance_criteria or "") != old["c2p_acceptance_criteria"]:
                moved.append(("task", _("Acceptance criteria (previous text)"),
                              _("Acceptance criteria changed"), None))
            if not moved:
                continue
            if not is_lead:
                # Raising here rolls the whole write back.
                raise UserError(_(
                    "'%s' is part of the approved plan. You cannot change its "
                    "date, assignee, milestone or acceptance criteria "
                    "directly: use Propose Plan Change and the delivery owner "
                    "will decide.", task.name))
            for kind, previous, new, baseline in moved:
                Change._log_direct_edit(kind, previous, new, task=task,
                                        baseline=baseline)
        return res

    def action_c2p_propose_plan_change(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Propose a plan change"),
            "res_model": "c2p.plan.change",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_task_id": self.id,
                "default_new_deadline": self._c2p_deadline_day() or False,
            },
        }
