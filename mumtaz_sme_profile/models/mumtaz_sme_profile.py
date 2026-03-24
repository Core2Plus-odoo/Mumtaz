from odoo import api, fields, models


class MumtazSmeProfile(models.Model):
    _name = "mumtaz.sme.profile"
    _description = "Mumtaz SME Company Profile"
    _rec_name = "legal_name"
    _order = "legal_name"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True

    # ── Company Link ───────────────────────────────────────────────────
    company_id = fields.Many2one(
        "res.company", required=True, ondelete="cascade",
        index=True, default=lambda self: self.env.company,
    )

    # ── Legal Identity ─────────────────────────────────────────────────
    legal_name = fields.Char(
        required=True, tracking=True,
        help="Official registered legal name of the business.",
    )
    trade_name = fields.Char(
        tracking=True,
        help="Trading name or brand name used in day-to-day operations.",
    )
    business_type = fields.Selection(
        [
            ("sole_proprietorship", "Sole Proprietorship"),
            ("partnership", "Partnership"),
            ("llc", "LLC / Limited Liability Company"),
            ("corporation", "Corporation / Joint Stock Company"),
            ("cooperative", "Cooperative"),
            ("ngo", "NGO / Non-Profit"),
            ("other", "Other"),
        ],
        tracking=True,
    )
    industry = fields.Selection(
        [
            ("retail", "Retail & Trading"),
            ("manufacturing", "Manufacturing"),
            ("services", "Professional Services"),
            ("food_beverage", "Food & Beverage"),
            ("technology", "Technology"),
            ("healthcare", "Healthcare"),
            ("construction", "Construction & Real Estate"),
            ("logistics", "Logistics & Transport"),
            ("education", "Education"),
            ("finance", "Finance & Insurance"),
            ("agriculture", "Agriculture"),
            ("hospitality", "Hospitality & Tourism"),
            ("other", "Other"),
        ],
        tracking=True,
    )

    # ── Location ───────────────────────────────────────────────────────
    country_id = fields.Many2one("res.country", string="Country")
    city = fields.Char()
    address = fields.Text()

    # ── Registration Numbers ───────────────────────────────────────────
    tax_number = fields.Char(
        string="Tax Registration Number",
        help="Tax registration or TIN number.",
    )
    vat_number = fields.Char(
        string="VAT Number",
        help="Value-added tax registration number.",
    )
    commercial_registration = fields.Char(
        string="Commercial Registration No.",
        help="Company registration or CR number issued by the relevant authority.",
    )

    # ── Contact ───────────────────────────────────────────────────────
    contact_email = fields.Char(string="Primary Contact Email")
    contact_phone = fields.Char(string="Primary Contact Phone")
    website = fields.Char()

    # ── Platform Lifecycle ────────────────────────────────────────────
    onboarding_stage = fields.Selection(
        [
            ("discovery", "Discovery"),
            ("profile_setup", "Profile Setup"),
            ("finance_setup", "Finance Setup"),
            ("operations_setup", "Operations Setup"),
            ("activated", "Activated"),
        ],
        default="discovery",
        required=True,
        tracking=True,
    )
    activation_status = fields.Selection(
        [
            ("pending", "Pending Activation"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("churned", "Churned"),
        ],
        default="pending",
        required=True,
        tracking=True,
    )

    # ── Subscription ──────────────────────────────────────────────────
    subscription_plan = fields.Selection(
        [
            ("starter", "Starter"),
            ("growth", "Growth"),
            ("professional", "Professional"),
            ("enterprise", "Enterprise"),
        ],
        tracking=True,
    )
    subscription_start = fields.Date(string="Subscription Start")
    subscription_end = fields.Date(string="Subscription End")

    # ── Ecosystem / Partner ───────────────────────────────────────────
    brand_id = fields.Many2one(
        "mumtaz.brand",
        string="Partner Brand",
        ondelete="set null",
        help="White-label brand this SME operates under.",
    )
    assigned_ecosystem = fields.Char(
        help="Name of the bank, fintech, or ecosystem partner that onboarded this SME.",
    )

    # ── Profile Completeness ──────────────────────────────────────────
    profile_completeness = fields.Integer(
        compute="_compute_profile_completeness",
        store=True,
        string="Profile Completeness (%)",
    )

    notes = fields.Text(string="Internal Notes")

    @api.depends(
        "legal_name", "trade_name", "business_type", "industry",
        "country_id", "tax_number", "contact_email", "contact_phone",
    )
    def _compute_profile_completeness(self):
        scored_fields = [
            "legal_name", "trade_name", "business_type", "industry",
            "country_id", "tax_number", "contact_email", "contact_phone",
        ]
        total = len(scored_fields)
        for rec in self:
            filled = sum(1 for f in scored_fields if rec[f])
            rec.profile_completeness = int(filled / total * 100) if total else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
        return super().create(vals_list)

    _sql_constraints = [
        ("mumtaz_sme_profile_company_unique", "unique(company_id)",
         "Each company can only have one SME profile record."),
    ]
