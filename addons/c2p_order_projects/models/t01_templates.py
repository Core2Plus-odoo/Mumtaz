"""T01 Rapid Odoo Implementation: the standard process, as two project templates.

The process lives here as data so it is defined once. The admin action creates
the two templates in the right companies; it is safe to press twice. The team
follows the tasks and marks them done in the delivery project.
"""
from markupsafe import Markup

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

NAME = "T01 Rapid Odoo Implementation"
OVERSIGHT_STAGES = ["Not Started", "In Progress", "Blocked", "Client Review", "Done"]
DELIVERY_STAGES = ["Backlog", "To Do", "In Progress", "Waiting on Client", "Review", "Done"]

# Oversight gate tasks: the tracker recognises "M<n>" at the start of the name.
OVERSIGHT_GATES = ["M1 Kickoff", "M2 Client acceptance", "M3 Closure"]
GATES = ["G1", "G2", "G3"]

# (name, owner role, after, plan day, checklist, evidence, sign-off, gate)
TASKS = [
    ("R01 Initiation: Kickoff", "Consultants Lead", [], 2,
     ["Client contact confirmed", "Apps in scope listed", "Scope agreed in writing",
      "Client access owner named"],
     "Kickoff brief and minutes of meeting", "Consultants", "G1"),
    ("R02 Discovery: Confirm requirements", "Functional", ["R01"], 5,
     ["Critical flows listed", "Exclusions listed", "Data needed from the client listed"],
     "Requirements checklist", "Client approver", "G2"),
    ("R03 Configure: Environment and setup", "Solutions Lead", ["R02"], 10,
     ["Environment verified", "Roles and access set", "Standard setup done"],
     "Setup record", "Internal review", "G2"),
    ("R04 Testing: Data and process tests", "Functional and QA", ["R03"], 14,
     ["Master data loaded and checked", "End-to-end flows tested", "Exceptions tested"],
     "Test results", "QA", "G2"),
    ("R05 Testing: User walkthrough", "Functional", ["R04"], 16,
     ["Demo given to the client team", "Notes taken", "Open questions listed"],
     "Walkthrough note", "", "G2"),
    ("R06 Deploy: Acceptance and readiness", "Project Manager", ["R04", "R05"], 18,
     ["Defects cleared or agreed", "User access confirmed", "Backup owner named"],
     "Readiness record", "Client", "G2"),
    ("R07 Closure: Hypercare and handover", "Support", ["R06"], 25,
     ["Open issues listed", "Support owner named", "Handover documents sent"],
     "Handover note", "Closure", "G3"),
]


def _description(task):
    name, role, after, day, checklist, evidence, signoff, gate = task
    parts = [Markup("<p>Plan: D+%d</p>") % day,
             Markup("<p>Owner role: %s</p>") % role]
    if after:
        parts.append(Markup("<p>Starts after: %s</p>") % ", ".join(after))
    parts.append(Markup("<p>Checklist:</p><ul>%s</ul>") % Markup("").join(
        Markup("<li>%s</li>") % item for item in checklist))
    parts.append(Markup("<p>Proof to keep: %s</p>") % evidence)
    if signoff:
        parts.append(Markup("<p>Sign-off: %s</p>") % signoff)
    parts.append(Markup("<p>Gate: %s</p>") % gate)
    return Markup("").join(parts)


class ProjectProject(models.Model):
    _inherit = "project.project"

    @api.model
    def c2p_create_t01_templates(self):
        """Create the two T01 templates, or report that they exist.

        Oversight goes to the current company, delivery to the delivery
        company from the system parameters. Nothing existing is changed.
        """
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only an administrator can create the T01 templates."))
        icp = self.env["ir.config_parameter"].sudo()  # sudo: system parameter read
        delivery_id = int(icp.get_param("c2p.order_projects.delivery_company_id") or 0)
        delivery_company = self.env["res.company"].browse(delivery_id).exists()
        if not delivery_company:
            raise UserError(_(
                "Set the delivery company first (system parameter "
                "c2p.order_projects.delivery_company_id)."))
        oversight_company = self.env.company
        if oversight_company == delivery_company:
            raise UserError(_(
                "Switch to the Consultants company first: the oversight "
                "template is created in the current company."))
        oversight, made_o = self._c2p_t01_oversight(oversight_company)
        delivery, made_d = self._c2p_t01_delivery(delivery_company)
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {
                "title": _("T01 templates"), "type": "success", "sticky": False,
                "message": _(
                    "Oversight: %(o)s. Delivery: %(d)s. Set them on the product: "
                    "the oversight one as Project Template, the delivery one as "
                    "Delivery Project Template.",
                    o=_("created") if made_o else _("already there"),
                    d=_("created") if made_d else _("already there")),
            },
        }

    # ── helpers ──────────────────────────────────────────────────────────
    @api.model
    def _c2p_t01_find(self, key, company):
        """The template made earlier for this company, found by its key."""
        # sudo: the key lives in ir.model.data and the project can be in another company
        data = self.env["ir.model.data"].sudo().search([
            ("module", "=", "c2p_order_projects"),
            ("name", "=", "%s_c%d" % (key, company.id)),
            ("model", "=", "project.project")], limit=1)
        # sudo: see above
        return self.sudo().with_context(active_test=False).browse(data.res_id).exists()

    @api.model
    def _c2p_t01_register(self, key, company, project):
        # sudo: records the key of a template created by this administrator action
        self.env["ir.model.data"].sudo().create({
            "module": "c2p_order_projects", "name": "%s_c%d" % (key, company.id),
            "model": "project.project", "res_id": project.id, "noupdate": True})

    @api.model
    def _c2p_t01_project(self, key, company, title, stage_names):
        project = self._c2p_t01_find(key, company)
        if project:
            return project, False
        # sudo: the template is created in a company the administrator may not have switched to
        project = self.sudo().with_company(company).create({
            "name": title, "is_template": True, "company_id": company.id,
            "allow_milestones": True, "allow_task_dependencies": True,
            "c2p_layer": "template",
        })
        Stage = self.env["project.task.type"].sudo().with_company(company)  # sudo: see above
        for sequence, stage in enumerate(stage_names, start=1):
            Stage.create({"name": stage, "sequence": sequence,
                          "fold": stage == "Done",
                          "project_ids": [(4, project.id)]})
        self._c2p_t01_register(key, company, project)
        return project, True

    @api.model
    def _c2p_t01_oversight(self, company):
        project, made = self._c2p_t01_project(
            "t01_oversight", company, "%s – Oversight" % NAME, OVERSIGHT_STAGES)
        if made:
            first = project.type_ids.sorted("sequence")[:1]
            Task = self.env["project.task"].sudo().with_company(company)  # sudo: see above
            for name in OVERSIGHT_GATES:
                Task.create({"name": name, "project_id": project.id,
                             "stage_id": first.id})
        return project, made

    @api.model
    def _c2p_t01_delivery(self, company):
        project, made = self._c2p_t01_project(
            "t01_delivery", company, "%s – Delivery" % NAME, DELIVERY_STAGES)
        if made:
            backlog = project.type_ids.sorted("sequence")[:1]
            Milestone = self.env["project.milestone"].sudo().with_company(company)  # sudo: see above
            gates = {name: Milestone.create({"name": name, "project_id": project.id})
                     for name in GATES}
            Task = self.env["project.task"].sudo().with_company(company)  # sudo: see above
            by_code = {}
            for spec in TASKS:
                name, after, gate = spec[0], spec[2], spec[7]
                task = Task.create({
                    "name": name, "project_id": project.id, "stage_id": backlog.id,
                    "milestone_id": gates[gate].id,
                    "description": _description(spec),
                    "depend_on_ids": [(6, 0, [by_code[c].id for c in after])],
                })
                by_code[name.split()[0]] = task
        return project, made
