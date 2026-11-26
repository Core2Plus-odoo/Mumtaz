import logging

import psycopg2

from odoo import _, models

_logger = logging.getLogger(__name__)

PARAM = "c2p.order_projects."
PROJECT_TRACKING = ("project_only", "task_in_project")
TRUE_VALUES = ("1", "true", "True")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        result = super()._action_confirm()
        if not self.env.context.get("c2p_skip_order_projects"):
            for order in self:
                order._c2p_ensure_project_pair_safely()
        return result

    # ── Settings ─────────────────────────────────────────────────────────
    def _c2p_settings(self):
        """The switch and its two ids, or None while the feature is off."""
        # sudo: system parameters are read for every user who confirms an order
        get = self.env["ir.config_parameter"].sudo().get_param
        if get(PARAM + "enabled") not in TRUE_VALUES:
            return None
        return {
            "company_id": int(get(PARAM + "delivery_company_id") or 0),
            "template_id": int(get(PARAM + "default_delivery_template_id") or 0),
            "pair": get(PARAM + "pair_in_tracker", "1") in TRUE_VALUES,
        }

    def _c2p_project_lines(self):
        """Lines whose product creates a project (the qualifying rule)."""
        return self.order_line.filtered(
            lambda line: not line.display_type
            and line.product_id.service_tracking in PROJECT_TRACKING)

    def _c2p_note(self, text):
        self.message_post(body=text, subtype_xmlid="mail.mt_note")

    # ── Entry point ──────────────────────────────────────────────────────
    def _c2p_ensure_project_pair_safely(self):
        """Never let this module stop a confirmation."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self._c2p_ensure_project_pair()
        except Exception:
            _logger.exception(
                "c2p_order_projects: could not set up projects for %s", self.name)
            self._c2p_note(_(
                "Automatic project set-up failed. The order is confirmed. "
                "See the server log, or ask an administrator to run it again."))

    def _c2p_ensure_project_pair(self):
        """Make sure this order has its oversight and delivery project.

        Safe to call any number of times. Returns the delivery project, or an
        empty recordset when nothing applies.
        """
        self.ensure_one()
        Project = self.env["project.project"]
        settings = self._c2p_settings()
        lines = self._c2p_project_lines()
        if not settings or self.state != "sale" or not lines:
            return Project
        # sudo: the confirming user may lack access to the delivery company's project
        found = Project.sudo().with_context(active_test=False).search([
            ("c2p_source_order_id", "=", self.id),
            ("is_template", "=", False)])
        oversight = found.filtered(lambda p: p.c2p_project_role == "oversight")[:1]
        delivery = found.filtered(lambda p: p.c2p_project_role == "delivery")[:1]
        if not oversight:
            oversight = self._c2p_tag_oversight(lines)
        if not oversight:
            self._c2p_note(_(
                "No oversight project exists for this order, so no delivery "
                "project was created."))
            return Project
        if delivery:
            return delivery
        return self._c2p_create_delivery(oversight, lines, settings)

    # ── Oversight project ────────────────────────────────────────────────
    def _c2p_tag_oversight(self, lines):
        """Tag the project the standard flow created for this order."""
        # sudo: order lines and their projects can belong to another company
        candidates = lines.sudo().mapped("project_id").with_context(active_test=False)
        candidates = candidates.filtered(
            lambda p: not p.is_template
            and p.company_id == self.company_id
            and not p.c2p_source_order_id)
        if not candidates:
            return candidates
        project = candidates[0]
        project.write({"c2p_source_order_id": self.id,
                       "c2p_project_role": "oversight"})
        return project

    # ── Delivery project ─────────────────────────────────────────────────
    def _c2p_delivery_template(self, lines, settings):
        Project = self.env["project.project"].sudo().with_context(active_test=False)  # sudo: the template belongs to the delivery company
        template = lines.product_id.product_tmpl_id.filtered(
            "c2p_delivery_template_id")[:1].c2p_delivery_template_id
        if not template and settings["template_id"]:
            template = Project.browse(settings["template_id"]).exists()
        return template

    def _c2p_create_delivery(self, oversight, lines, settings):
        company = self.env["res.company"].browse(settings["company_id"]).exists()
        if not company or company == self.company_id:
            self._c2p_note(_(
                "No delivery project was created: the delivery company is not "
                "set, or is the same as the order's company."))
            return self.env["project.project"]
        template = self._c2p_delivery_template(lines, settings)
        if not template or not template.is_template or not template.active:
            self._c2p_note(_(
                "No delivery project was created: no active delivery "
                "template is set for this order."))
            return self.env["project.project"]
        values = {
            "name": "%s – Delivery" % oversight.name,
            "company_id": company.id,
            "partner_id": oversight.partner_id.id,
            "user_id": oversight.user_id.id,
            "allow_milestones": True,
            "c2p_source_order_id": self.id,
            "c2p_project_role": "delivery",
        }
        try:
            with self.env.cr.savepoint():
                # sudo: the delivery project is created in another company
                delivery = template.sudo().with_company(company).action_create_from_template(values)
        except psycopg2.IntegrityError:
            # A concurrent confirmation won the race; the index held.
            # sudo: see above
            return self.env["project.project"].sudo().with_context(active_test=False).search([
                ("c2p_source_order_id", "=", self.id),
                ("c2p_project_role", "=", "delivery"),
                ("is_template", "=", False)], limit=1)
        self._c2p_link_legacy(oversight, delivery)
        if settings["pair"]:
            self._c2p_pair_in_tracker(oversight, delivery)
        oversight.message_post(
            body=_("Delivery project created in %(company)s: %(name)s",
                   company=company.name, name=delivery.name),
            subtype_xmlid="mail.mt_note")
        return delivery

    def _c2p_link_legacy(self, oversight, delivery):
        """Keep the database-only links and the billing mirror working.

        The live automations (milestone to billing) read custom fields that
        exist only on that database. Where they exist they are filled in the
        same way as before; elsewhere this does nothing.
        """
        fields_ = oversight._fields
        if "x_delivery_project_id" not in fields_ or "x_billing_project_id" not in fields_:
            return
        # sudo: the delivery project belongs to another company
        delivery.sudo().write({"x_billing_project_id": oversight.id})
        oversight.sudo().write({"x_delivery_project_id": delivery.id})  # sudo: same pair
        if "x_billing_milestone_id" not in delivery.env["project.milestone"]._fields:
            return
        for milestone in oversight.milestone_ids:
            delivery.env["project.milestone"].sudo().create({  # sudo: same pair
                "name": milestone.name,
                "project_id": delivery.id,
                "deadline": milestone.deadline,
                "is_reached": milestone.is_reached,
                "x_billing_milestone_id": milestone.id,
            })

    def _c2p_pair_in_tracker(self, oversight, delivery):
        """Layers and counterpart for the Project Tracker, when it is safe.

        The tracker refuses a delivery task that has left Backlog without an
        owner, a date and a milestone. A template with no Backlog stage would
        therefore trap its first edit, so such a pair is left unpaired.
        """
        if oversight.c2p_counterpart_id or oversight.c2p_layer:
            return
        if "backlog" not in [(s.name or "").strip().lower() for s in delivery.type_ids]:
            self._c2p_note(_(
                "The projects were not paired in the Project Tracker: the "
                "delivery template has no Backlog stage."))
            return
        # sudo: both projects are in different companies
        delivery.sudo().write({"c2p_layer": "delivery"})
        oversight.sudo().write({"c2p_layer": "portfolio",  # sudo: same pair
                                "c2p_counterpart_id": delivery.id})
