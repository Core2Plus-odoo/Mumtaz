import re
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MumtazOrganization(models.Model):
    _name = "mumtaz.organization"
    _description = "Mumtaz Organization"
    _rec_name = "name"
    _order = "name"
    _inherit = ["mail.thread"]

    # ── Identity ──────────────────────────────────────────────────────
    name = fields.Char(required=True, tracking=True)
    slug = fields.Char(
        required=True, index=True,
        help="URL-safe identifier used in /org/<slug>/ routes.",
    )
    tagline = fields.Char(
        help="Short one-line description shown on public profile.",
    )
    description = fields.Html(
        help="Full public-facing description for the organisation profile page.",
    )
    logo = fields.Binary(attachment=True)
    logo_filename = fields.Char()
    industry = fields.Selection(
        [
            ("manufacturing", "Manufacturing & Industry"),
            ("it", "IT & Technology"),
            ("retail", "Retail & Wholesale"),
            ("construction", "Construction & Real Estate"),
            ("logistics", "Logistics & Freight"),
            ("food", "Food & Beverage"),
            ("healthcare", "Healthcare & Pharma"),
            ("finance", "Financial Services"),
            ("hr", "HR & Staffing"),
            ("marketing", "Marketing & Media"),
            ("professional", "Professional Services"),
            ("other", "Other"),
        ],
        default="other",
        tracking=True,
    )
    country_id = fields.Many2one("res.country", string="Country", tracking=True)
    company_id = fields.Many2one(
        "res.company", string="Owning Company",
        default=lambda self: self.env.company,
        tracking=True,
    )

    # ── Contact ───────────────────────────────────────────────────────
    website_url = fields.Char(string="Website")
    email = fields.Char(string="Contact Email")
    phone = fields.Char(string="Contact Phone")

    # ── State ─────────────────────────────────────────────────────────
    state = fields.Selection(
        [("active", "Active"), ("pending", "Pending Review"), ("suspended", "Suspended")],
        default="active",
        tracking=True,
    )
    is_public = fields.Boolean(
        default=True,
        help="Public orgs appear in /org/<slug>/ and signup pages.",
        tracking=True,
    )
    active = fields.Boolean(default=True)

    # ── Stats (computed from signups) ─────────────────────────────────
    signup_ids = fields.One2many("mumtaz.sme.signup", "org_id", string="SME Signups")
    member_count = fields.Integer(compute="_compute_member_count", store=True)

    @api.depends("signup_ids")
    def _compute_member_count(self):
        for rec in self:
            rec.member_count = len(rec.signup_ids)

    # ── Constraints ───────────────────────────────────────────────────
    _sql_slug_unique = models.Constraint("unique(slug)", "Organisation slug must be unique.")

    @api.constrains("slug")
    def _check_slug(self):
        for rec in self:
            if not re.match(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$", rec.slug or ""):
                raise ValidationError(
                    "Slug must be 3–64 lowercase letters, digits, or hyphens and "
                    "cannot start or end with a hyphen."
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("slug") and vals.get("name"):
                vals["slug"] = self._slugify(vals["name"])
        return super().create(vals_list)

    @api.model
    def _slugify(self, name: str) -> str:
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")[:60]
        return slug or "org"

    def action_suspend(self):
        self.write({"state": "suspended"})

    def action_activate(self):
        self.write({"state": "active"})
