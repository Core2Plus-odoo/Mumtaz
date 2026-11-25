from odoo import api, fields, models

from .project_milestone import HEALTH

# Worst first. Grey ranks last: a project is grey only when no milestone has a
# forecast at all.
ORDER = ["red", "amber", "green"]


class ProjectProject(models.Model):
    _inherit = "project.project"

    c2p_milestone_health = fields.Selection(
        HEALTH, string="Milestone Health",
        compute="_compute_c2p_milestone_health", store=True,
        help="The colour of this project's worst milestone.")

    @api.depends("milestone_ids.c2p_health")
    def _compute_c2p_milestone_health(self):
        for project in self:
            colours = set(project.milestone_ids.mapped("c2p_health"))
            project.c2p_milestone_health = next(
                (c for c in ORDER if c in colours), "grey")
