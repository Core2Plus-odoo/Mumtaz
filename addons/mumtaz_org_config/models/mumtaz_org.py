"""
mumtaz.org — Organization record for SME multi-company tenants.

SME organisations live in the shared mumtaz_platform database under their
own res.company record.  This model is the control record that binds a
subdomain slug to a company and tracks signup state.
"""
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MumtazOrg(models.Model):
    _name = "mumtaz.org"
    _description = "Mumtaz Organisation (SME)"
    _rec_name = "name"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ── Identity ─────────────────────────────────────────────────────────
    name = fields.Char(
        required=True, tracking=True,
        help="Display name of the organisation.",
    )
    slug = fields.Char(
        required=True, tracking=True, index=True,
        help="URL slug: acme → acme.mumtaz.digital",
    )
    company_id = fields.Many2one(
        "res.company", string="Odoo Company",
        ondelete="restrict", tracking=True, index=True,
        help="The res.company that represents this org in Odoo.",
    )
    active = fields.Boolean(default=True, tracking=True)

    # ── Contact ───────────────────────────────────────────────────────────
    admin_email = fields.Char(
        required=True, tracking=True,
        help="Email of the org administrator who signed up.",
    )
    admin_name = fields.Char(tracking=True)
    phone = fields.Char()
    country_id = fields.Many2one("res.country")

    # ── Plan & Status ────────────────────────────────────────────────────
    plan = fields.Selection(
        [
            ("trial",   "Trial (14 days)"),
            ("starter", "Starter"),
            ("growth",  "Growth"),
            ("scale",   "Scale"),
        ],
        default="trial", required=True, tracking=True,
    )
    state = fields.Selection(
        [
            ("pending",   "Pending Review"),
            ("active",    "Active"),
            ("suspended", "Suspended"),
            ("cancelled", "Cancelled"),
        ],
        default="pending", required=True, tracking=True,
    )
    trial_expiry = fields.Date(tracking=True)

    # ── Branding ─────────────────────────────────────────────────────────
    brand_id = fields.Many2one(
        "mumtaz.brand", string="Brand Config",
        ondelete="set null", tracking=True,
    )
    custom_domain = fields.Char(
        tracking=True,
        help="Optional CNAME domain (e.g. suite.acmebank.com).",
    )

    # ── Computed ─────────────────────────────────────────────────────────
    subdomain_url = fields.Char(
        compute="_compute_subdomain_url", string="Subdomain URL",
    )

    @api.depends("slug")
    def _compute_subdomain_url(self):
        for rec in self:
            rec.subdomain_url = f"https://{rec.slug}.mumtaz.digital" if rec.slug else ""

    # ── Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        ("mumtaz_org_slug_unique", "unique(slug)",
         "Each organisation must have a unique URL slug."),
    ]

    @api.constrains("slug")
    def _check_slug(self):
        pattern = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$")
        reserved = {"admin", "api", "app", "www", "mail", "smtp", "support",
                    "help", "mumtaz", "platform", "portal", "vendor", "marketplace"}
        for rec in self:
            if not pattern.match(rec.slug or ""):
                raise ValidationError(
                    _("Slug '%s' is invalid. Use 3–32 lowercase letters, digits, or hyphens.") % rec.slug
                )
            if rec.slug in reserved:
                raise ValidationError(
                    _("Slug '%s' is reserved and cannot be used.") % rec.slug
                )

    # ── Lifecycle ────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("slug"):
                vals["slug"] = vals["slug"].lower().strip()
        return super().create(vals_list)

    def action_activate(self):
        for rec in self:
            rec.write({"state": "active"})
            rec._ensure_company()
            rec.message_post(body=_("Organisation activated."))

    def action_suspend(self):
        self.write({"state": "suspended"})

    def action_cancel(self):
        self.write({"state": "cancelled", "active": False})

    def _ensure_company(self):
        """Create a res.company for this org if one doesn't exist yet."""
        self.ensure_one()
        if self.company_id:
            return self.company_id
        company = self.env["res.company"].sudo().create({
            "name": self.name,
            "email": self.admin_email,
            "country_id": self.country_id.id if self.country_id else False,
        })
        self.sudo().write({"company_id": company.id})
        # Store the slug on the company for portal routing lookups
        company.sudo().write({"mumtaz_org_slug": self.slug})
        return company

    # ── Portal URL button ─────────────────────────────────────────────────

    def action_open_portal(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.subdomain_url,
            "target": "new",
        }
