from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    # This field, and the UNIQUE constraint on it, are the whole duplicate
    # guard. Everything else in the conversion path is convenience.
    #
    # PostgreSQL treats NULLs as distinct under a UNIQUE constraint, so the
    # overwhelming majority of tasks — which have no meeting origin — are
    # unaffected, while any two tasks claiming the same action reference is a
    # database error rather than a silent duplicate.
    #
    # copy=False matters more than it looks: duplicating a task must not carry
    # the reference across, or the copy would collide with its own original.
    c2p_meeting_action_ref = fields.Char(
        string="Meeting Action Reference", readonly=True, copy=False,
        index=True,
        help="The reference of the meeting action item this task came from. "
             "Unique across tasks, which is what makes conversion idempotent.")

    c2p_meeting_action_ids = fields.One2many(
        "c2p.meeting.action", "task_id", string="Meeting Actions",
        readonly=True,
        help="The action item that created this task, for provenance.")

    _meeting_action_ref_unique = models.Constraint(
        "UNIQUE(c2p_meeting_action_ref)",
        "A task already exists for that meeting action item.")
