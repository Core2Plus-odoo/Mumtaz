from odoo import api, fields, models


class MumtazOnboardingChecklist(models.Model):
    _name = "mumtaz.onboarding.checklist"
    _description = "Mumtaz SME Onboarding Checklist"
    _rec_name = "name"
    _inherit = ["mail.thread"]
    _check_company_auto = True

    # ── Core Links ────────────────────────────────────────────────────
    company_id = fields.Many2one(
        "res.company", required=True, ondelete="cascade",
        index=True, default=lambda self: self.env.company,
    )
    sme_profile_id = fields.Many2one(
        "mumtaz.sme.profile",
        string="SME Profile",
        ondelete="set null",
        domain="[('company_id', '=', company_id)]",
    )
    name = fields.Char(
        compute="_compute_name", store=True, string="Checklist",
    )

    # ── Progress ──────────────────────────────────────────────────────
    progress = fields.Integer(
        compute="_compute_progress", store=True,
        string="Overall Progress (%)",
    )
    onboarding_stage = fields.Selection(
        [
            ("profile", "Company Profile"),
            ("finance", "Finance Setup"),
            ("crm", "Customer & Sales"),
            ("complete", "All Complete"),
        ],
        compute="_compute_onboarding_stage", store=True,
        string="Current Stage", tracking=True,
    )

    # ── Section 1: Company Profile ────────────────────────────────────
    task_company_info = fields.Boolean(
        string="Company Information Complete",
        tracking=True,
        help="Legal name, trading name, type, and industry have been filled in.",
    )
    task_logo = fields.Boolean(
        string="Company Logo Uploaded",
        tracking=True,
        help="A company logo has been uploaded in the system.",
    )
    task_currency = fields.Boolean(
        string="Reporting Currency Set",
        tracking=True,
        help="The company's reporting currency has been confirmed.",
    )

    # ── Section 2: Finance Setup ──────────────────────────────────────
    task_fiscal_year = fields.Boolean(
        string="Fiscal Year Configured",
        tracking=True,
        help="The fiscal year start/end dates are configured.",
    )
    task_chart_of_accounts = fields.Boolean(
        string="Chart of Accounts Reviewed",
        tracking=True,
        help="The chart of accounts has been reviewed and customised if needed.",
    )
    task_bank_account = fields.Boolean(
        string="Bank Account Connected",
        tracking=True,
        help="At least one bank or cash account is set up in the system.",
    )
    task_tax_setup = fields.Boolean(
        string="Tax Configuration Verified",
        tracking=True,
        help="Applicable tax rates and positions have been configured.",
    )
    task_payment_terms = fields.Boolean(
        string="Payment Terms Defined",
        tracking=True,
        help="Default payment terms for customers and vendors are set.",
    )

    # ── Section 3: Customer & Sales Setup ────────────────────────────
    task_first_customer = fields.Boolean(
        string="First Customer Created",
        tracking=True,
        help="At least one customer record exists in the system.",
    )
    task_first_quotation = fields.Boolean(
        string="First Quotation or Order Created",
        tracking=True,
        help="A sales quotation or order has been created.",
    )
    task_first_invoice = fields.Boolean(
        string="First Invoice Issued",
        tracking=True,
        help="A customer invoice has been created and posted.",
    )

    # ── Section 4: Operations ─────────────────────────────────────────
    task_products = fields.Boolean(
        string="Products / Services Defined",
        tracking=True,
        help="At least one product or service is available in the system.",
    )

    # ── Internal ──────────────────────────────────────────────────────
    notes = fields.Text(string="Onboarding Notes")

    # ── Computed ─────────────────────────────────────────────────────
    _TASKS = [
        "task_company_info", "task_logo", "task_currency",
        "task_fiscal_year", "task_chart_of_accounts", "task_bank_account",
        "task_tax_setup", "task_payment_terms",
        "task_first_customer", "task_first_quotation", "task_first_invoice",
        "task_products",
    ]

    @api.depends("company_id")
    def _compute_name(self):
        for rec in self:
            rec.name = f"Onboarding — {rec.company_id.name}" if rec.company_id else "Onboarding Checklist"

    @api.depends(*_TASKS)
    def _compute_progress(self):
        total = len(self._TASKS)
        for rec in self:
            done = sum(1 for t in self._TASKS if rec[t])
            rec.progress = int(done / total * 100) if total else 0

    @api.depends("progress")
    def _compute_onboarding_stage(self):
        for rec in self:
            p = rec.progress
            if p == 100:
                rec.onboarding_stage = "complete"
            elif p >= 67:
                rec.onboarding_stage = "crm"
            elif p >= 34:
                rec.onboarding_stage = "finance"
            else:
                rec.onboarding_stage = "profile"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
        return super().create(vals_list)

    _sql_constraints = [
        ("mumtaz_onboarding_company_unique", "unique(company_id)",
         "Each company can only have one onboarding checklist."),
    ]
