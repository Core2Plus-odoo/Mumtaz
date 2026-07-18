from odoo import fields, models


class SaleOrder(models.Model):
    """Proposal-specific narrative fields layered on top of a quotation.

    The Proposal Maker wizard creates a normal ``sale.order`` (so pricing,
    taxes, templates and the CRM pipeline all keep working) and stores the
    narrative context here.  The branded ``c2p_proposal`` QWeb report then
    renders a full document — executive summary, solution architecture,
    methodology, commercial table, AMC and next steps — instead of a bare
    quotation PDF.
    """

    _inherit = "sale.order"

    c2p_is_proposal = fields.Boolean(
        string="Is C2P Proposal", default=False, copy=False,
        help="Marks orders created through the Proposal Maker so the branded "
             "proposal report is offered.")
    c2p_proposal_title = fields.Char(
        string="Proposal Title", default="Odoo ERP Implementation Proposal")
    c2p_exec_summary = fields.Text(string="Executive Summary")
    c2p_pain_points = fields.Text(
        string="Pain Points / Requirements",
        help="One challenge per line — rendered as a bullet list on the proposal.")
    c2p_objectives = fields.Text(
        string="Objectives", help="One objective per line.")
    c2p_industry = fields.Char(string="Client Industry")
    c2p_timeline_weeks = fields.Integer(string="Indicative Timeline (weeks)", default=12)
    c2p_amc_monthly = fields.Monetary(
        string="Monthly AMC", currency_field="currency_id",
        help="Optional post go-live annual maintenance contract, billed monthly.")
    c2p_hosting_note = fields.Text(
        string="Licensing & Hosting Note",
        default="Odoo Enterprise licences and Odoo.sh / cloud hosting are billed "
                "separately by Odoo S.A. at published rates and are not included "
                "in the implementation fees above.")

    # ── Structured content the report iterates over ─────────────────────────
    def _c2p_lines_to_bullets(self, text):
        """Split a textarea into clean non-empty lines."""
        return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

    def _c2p_pain_list(self):
        self.ensure_one()
        pains = self._c2p_lines_to_bullets(self.c2p_pain_points)
        if pains:
            return pains
        return [
            "Disconnected spreadsheets and standalone apps with no single source of truth.",
            "Manual, error-prone data entry duplicated across departments.",
            "Limited real-time visibility into sales, inventory and finance.",
            "Compliance and reporting handled outside the system, late and by hand.",
            "No scalable platform to support growth into new markets or entities.",
        ]

    def _c2p_objective_list(self):
        self.ensure_one()
        objs = self._c2p_lines_to_bullets(self.c2p_objectives)
        if objs:
            return objs
        return [
            "Unify core operations on a single, integrated Odoo platform.",
            "Automate cross-department workflows to cut manual effort and errors.",
            "Give management real-time dashboards and reliable reporting.",
            "Ensure statutory and tax compliance is handled inside the system.",
            "Build a scalable foundation that grows with the business.",
        ]

    def _c2p_benefits(self):
        """Key business benefits — rendered as an icon tile grid."""
        return [
            {"title": "One unified platform",
             "desc": "Every department on a single source of truth."},
            {"title": "Automation",
             "desc": "Manual, repetitive work eliminated across processes."},
            {"title": "Real-time insight",
             "desc": "Live dashboards for sales, inventory and finance."},
            {"title": "Built-in compliance",
             "desc": "VAT / tax and statutory reporting inside the system."},
            {"title": "Scalable foundation",
             "desc": "Grows with new users, branches and entities."},
            {"title": "Anywhere access",
             "desc": "Secure web and mobile access for teams on the go."},
        ]

    def _c2p_methodology(self):
        """The C2P eight-phase delivery methodology."""
        return [
            {"n": 1, "name": "Discovery & Requirement Analysis",
             "desc": "Structured workshops to document current processes, pains, "
                     "data sources and success criteria; sign-off on a Business "
                     "Requirements Document (BRD)."},
            {"n": 2, "name": "Solution Design & Gap-Fit",
             "desc": "Map requirements to standard Odoo, identify configuration vs. "
                     "customisation, and agree the target process design (FRS)."},
            {"n": 3, "name": "Configuration & Base Setup",
             "desc": "Company, chart of accounts, taxes, users, security and the "
                     "in-scope apps configured on a dedicated environment."},
            {"n": 4, "name": "Customisation & Development",
             "desc": "Any approved custom modules, reports and integrations built "
                     "on top of standard Odoo - inherited, never forked."},
            {"n": 5, "name": "Data Migration",
             "desc": "Clean, map and load master and opening data (customers, "
                     "vendors, products, balances) with validation and reconciliation."},
            {"n": 6, "name": "Training & UAT",
             "desc": "Role-based user training and a formal User Acceptance Testing "
                     "cycle against the agreed test scripts."},
            {"n": 7, "name": "Go-Live & Cutover",
             "desc": "Final data load, go/no-go checklist, production cutover and "
                     "hyper-care support in the first weeks of operation."},
            {"n": 8, "name": "Post Go-Live Support & AMC",
             "desc": "Ongoing support, issue resolution, enhancements and periodic "
                     "health checks under the Annual Maintenance Contract."},
        ]

    def _c2p_deliverables(self):
        return [
            "Business Requirements Document (BRD) and Functional Requirements Spec (FRS).",
            "Configured Odoo environment for every in-scope application.",
            "Approved custom modules, reports and integrations (where in scope).",
            "Migrated and reconciled master and opening data.",
            "Role-based training sessions and user manuals.",
            "UAT sign-off, go-live cutover and hyper-care support.",
        ]

    def _c2p_roles(self):
        return [
            {"party": "C2P Consultants", "resp":
                "Project management, solution design, configuration, custom "
                "development, data migration support, training and go-live."},
            {"party": "Client", "resp":
                "Nominate a project sponsor and key users, provide timely access "
                "to data and SMEs, validate designs, and complete UAT sign-off."},
            {"party": "Odoo S.A.", "resp":
                "Enterprise licensing, the Odoo.sh / cloud hosting platform and "
                "underlying product maintenance."},
        ]

    def _c2p_assumptions(self):
        return [
            "Pricing is based on the scope and modules listed in this proposal; "
            "material changes will be handled through a change request.",
            "The client provides clean master data in the agreed template and "
            "timely feedback at each sign-off gate.",
            "One production and one staging environment are assumed unless stated.",
            "Odoo Enterprise licences and hosting are contracted separately with Odoo S.A.",
            "Work is delivered remotely with on-site visits as mutually agreed.",
        ]

    def _c2p_why_choose(self):
        return [
            {"title": "Certified Odoo expertise",
             "desc": "A dedicated Odoo practice delivering end-to-end ERP across "
                     "the GCC and Pakistan."},
            {"title": "Standard-first discipline",
             "desc": "We configure standard Odoo first and customise only where it "
                     "adds real value - lower cost, easier upgrades."},
            {"title": "Business + technical depth",
             "desc": "Finance, tax and process consultants working alongside "
                     "developers, not just coders."},
            {"title": "Compliance built in",
             "desc": "VAT / tax and statutory reporting configured inside the "
                     "system, not bolted on afterwards."},
            {"title": "Long-term partnership",
             "desc": "Structured AMC and advisory retainers keep the platform "
                     "healthy and evolving after go-live."},
        ]

    def _c2p_next_steps(self):
        return [
            "Confirm acceptance of this proposal and commercial terms.",
            "Sign the engagement and raise the mobilisation invoice.",
            "Schedule the Discovery workshops and kick off the project.",
        ]
